#include <signal.h> // For redis.h 'siginfo_t'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <assert.h>
#undef __GNUC__  // allow malloc (needed for uthash)  (see redis.h ln 1403)
#include "uthash.h"
#include "kvolve.h"
#include "redis.h"


static struct version_hash * vers_list = NULL;

/* return 1 to halt normal execution flow. return 0 to continue as normal */
int kvolve_process_command(redisClient *c){
  
    if (c->argc > 2 && strcasecmp((char*)c->argv[0]->ptr, "client") == 0 && 
                 strcasecmp((char*)c->argv[1]->ptr, "setname") == 0) {
        kvolve_append_version((char*)c->argv[2]->ptr);
    } else if (c->argc > 2 && strcasecmp((char*)c->argv[0]->ptr, "set") == 0){
        kvolve_set(c);
    } else if (c->argc > 1 && strcasecmp((char*)c->argv[0]->ptr, "get") == 0){
        kvolve_get(c);
    }
 
    // TODO, do we ever need to halt normal execution flow?
    return 0;
}
/* return 1 if appended new version.  else return 0 */
int kvolve_append_version(char * vers_str){
  
    int toprocess =  strlen(vers_str);
    char * cpy = malloc(strlen(vers_str)+1);
    strcpy(cpy, vers_str);

    /* TODO verification/validation.....*/
    while(1) {
        char * ns_lookup; 
        char * vers;
        if (strcmp(cpy, vers_str) == 0)
            ns_lookup = strtok(cpy, "@");
        else
            ns_lookup = strtok(NULL, "@"); /* We've already started processing */
        vers = strtok(NULL, ",");
        int pos = strlen(vers);
        printf("%s %s %s %d %d", ns_lookup, vers, vers_str, toprocess, pos);
  
        struct version_hash *e = NULL;
  
        HASH_FIND(hh, vers_list, ns_lookup, strlen(ns_lookup), e);  /* id already in the hash? */
        if (e==NULL){
            e = (struct version_hash*)malloc(sizeof(struct version_hash));
            e->ns = malloc(strlen(ns_lookup)+1);
            strcpy(e->ns, ns_lookup); 
            e->num_versions = 1;
            e->versions = calloc(10,sizeof(char*)); /* TODO, dynamically resize array */
            e->versions[0] = malloc(strlen(vers)+1);
            strcpy(e->versions[0], vers);
            HASH_ADD_KEYPTR(hh, vers_list, e->ns, strlen(e->ns), e);  /* id: name of key field */
        } else if(strcmp(e->versions[e->num_versions-1], vers) == 0){
            // TODO do we need to do something here?
        } else{
            
            /* TODO correct version validation!!!!! */
            e->num_versions++;
            if(e->num_versions > 10){
                /* TODO realloc*/
                printf("CANNOT APPEND, REALLOC NOT IMPLEMENTED, TOO MANY VERSIONS. ");
                return 0;
            }
            /* TODO validation!!!!!!!! */
            e->versions[e->num_versions-1] = malloc(strlen(vers)+1);
            strcpy(e->versions[e->num_versions-1], vers);
        }
        if(&vers[pos] == &cpy[toprocess])
            return 1;
    }
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
        len = split - lookup;
        ns = malloc(len+1);
        tofree = 1;
        snprintf(ns, len+1, "%s", lookup);
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
    robj *o = lookupKeyRead(c->db, c->argv[1]);
    if(!o)
        return;

    /* Check to see if the version is current */
    if (strcmp(o->vers, v->versions[v->num_versions-1]))
        return;

    /* Key is present at an older version. Time to update, if available. */
    // TODO implement

}

#define __GNUC__  // "re-unallow" malloc
