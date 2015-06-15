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
#include "kvolve_internal.h"
#include "redis.h"
#include "kvolve_upd.h"

static struct version_hash * vers_list = NULL;
#define KV_INIT_SZ 10

struct version_hash * get_vers_list(void){
   return vers_list;
}


struct version_hash * kvolve_create_ns(char *ns_lookup, char *prev_ns, char * v0){
    struct version_hash * v = (struct version_hash*)malloc(sizeof(struct version_hash));
    v->ns = malloc(strlen(ns_lookup)+1);
    strcpy(v->ns, ns_lookup); 
    v->prev_ns = NULL;
    if (prev_ns){
        v->prev_ns = malloc(strlen(prev_ns)+1);
        strcpy(v->prev_ns, prev_ns); 
    }
    v->num_versions = 1;
    v->versions = calloc(KV_INIT_SZ,sizeof(char*));
    v->versions[0] = malloc(strlen(v0)+1);
    v->info = calloc(KV_INIT_SZ,sizeof(struct kvolve_upd_info*));
    v->info[0] = NULL;
    strcpy(v->versions[0], v0);
    HASH_ADD_KEYPTR(hh, vers_list, v->ns, strlen(v->ns), v);  /* id: name of key field */
    return v;
}

/* Get the keyname from @orig_key and combine it with @old_ns.  
 * Allocates memory for the new string and returns it. */
char * kvolve_prev_name(char * orig_key, char *old_ns){
    char * name = strrchr(orig_key, ':');
    char * ret = malloc(strlen(name)+strlen(old_ns) +1);
    strcpy(ret, old_ns);
    strcat(ret, name);
    return ret;
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
            kvolve_create_ns(ns_lookup, NULL, vers);
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

int kvolve_get_flags(redisClient *c){
    int flags = REDIS_SET_NO_FLAGS;
    int j;

    for (j = 3; j < c->argc; j++) {
        char *a = c->argv[j]->ptr;

        if ((a[0] == 'n' || a[0] == 'N') &&
            (a[1] == 'x' || a[1] == 'X') && a[2] == '\0') {
            flags |= REDIS_SET_NX;
        } else if ((a[0] == 'x' || a[0] == 'X') &&
                   (a[1] == 'x' || a[1] == 'X') && a[2] == '\0') {
            flags |= REDIS_SET_XX;
        }

    }
    return flags;
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
        } else if (strcmp(list->from_ns, list->to_ns) != 0){
            /* check to see if we need a new namespace */
            HASH_FIND(hh, vers_list, list->to_ns, strlen(list->to_ns), v);
            if (v != NULL){
                printf("Cannot merge into existing ns (%s) from ns (%s).\n", 
                       list->to_ns, list->from_ns);
            }
            else{
                v = kvolve_create_ns(list->to_ns, list->from_ns, list->to_vers);
                v->info[0] = list;
                item_used = 1;
                succ_loaded++;
            }
            ok_to_load = 0;
        } else {
            /* make sure update was not already loaded */
            for (i = 0; i < v->num_versions; i++){
                if (strcmp(v->versions[i], list->to_ns) == 0){
                    printf("ERROR, previous version %s already loaded...\n", list->to_ns);
                    ok_to_load = 0;
                    break;
                }
            }
        }
        /* If not a new ns, make sure the previous version exists */
        if (v->prev_ns == NULL && strcmp(v->versions[v->num_versions-1], list->from_vers) != 0){
            printf("No such version (%s) to upgrade for ns (%s).\n", 
                   list->from_vers, list->from_ns);
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

            v->info[v->num_versions-1] = list;
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
struct version_hash * version_hash_lookup_from_prev(char * lookup){
    struct version_hash *v = NULL;
    /* Get the current version for the namespace, if it exists */
    HASH_FIND(hh, vers_list, lookup, strlen(lookup), v);
    return v;
}

///* returns an array of objects at all possible versions of c->arg[v]@ns v 
//  
//   Allocates memory.  You must free it yourself.
//*/
//int kvolve_get_all_versions(redisClient * c, robj *** arr){
//
//    int num_vers = 1, curr;
//    struct version_hash * v = version_hash_lookup((char*)c->argv[1]->ptr);
//    struct version_hash * tmp = v;
//    assert(v != NULL);
//    /* Get number of prev namespaces */
//    while(tmp && tmp->prev_ns != NULL){
//        tmp = version_hash_lookup(tmp->prev_ns);
//        num_vers++;
//    }
//    *arr = calloc(num_vers, sizeof(robj*));
//    (*arr)[0] = createStringObject((char*)c->argv[1]->ptr,strlen((char*)c->argv[1]->ptr));
//    printf("%p\n", (void*)(*arr)[0]);
//
//    /* curr = 1 because arr[0] already assigned w current vers */
//    tmp = v;
//    for(curr=1; curr<num_vers; curr++){
//        char * old = kvolve_prev_name((char*)c->argv[1]->ptr, tmp->prev_ns);
//        printf("creating with old = %s\n", old);
//        (*arr)[curr] = createStringObject(old,strlen(old));
//        free(old);
//        if(tmp->prev_ns)
//            tmp = version_hash_lookup(tmp->prev_ns);
//    }
//   return num_vers;
//}
//
///* Return 1 if the key exists at any version; else return 0 */
//int kvolve_exists_anywhere(redisClient * c){
//    robj ** objarr = NULL;
//    int i, ret=0, numobj;
//    /* first, check for the current to see if we can short-cut */
//    if(lookupKeyRead(c->db, c->argv[1]))
//        return 1;
//
//    numobj = kvolve_get_all_versions(c, &objarr);
//    for(i=0; i<numobj; i++){
//        printf("Looking up key at %p\n", (void*)objarr[i]);
//        if(lookupKeyRead(c->db, objarr[i])){
//            ret = 1;
//            break;
//        }
//    }
//    for(i=0; i<numobj; i++){
//       zfree(objarr[i]);
//    }
//    free(objarr);
//    return ret;
//}

/* return the VALUE with the namespace that's currently in the db */
robj * kvolve_get_curr_ver(redisClient * c){

    struct version_hash * v = version_hash_lookup((char*)c->argv[1]->ptr);
    struct version_hash * tmp = v;
    robj * key, * val;
    assert(v != NULL);

    /* first check the obvious (current) */
    val = lookupKeyRead(c->db, c->argv[1]);
    if(val) return val;

    /* Iterate prev namespaces */
    while(tmp && tmp->prev_ns){
        printf("tmp is %p\n", (void*)tmp);
        char * old = kvolve_prev_name((char*)c->argv[1]->ptr, tmp->prev_ns);
        DEBUG_PRINT(("creating with old = %s\n", old));
        key = createStringObject(old,strlen(old));
        free(old);
        val = lookupKeyRead(c->db, key);
        zfree(key);
        if (val) return val;
        if(!tmp->prev_ns)
            break;
        tmp = version_hash_lookup(tmp->prev_ns);
    }
    return NULL;
}

void kvolve_internal_rename(redisClient * c, struct version_hash * v) {

    redisClient * c_fake = createClient(-1);
    c_fake->argc = 3;
    c_fake->argv = zmalloc(sizeof(void*)*3);
    char * old = kvolve_prev_name((char*)c->argv[1]->ptr, v->prev_ns);
    c_fake->argv[1] = createStringObject(old,strlen(old));  // do not free. added to db
    c_fake->argv[2] = c->argv[1]; 
    sds ren = sdsnew("rename");
    c_fake->cmd = lookupCommand(ren);
    c_fake->cmd->proc(c_fake);
    zfree(c_fake->argv);
    zfree(c_fake);
    sdsfree(ren);
    free(old);
}

// Checks updates for key c->argv[1] and robj *o (if provided, else o looked up) 
// If check_key is 0, it will not try to update the key (sets, hashes, etc)
void kvolve_check_update_kv_pair(redisClient * c, int check_key, robj * o){

    int i, key_vers = -1, fun;
    struct version_hash * v = version_hash_lookup((char*)c->argv[1]->ptr);

    /* TODO something better than assert fail.
     * Also, should we support 'default namespace' automatically? */
    assert(v != NULL);

    if (!o){
        o = kvolve_get_curr_ver(c);
        if (!o) return;
    }

    /* Check to see if the version is current */
    if (strcmp(o->vers, v->versions[v->num_versions-1])==0)
        return;

    /* Key is present at an older version. Time to update, if available. */
    for (i = 0; i < v->num_versions; i++){
        if (strcmp(v->versions[i], o->vers) == 0){
            key_vers = i;
            break;
        }
    }

    /* Check if we're in the current version for the _old_ namespace */
    if (v->prev_ns && (key_vers == (v->num_versions - 1))){
        DEBUG_PRINT(("Updating from old namespace\n"));
        v = version_hash_lookup_from_prev(v->prev_ns);
        key_vers = -1;
    }

    /* call all update functions */
    for ( ; key_vers < v->num_versions-1; key_vers++){
        /* in some cases, there may be multiple updates */
        if (!v->info[key_vers+1]){
            printf("Warning: no update functions for %s:%s\n", 
                   v->ns, v->versions[key_vers+1]); 
            o->vers = v->versions[key_vers+1];
            continue;
        }
        for (fun=0; fun < v->info[key_vers+1]->num_funs; fun++){
            char * key = (char*)c->argv[1]->ptr;
            char * val = (char*)o->ptr;
            /* next line calls the update func (mods key/val as specified): */
            v->info[key_vers+1]->funs[fun](&key, (void*)&val);
            if (check_key && (key != (char*)c->argv[1]->ptr)){
                DEBUG_PRINT(("Updated key from %s to %s\n", (char*)c->argv[1]->ptr, key));
                kvolve_internal_rename(c, v);
                sdsfree(c->argv[1]->ptr); // free old memory
                //TODO are keys sds???  or just a char *???
                c->argv[1]->ptr = sdsnew(key); // memcpy's key (user alloc'ed)
                free(key); // free user-update-allocated memory
            }
            if (val != (char*)o->ptr){
                DEBUG_PRINT(("Updated value from %s to %s\n", (char*)o->ptr, val));
                sdsfree(o->ptr);
                o->ptr = sdsnew(val);
                free(val);
                /* This will notify any client watching key (normally called 
                 * automatically, but we bypassed by changing val directly */
                signalModifiedKey(c->db,o);
            }
        }
        o->vers = v->versions[key_vers+1];
        if ((v->num_versions-1 == key_vers+1) && v->prev_ns){
            v = version_hash_lookup_from_prev(v->prev_ns);
            if(v->num_versions == 1 && !v->info[0])
                break; /* We're done, no updates in new ns */
            key_vers = -2; /* This will become -1 after the loop decrement */
        }
    }
    server.dirty++;
}
#define __GNUC__  // "re-unallow" malloc
