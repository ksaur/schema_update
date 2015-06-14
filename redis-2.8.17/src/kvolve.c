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
    } else if (c->argc >= 3 && strcasecmp((char*)c->argv[0]->ptr, "mset") == 0){
        kvolve_mset(c);
    } else if (c->argc == 2 && strcasecmp((char*)c->argv[0]->ptr, "get") == 0){
        kvolve_get(c);
    } else if (c->argc >= 2 && strcasecmp((char*)c->argv[0]->ptr, "mget") == 0){
        kvolve_mget(c);
    } else if (c->argc == 3 && strcasecmp((char*)c->argv[0]->ptr, "setnx") == 0){
        kvolve_setnx(c, NULL);
    } else if (c->argc >= 3 && strcasecmp((char*)c->argv[0]->ptr, "sadd") == 0){
        kvolve_sadd(c);
    } else if (c->argc == 2 && strcasecmp((char*)c->argv[0]->ptr, "smembers") == 0){
        kvolve_smembers(c);
    }
 
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

void kvolve_mset(redisClient * c){
    int i;
    redisClient * c_fake = createClient(-1);
    c_fake->db = c->db;
    c_fake->argc = 3;
    c_fake->argv = zmalloc(sizeof(void*)*3);
    sds ren = sdsnew("set");
    c_fake->cmd = lookupCommand(ren);

    assert(c->argc % 2 == 1);
    for (i=1; i < c->argc; i=i+2){
        c_fake->argv[1]= c->argv[i];
        c_fake->argv[2]= c->argv[i+1];
        kvolve_set(c_fake);
    }
    zfree(c_fake->argv);
    zfree(c_fake);
    sdsfree(ren);
}

void kvolve_mget(redisClient * c){
    int i;
    redisClient * c_fake = createClient(-1);
    c_fake->db = c->db;
    c_fake->argc = 2;
    c_fake->argv = zmalloc(sizeof(void*)*2);
    sds ren = sdsnew("get");
    c_fake->cmd = lookupCommand(ren);

    for (i=1; i < c->argc; i++){
        c_fake->argv[1]= c->argv[i];
        kvolve_get(c_fake);
    }
    zfree(c_fake->argv);
    zfree(c_fake);
    sdsfree(ren);
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
    kvolve_check_update_kv_pair(c);
}

void kvolve_smembers(redisClient * c){


    robj * o = lookupKeyRead(c->db, c->argv[1]);
    setTypeIterator *si = setTypeInitIterator(o);
    robj * e = setTypeNextObject(si);
    while(e){
        printf("%p\n", (void*)e);
        e = setTypeNextObject(si);
    }
    // TODO OLD VERSIONS!!!
   // redisClient * c_fake = createClient(-1);
   // c_fake->db = c->db;
   // c_fake->argc = 2;
   // c_fake->argv = zmalloc(sizeof(void*)*2);
   // sds ren = sdsnew("smembers");
   // c_fake->cmd = lookupCommand(ren);
   // c_fake->argv[1]= c->argv[1];
   // c_fake->cmd->proc(c_fake);
   // zfree(c_fake->argv);
   // zfree(c_fake);
   // sdsfree(ren);
    //free(old);

}

void kvolve_sadd(redisClient * c){
    int elem;
    robj * oldobj = NULL;
    char * old = NULL; 
    struct version_hash * v = NULL;
    v = version_hash_lookup((char*)c->argv[1]->ptr);
    assert(v != NULL);
    
    for (elem=2; elem < c->argc; elem++)
        c->argv[elem]->vers = v->versions[v->num_versions-1];
        
    if(v->prev_ns != NULL){ //TODO recurse multiple old ns
        old = kvolve_prev_name((char*)c->argv[1]->ptr, v->prev_ns);
        oldobj = createStringObject(old,strlen(old));
        dbDelete(c->db,oldobj); /* will also free oldobj. */
        free(old);
    }
}

#define __GNUC__  // "re-unallow" malloc
