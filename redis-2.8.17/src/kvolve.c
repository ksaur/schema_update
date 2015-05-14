#include <signal.h> // For redis.h 'siginfo_t'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <assert.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <dlfcn.h>
#undef __GNUC__  // allow malloc (needed for uthash)  (see redis.h ln 1403)
#include "uthash.h"
#include "kvolve.h"
#include "redis.h"
#include "kvolve_upd.h"


static struct version_hash * vers_list = NULL;
#define KV_INIT_SZ 10

/* return 1 to halt normal execution flow. return 0 to continue as normal */
int kvolve_process_command(redisClient *c){
  
    if (c->argc == 3 && (strcasecmp((char*)c->argv[0]->ptr, "client") == 0)
            && (strcasecmp((char*)c->argv[1]->ptr, "setname") == 0)
            && (strncasecmp((char*)c->argv[2]->ptr, "update", 6) == 0)){
        kvolve_update_version((char*)(c->argv[2]->ptr)+6);
    } else if (c->argc == 3 && (strcasecmp((char*)c->argv[0]->ptr, "client") == 0) && 
            (strcasecmp((char*)c->argv[1]->ptr, "setname") == 0)){
        kvolve_check_version((char*)c->argv[2]->ptr);
    } else if (c->argc == 3 && strcasecmp((char*)c->argv[0]->ptr, "set") == 0){
        kvolve_set(c);
    } else if (c->argc == 2 && strcasecmp((char*)c->argv[0]->ptr, "get") == 0){
        kvolve_get(c);
    }
 
    // TODO, do we ever need to halt normal execution flow?
    return 0;
}

struct version_hash * kvolve_create_ns(char *ns_lookup, char * v0){
    struct version_hash * v = (struct version_hash*)malloc(sizeof(struct version_hash));
    v->ns = malloc(strlen(ns_lookup)+1);
    strcpy(v->ns, ns_lookup); 
    v->num_versions = 1;
    v->versions = calloc(KV_INIT_SZ,sizeof(char*));
    v->versions[0] = malloc(strlen(v0)+1);
    v->info = calloc(KV_INIT_SZ,sizeof(struct kvolve_upd_info));
    strcpy(v->versions[0], v0);
    HASH_ADD_KEYPTR(hh, vers_list, v->ns, strlen(v->ns), v);  /* id: name of key field */
    return v;
}
/* return 1 if OK.  else return 0. TODO don't allow connect if err */
int kvolve_check_version(char * vers_str){
  
    int toprocess =  strlen(vers_str);
    char * cpy = malloc(strlen(vers_str)+1);
    strcpy(cpy, vers_str);

    while(1) {
        char * ns_lookup; 
        char * vers;
        if (strcmp(cpy, vers_str) == 0)
            ns_lookup = strtok(cpy, "@");
        else
            ns_lookup = strtok(NULL, "@"); /* We've already started processing */
        vers = strtok(NULL, ",");
        int pos = strlen(vers);
  
        struct version_hash *v = NULL;
  
        HASH_FIND(hh, vers_list, ns_lookup, strlen(ns_lookup), v);  /* id already in the hash? */
        if (v==NULL){
            kvolve_create_ns(ns_lookup, vers);
        } else if (strcmp(v->versions[v->num_versions-1], vers) != 0){
            printf("ERROR, INVALID VERSION (%s). System is at \'%s\' for ns \'%s\'\n", 
                   vers, v->versions[v->num_versions-1], v->ns);
            //TODO don't let it connect.
            return 0;
        } 
        if (&vers[pos] == &cpy[toprocess])
            return 1;
    }
}

/* return number of "struct kvolve_upd_info"'s loaded. */
int kvolve_update_version(char * upd_code){

    void *handle;
    char *errstr;
    kvolve_upd_info_getter fun;
    struct kvolve_upd_info * list, * tmp;
    struct version_hash * v;
    int ok_to_load, succ_loaded = 0, item_used, err, i;
    struct stat s;
  
    DEBUG_PRINT(("Updating with %s\n", upd_code));
    err = stat(upd_code, &s);
    if(-1 == err) {
        printf("ERROR, update file %s does not exist.\n", upd_code);
        return 0;
    }

    handle = dlopen(upd_code, RTLD_LAZY);
    if (handle == NULL){
        errstr = dlerror();
        printf ("A dynamic linking error occurred: (%s)\n", errstr);
        return 0;
    }
    /* apparently there is no way to suppress -pedantic with -02 for dlsym on fptr?*/
    fun = (kvolve_upd_info_getter)dlsym(handle, "get_update_func_list");
    list = fun();
    
    while(list != NULL){
        ok_to_load = 1; 
        item_used = 0;

        HASH_FIND(hh, vers_list, list->from_ns, strlen(list->from_ns), v);
        /* make sure namespace exists */
        if (v == NULL){
            printf("No such namespace (%s) to upgrade.\n", list->from_ns);
            ok_to_load = 0;
        } 
        else {
            /* make sure update was not already loaded */
            for (i = 0; i < v->num_versions; i++){
                if (strcmp(v->versions[i], list->to_ns) == 0){
                    printf("ERROR, previous version %s already loaded...\n", list->to_ns);
                    ok_to_load = 0;
                    break;
                }
            }
        }
        /* make sure the previous version exists */
        if (strcmp(v->versions[v->num_versions-1], list->from_vers) != 0){
            printf("No such version (%s) to upgrade for ns (%s).\n", 
                   list->from_vers, list->from_ns);
            ok_to_load = 0;
        }

        /* check to see if we need a new namespace */
        if (strcmp(list->from_ns, list->to_ns) != 0){
            HASH_FIND(hh, vers_list, list->to_ns, strlen(list->to_ns), v);
            if (v != NULL){
                printf("Cannot merge into existing ns (%s) from ns (%s).\n", 
                       list->to_ns, list->from_ns);
            }
            else{
                v = kvolve_create_ns(list->to_ns, list->to_vers);
                v->info = list;
                item_used = 1;
                succ_loaded++;
            }
            ok_to_load = 0;
        }

        /* if none of the prior checks fired, then load */
        if (ok_to_load){
            
            v->num_versions++;
            if (v->num_versions > KV_INIT_SZ){ /*TODO change this when resize impl'ed */
                /* TODO realloc*/ /* TODO, dynamically resize array */
                printf("CANNOT APPEND, REALLOC NOT IMPLEMENTED, TOO MANY VERSIONS.\n");
                return 0;
            }
            v->versions[v->num_versions-1] = malloc(strlen(list->to_vers)+1);
            strcpy(v->versions[v->num_versions-1], list->to_vers);

            v->info = list;
            item_used = 1;
            succ_loaded++;
        }

        /* if error above, free list and function info. else just advance ptr */
        tmp = list->next;
        if (!item_used) {
            if (list->num_funs)
                free(list->funs);
            free(list);
        }
        list = tmp;

    }
    return succ_loaded;

    /////////////////////// THIS IS HOW TO CALL!
    //list->funs[0]("foo", "bar");

}

/* Looks for a prepended namespace in @lookup, and then lookups and returns the
 * version information in the hashtable if it exists, else returns null.  */
struct version_hash * version_hash_lookup(char * lookup){
    struct version_hash *v = NULL;
    char * ns;
    size_t len;
    int tofree = 0;

    /* Split out the namespace from the key, if a namespace exists. */
    char * split = strrchr(lookup, ':');
    if (split != NULL){
        len = split - lookup + 1;
        ns = malloc(len);
        tofree = 1;
        snprintf(ns, len, "%s", lookup);
    }
    else
        ns = "*"; 

    /* Get the current version for the namespace, if it exists */
    HASH_FIND(hh, vers_list, ns, strlen(ns), v);  
    if (tofree)
        free(ns);
    return v;
}


void kvolve_set(redisClient * c){

    struct version_hash * v = version_hash_lookup((char*)c->argv[1]->ptr);

    /* TODO something better than assert fail.
     * Also, should we support 'default namespace' automatically? */
    assert(v != NULL);
    
	/* set the version field in the value (only the string is stored for the
     * key).  Note that this will automatically blow away any old version. */
    c->argv[2]->vers = v->versions[v->num_versions-1];

}

void kvolve_get(redisClient * c){

    struct version_hash * v = version_hash_lookup((char*)c->argv[1]->ptr);

    /* TODO something better than assert fail.
     * Also, should we support 'default namespace' automatically? */
    assert(v != NULL);

    /* Lookup the key in the database to get the current version */
	/* ...alternatively we could return this here, but that messes up the
     * stats, key expiration, etc...so we'd have to do all that, and mess 
     * with the return packet as well.*/
    robj *o = lookupKeyRead(c->db, c->argv[1]);
    if (!o)
        return;

    /* Check to see if the version is current */
    if (strcmp(o->vers, v->versions[v->num_versions-1]))
        return;

    /* Key is present at an older version. Time to update, if available. */
    // TODO implement

}

#define __GNUC__  // "re-unallow" malloc
