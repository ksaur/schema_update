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


void kvolve_process_command(redisClient *c){

    kvolve_prevcall_check();
  
    if (c->argc == 3 && (strcasecmp((char*)c->argv[0]->ptr, "client") == 0)
            && (strcasecmp((char*)c->argv[1]->ptr, "setname") == 0)
            && (strncasecmp((char*)c->argv[2]->ptr, "update", 6) == 0)){
        kvolve_load_update((char*)(c->argv[2]->ptr)+6);
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
    } else if (c->argc == 3 && strcasecmp((char*)c->argv[0]->ptr, "getset") == 0){
        kvolve_getset(c);
    } else if (c->argc == 4 && strcasecmp((char*)c->argv[0]->ptr, "getrange") == 0){
        kvolve_getrange(c);
    } else if (c->argc == 2 && strcasecmp((char*)c->argv[0]->ptr, "incr") == 0){
        kvolve_incr(c);
    } else if (c->argc == 3 && strcasecmp((char*)c->argv[0]->ptr, "incrby") == 0){
        kvolve_incrby(c);
    } else if (c->argc >= 2 && strcasecmp((char*)c->argv[0]->ptr, "del") == 0){
        kvolve_del(c);
    } else if (c->argc == 3 && strcasecmp((char*)c->argv[0]->ptr, "setnx") == 0){
        kvolve_setnx(c, NULL);
    } else if (c->argc >= 3 && strcasecmp((char*)c->argv[0]->ptr, "sadd") == 0){
        kvolve_sadd(c);
    } else if (c->argc >= 3 && strcasecmp((char*)c->argv[0]->ptr, "scard") == 0){
        kvolve_scard(c);
    } else if (c->argc >= 2 && strcasecmp((char*)c->argv[0]->ptr, "spop") == 0){
        kvolve_spop(c);
    } else if (c->argc == 2 && strcasecmp((char*)c->argv[0]->ptr, "smembers") == 0){
        kvolve_smembers(c);
    } else if (c->argc == 3 && strcasecmp((char*)c->argv[0]->ptr, "sismember") == 0){
        kvolve_sismember(c);
    } else if (c->argc >= 3 && strcasecmp((char*)c->argv[0]->ptr, "srem") == 0){
        kvolve_srem(c);
    } else if (c->argc >= 4 && strcasecmp((char*)c->argv[0]->ptr, "zadd") == 0){
        kvolve_zadd(c);
    } else if (c->argc >= 3 && strcasecmp((char*)c->argv[0]->ptr, "zcard") == 0){
        kvolve_zcard(c);
    } else if (c->argc == 3 && strcasecmp((char*)c->argv[0]->ptr, "zscore") == 0){
        kvolve_zscore(c);
    } else if (c->argc >= 3 && strcasecmp((char*)c->argv[0]->ptr, "zrem") == 0){
        kvolve_zrem(c);
    } else if (c->argc >= 4 && strcasecmp((char*)c->argv[0]->ptr, "zrange") == 0){
        kvolve_zrange(c);
    }
}

/* NX -- Only set the key if it does not already exist*/
void kvolve_setnx(redisClient * c, struct version_hash * v){

    /* Do nothing if already at current namespace, do nothing*/
    if (lookupKeyRead(c->db, c->argv[1]))
        return;

    robj * present = kvolve_get_db_val(c);
    DEBUG_PRINT(("Present is = %p\n", (void*)present));
    /* If doesn't exist anywhere, do nothing */
    if (present == NULL)
        return;

    if(!v) /* if the user calls setnx directly instead of using flags w set*/
       v = kvolve_version_hash_lookup((char*)c->argv[1]->ptr);

    /* But if the key DOES exist at a PRIOR namespace, then we need to
     * rename the key, so that the set doesn't erroneously occur (because
     * it will appear to be fake-missing because it is under the old name.
     *     (Note that the set will not occur!!!) 
     * This leaves the version number at the old, so when a set _does_ occur,
     * the version will be bumped up only at that time. */
    kvolve_namespace_update(c,v);

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

    assert(c->argc % 2 == 1);
    for (i=1; i < c->argc; i=i+2){
        c_fake->argv[1]= c->argv[i];
        c_fake->argv[2]= c->argv[i+1];
        kvolve_set(c_fake);
    }
    zfree(c_fake->argv);
    zfree(c_fake);
}

/* We only have to worry about namespace changes here. We need to do the rename
 * so it will be deleted properly (and return the right value count*/

void kvolve_del(redisClient * c){
    kvolve_check_rename(c, c->argc);
}

/* check for update, the same as kvolve_get, but a substring */
void kvolve_getrange(redisClient *c){
    kvolve_get(c);
}

/* will just check for update, and do if necessary. Remember, we must keep all
 * set elements at same version. this will do that.*/
void kvolve_sismember(redisClient * c){
    kvolve_smembers(c);
}
void kvolve_srem(redisClient * c){
    kvolve_smembers(c);
}
void kvolve_scard(redisClient * c){
    kvolve_smembers(c);
}
void kvolve_spop(redisClient * c){
    kvolve_smembers(c);
}
void kvolve_incrby(redisClient * c){
    kvolve_incr(c);
}
void kvolve_getset(redisClient * c){
    kvolve_get(c);
}
void kvolve_zcard(redisClient * c){
    kvolve_update_all_zset(c);
}
void kvolve_zrem(redisClient * c){
    kvolve_zcard(c);
}
void kvolve_zscore(redisClient * c){
    kvolve_zcard(c);
}
void kvolve_zrange(redisClient * c){
    kvolve_zcard(c);
}

/* the incr command blows away any version you pass it, because it creates its
 * own object.  Since incr values can ONLY be strings that convert to ints,
 * there is no way that there can be a meaninful value change.  Therefore, we
 * just need to make sure the name is current and go from there. */
void kvolve_incr(redisClient * c){

    struct version_hash * v = kvolve_version_hash_lookup((char*)c->argv[1]->ptr);
    if(!v || !v->prev_ns) return;

    /* check if current at correct ns, or doesn't exist at all*/
    if(lookupKeyRead(c->db, c->argv[1]) || (kvolve_get_db_val(c)==NULL))
        return;

    /* at this point, we must update the namespace */
    kvolve_namespace_update(c, v);

}

void kvolve_mget(redisClient * c){
    int i;
    redisClient * c_fake = createClient(-1);
    c_fake->db = c->db;
    c_fake->argc = 2;
    c_fake->argv = zmalloc(sizeof(void*)*2);

    for (i=1; i < c->argc; i++){
        c_fake->argv[1]= c->argv[i];
        kvolve_get(c_fake);
    }
    zfree(c_fake->argv);
    zfree(c_fake);
}

void kvolve_set(redisClient * c){

    int flags;
    char * old = NULL; 
    robj *o, * oldobj = NULL;
    struct version_hash * v = NULL;

    v = kvolve_version_hash_lookup((char*)c->argv[1]->ptr);
    if(v == NULL) return;

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
        o = kvolve_get_db_val(c);  //if we're current, return
        if ((!o) || strcmp(o->vers, v->versions[v->num_versions-1])==0)
            return;
        old = kvolve_construct_prev_name((char*)c->argv[1]->ptr, v->prev_ns);
        oldobj = createStringObject(old,strlen(old));
        dbDelete(c->db,oldobj); /* will also free oldobj. */
        free(old);
    }
}

void kvolve_get(redisClient * c){
    kvolve_check_update_kv_pair(c, 1, NULL, REDIS_STRING, NULL);
}

void kvolve_smembers(redisClient * c){

    struct version_hash * v = NULL;
    int first = 1;
    v = kvolve_version_hash_lookup((char*)c->argv[1]->ptr);
    if(v == NULL) 
        return;
    robj * o = kvolve_get_db_val(c);
    /* return if object isn't present or is already current */
    if (!o || strcmp(o->vers, v->versions[v->num_versions-1])==0)
        return;

    redisClient * c_fake = createClient(-1);
    c_fake->db = c->db;
    c_fake->argc = 3;
    c_fake->argv = zmalloc(sizeof(void*)*3);
    c_fake->argv[1] = c->argv[1];
    setTypeIterator *si = setTypeInitIterator(o);
    robj * e = setTypeNextObject(si);
    /* call update on each of the set elements */
    while(e){
        c_fake->argv[2] = e;
        kvolve_check_update_kv_pair(c, first, e, REDIS_SET, NULL);
        e = setTypeNextObject(si);
        first = 0;
    }

    /* Update the version string in the set container to match the update we
     * just did on the set members .*/
    o->vers = v->versions[v->num_versions-1];
    zfree(c_fake->argv);
    zfree(c_fake);
}

void kvolve_sadd(redisClient * c){
    robj * oldobj = NULL;
    char * old = NULL; 
    int i;
    struct version_hash * v = NULL;
    v = kvolve_version_hash_lookup((char*)c->argv[1]->ptr);
    if(v == NULL) return;

    /* Check if the set exists or if we're creating a new set.  If we're
     * creating a new set, redis will create it during the call.  (We can't create
     * it ahead of time because redis doesn't allow empty sets. And we can't add
     * the element because it will throw off the return response.)  Therefore,
     * notify networking.c to patchup the set version after the call where the set
     * is created. */
    robj * o = kvolve_get_db_val(c);
    if (o == NULL) {
        kvolve_new_version(c,REDIS_SET);
        return;
    }

    /* make sure all set elements are at this current version and update them
     * all if necessary.  Don't let different members of the same set be at different
     * versions!! (would be a confusing mess.) This will check and return if current,
     * else update other set members to the current version */
    if (strcmp(o->vers, v->versions[v->num_versions-1])!=0)
        kvolve_smembers(c);

    /* Set the version for the new element(s) that is not yet a member */
    for(i=2; i < c->argc; i++)
        c->argv[i]->vers = v->versions[v->num_versions-1];
        
    if((v->prev_ns != NULL) && (strcmp(o->vers,
             v->versions[v->num_versions-1])==0)){ //TODO recurse multiple old ns
        old = kvolve_construct_prev_name((char*)c->argv[1]->ptr, v->prev_ns);
        oldobj = createStringObject(old,strlen(old));
        dbDelete(c->db,oldobj); /* will also free oldobj. */
        free(old);
    }
}

void kvolve_zadd(redisClient * c){
    robj * oldobj = NULL;
    char * old = NULL;
    struct version_hash * v = NULL;
    v = kvolve_version_hash_lookup((char*)c->argv[1]->ptr);
    if(v == NULL) return;

    /* Check if the zset exists or if we're creating a new set.*/
    robj * o = kvolve_get_db_val(c);
    if (o == NULL) {
        kvolve_new_version(c, REDIS_ZSET);
        return;
    }

    /* make sure all set elements are at this current version. Else update all*/
    kvolve_update_all_zset(c);

    if((v->prev_ns != NULL) && (strcmp(o->vers,
             v->versions[v->num_versions-1])==0)){ //TODO recurse multiple old ns
        old = kvolve_construct_prev_name((char*)c->argv[1]->ptr, v->prev_ns);
        oldobj = createStringObject(old,strlen(old));
        dbDelete(c->db,oldobj); /* will also free oldobj. */
        free(old);
    }
}


#define __GNUC__  // "re-unallow" malloc
