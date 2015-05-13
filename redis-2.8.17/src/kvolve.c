#include <signal.h> // For redis.h 'siginfo_t'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <assert.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
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
  
        struct version_hash *e = NULL;
  
        HASH_FIND(hh, vers_list, ns_lookup, strlen(ns_lookup), e);  /* id already in the hash? */
        if (e==NULL){
            e = (struct version_hash*)malloc(sizeof(struct version_hash));
            e->ns = malloc(strlen(ns_lookup)+1);
            strcpy(e->ns, ns_lookup); 
            e->num_versions = 1;
            e->versions = calloc(KV_INIT_SZ,sizeof(char*));
            e->versions[0] = malloc(strlen(vers)+1);
            e->info = calloc(KV_INIT_SZ,sizeof(struct kvolve_upd_info));
            strcpy(e->versions[0], vers);
            HASH_ADD_KEYPTR(hh, vers_list, e->ns, strlen(e->ns), e);  /* id: name of key field */
        } else if (strcmp(e->versions[e->num_versions-1], vers) != 0){
            printf("ERROR, INVALID VERSION (%s). System is at \'%s\' for ns \'%s\'\n", 
                   vers, e->versions[e->num_versions-1], e->ns);
            //TODO don't let it connect.
            return 0;
        } 
        if (&vers[pos] == &cpy[toprocess])
            return 1;
    }
}

/* return 1 if update loaded.  else return 0. */
int kvolve_update_version(void * upd_code){
  
    DEBUG_PRINT(("Updating with %s\n", (char*)upd_code));
    struct stat s;
    int err = stat(upd_code, &s);
    if(-1 == err) {
        printf("ERROR, update file %s does not exist.\n", (char*)upd_code);
        return 0;
    }
    //int i, toprocess =  strlen(vers_str);
    //char * cpy = malloc(strlen(vers_str)+1);
    //strcpy(cpy, vers_str);

    ///* TODO verification/validation.....*/
    //while(1) {
    //    char * ns_lookup; 
    //    char * vers;
    //    if (strcmp(cpy, vers_str) == 0)
    //        ns_lookup = strtok(cpy, "@");
    //    else
    //        ns_lookup = strtok(NULL, "@"); /* We've already started processing */
    //    vers = strtok(NULL, ",");
    //    int pos = strlen(vers);
  
    //    struct version_hash *e = NULL;
  
    //    HASH_FIND(hh, vers_list, ns_lookup, strlen(ns_lookup), e);  /* id already in the hash? */
    //    if (e==NULL){
    //        printf("ERROR, no such version (%s) for \'%s\'...\n", vers, ns_lookup);
    //    } else if (strcmp(e->versions[e->num_versions-1], vers) == 0){
    //        /* If they try to load code twice, error if it's not the same code */
    //        //TODO finish implementing... memcmp??
    //        //    printf("WARNING, different code already loaded....\n");
    //    } else {
    //        /* Load the update */

    //        // TODO better error handling...
    //        if (!upd_code){
    //            printf("ERROR, no update code to be loaded...\n");
    //            return 0;
    //        } 
    //        for (i = 0; i < e->num_versions; i++){
    //            if (strcmp(e->versions[i], vers) == 0){
    //                printf("ERROR, previous version %s already loaded...\n", vers);
    //                return 0;
    //            }
    //        }
    //        printf("TODO: LOAD FUNCTION!...\n");
    //        e->num_versions++;
    //        if (e->num_versions > KV_INIT_SZ){ /*TODO change this when resize impl'ed */
    //            /* TODO realloc*/ /* TODO, dynamically resize array */
    //            printf("CANNOT APPEND, REALLOC NOT IMPLEMENTED, TOO MANY VERSIONS. ");
    //            return 0;
    //        }
    //        /* TODO validation!!!!!!!! */
    //        e->versions[e->num_versions-1] = malloc(strlen(vers)+1);
    //        strcpy(e->versions[e->num_versions-1], vers);
    //    }
    //    if (&vers[pos] == &cpy[toprocess])
    //        return 1;
    //}
    return 1;
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
