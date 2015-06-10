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
#include "kvolve_internal.h"


/* return 1 to halt normal execution flow. return 0 to continue as normal */
int kvolve_process_command(redisClient *c){
  
    if (c->argc == 3 && (strcasecmp((char*)c->argv[0]->ptr, "client") == 0)
            && (strcasecmp((char*)c->argv[1]->ptr, "setname") == 0)
            && (strncasecmp((char*)c->argv[2]->ptr, "update", 6) == 0)){
        kvolve_update_version((char*)(c->argv[2]->ptr)+6);
    } else if (c->argc == 3 && (strcasecmp((char*)c->argv[0]->ptr, "client") == 0) && 
            (strcasecmp((char*)c->argv[1]->ptr, "setname") == 0)){
        kvolve_check_version((char*)c->argv[2]->ptr);
    } else if (c->argc >= 3 && strcasecmp((char*)c->argv[0]->ptr, "set") == 0){
        kvolve_set(c);
    } else if (c->argc == 2 && strcasecmp((char*)c->argv[0]->ptr, "get") == 0){
        kvolve_get(c);
    } //else if (c->argc == 3 && strcasecmp((char*)c->argv[0]->ptr, "setnx") == 0){
       // kvolve_setnx(c);
    //}
 
    // TODO, do we ever need to halt normal execution flow?
    return 0;
}


/* NX -- Only set the key if it does not already exist 
   Return 0 if set will not occur.  Return 1 if set will occurr. */
/* TODO This assumes that namespace changes do not have value updates as well */
void kvolve_setnx(redisClient * c, struct version_hash * v){

    /* Do nothing if already at current namespace, do nothing*/
    if (lookupKeyRead(c->db, c->argv[1]))
        return;

    robj * present = kvolve_get_curr_ver(c);
    DEBUG_PRINT(("Present is = %p\n", (void*)present));
    /* If doesn't exist anywhere, do nothing */
    if (present == NULL)
        return;
    zfree(present);

    if(!v) /* if the user calls setnx directly instead of using flags w set*/
       v = version_hash_lookup((char*)c->argv[1]->ptr);

    /* But if the key DOES exist at a PRIOR namespace, then we need to
     * rename the key, so that the set doesn't erroneously occur (because
     * it will appear to be fake-missing because it is under the old name.
     *     (Note that the set will not occur!!!) 
     * This leaves the version number at the old, so when a set _does_ occur,
     * the version will be bumped up only at that time. */
    kvolve_internal_rename(c,v);

}

/* XX -- Only set the key if it already exists. */
void kvolve_setxx(redisClient * c, struct version_hash * v){

    /* we can reuse the basics which just renames if necessary*/
    kvolve_setnx(c, v);

	/* If the set occurs, this will correctly bump the version.  If doesn't
     * occur, this will be ignored.*/
    c->argv[2]->vers = v->versions[v->num_versions-1];
}

void kvolve_set(redisClient * c){

    int flags;
    char * old = NULL; 
    robj * oldobj = NULL;
    struct version_hash * v = NULL;

    v = version_hash_lookup((char*)c->argv[1]->ptr);
    /* TODO something better than assert fail.
     * Also, should we support 'default namespace' automatically? */
    assert(v != NULL);

    /* check to see if any xx/nx flags set */
    flags = kvolve_get_flags(c);
    if(flags & REDIS_SET_XX){
        kvolve_setxx(c, v);
        return;
    }
    if(flags & REDIS_SET_NX){
        kvolve_setnx(c, v);
        return;
    }

    /* Set the version field in the value (only the string is stored for the
     * key).  Note that this will automatically blow away any old version. */
    c->argv[2]->vers = v->versions[v->num_versions-1];

    /* Since there are no (nx,xx) flags, the set will occur. 
     * Check to see if it's possible that an old version exists 
     * under another namespace that should be deleted. */
    if(v->prev_ns != NULL){ //TODO recurse multiple old ns
        old = kvolve_prev_name((char*)c->argv[1]->ptr, v->prev_ns);
        oldobj = createStringObject(old,strlen(old));
        dbDelete(c->db,oldobj); /* will also free oldobj. */
        free(old);
    }
}


void kvolve_get(redisClient * c){

    int i, key_vers = -1, fun;
    struct version_hash * v_new = NULL;
    struct version_hash * v = version_hash_lookup((char*)c->argv[1]->ptr);
    char * old = NULL; 
    robj * oldobj = NULL;

    /* TODO something better than assert fail.
     * Also, should we support 'default namespace' automatically? */
    assert(v != NULL);

    /* Lookup the key in the database to get the current version */
	/* ...alternatively we could return this here, but that messes up the
     * stats, key expiration, etc...so we'd have to do all that, and mess 
     * with the return packet as well.*/
	//TODO, use "kvolve_get_all_versions" to test for namespaces that are
	//changed twice...this will only get the immediately previous namespace.
    robj *o = lookupKeyRead(c->db, c->argv[1]);
    if (!o && v->prev_ns != NULL){
        v_new = v;
        HASH_FIND(hh, get_vers_list(), v_new->prev_ns, strlen(v_new->prev_ns), v);
        if  (!v) {
            printf("Could not find previous ns (%s) for curr ns (%s)\n", 
                 v_new->prev_ns, v_new->ns);
            return;
        }
        old = kvolve_prev_name((char*)c->argv[1]->ptr, v_new->prev_ns);
        oldobj = createStringObject(old,strlen(old));
        o = lookupKeyRead(c->db, oldobj);
    }
    /* try again. */
    if (!o)
        return;

    /* Check to see if the version is current */
    if (!v_new && strcmp(o->vers, v->versions[v->num_versions-1])==0)
        return;

    /* Key is present at an older version. Time to update, if available. */
    for (i = 0; i < v->num_versions; i++){
        if (strcmp(v->versions[i], o->vers) == 0){
            key_vers = i;
            break;
        }
    }

    /* Check if we're in the current version for the _old_ namespace */
    if (v_new && (key_vers == (v->num_versions - 1))){
        DEBUG_PRINT(("Updating from old namespace\n"));
        v = v_new;
        key_vers = -1;
        v_new = NULL; /* no need to update from multipe namespaces */
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
            v->info[key_vers+1]->funs[fun](&key, (void*)&val);
            if (key != (char*)c->argv[1]->ptr){
                DEBUG_PRINT(("Updated key from %s to %s\n", (char*)c->argv[1]->ptr, key));
                kvolve_internal_rename(c, v);
                sdsfree(c->argv[1]->ptr); // free old memory
                //TODO are keys sds???  or just a char *???
                c->argv[1]->ptr = sdsnew(key); // memcpy's key (user alloc'ed)
                free(key); // free user-update-allocated memory
                if(oldobj)
                    zfree(oldobj);
                if(old)
                    free(old);
            }
            if (val != (char*)o->ptr){
                DEBUG_PRINT(("Updated value from %s to %s\n", (char*)o->ptr, val));
                sdsfree(o->ptr);
                o->ptr = sdsnew(val);
                free(val);
                /* This will notify any client watching key (normally called 
                 * automatically, but we bypassed by changing val directly */
                if (oldobj)
                    signalModifiedKey(c->db,oldobj);
                else
                    signalModifiedKey(c->db,c->argv[1]);
            }
        }
        o->vers = v->versions[key_vers+1];
        if ((v->num_versions-1 == key_vers+1) && v_new){
            v = v_new;
            key_vers = -2; /* This will become -1 after the loop decrement */
            v_new = NULL;
        }
    }
    server.dirty++;
}


#define __GNUC__  // "re-unallow" malloc
