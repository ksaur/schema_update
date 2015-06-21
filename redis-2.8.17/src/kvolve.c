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
#include <ctype.h>
#undef __GNUC__  // allow malloc (needed for uthash)  (see redis.h ln 1403)
#include "uthash.h"
#include "kvolve.h"
#include "redis.h"
#include "kvolve_upd.h"
#include "kvolve_internal.h"

struct kvolve_cmd_hash_populate kvolveCommandTable[] = {
    {"set",kvolve_set,3},
    {"mset",kvolve_mset,3},
    {"get",kvolve_get,2},
    {"mget",kvolve_mget,2},
    {"getset",kvolve_getset,3},
    {"getrange",kvolve_getrange,4},
    {"incr",kvolve_incr,2},
    {"incrby",kvolve_incrby,3},
    {"del",kvolve_del,2},
    {"setnx",kvolve_setnx,3},
    {"sadd",kvolve_sadd,3},
    {"scard",kvolve_scard,3},
    {"spop",kvolve_spop,2},
    {"smembers",kvolve_smembers,2},
    {"sismember",kvolve_sismember,3},
    {"srem",kvolve_srem,3},
    {"zadd",kvolve_zadd,4},
    {"zcard",kvolve_zcard,2},
    {"zscore",kvolve_zscore,3},
    {"zrem",kvolve_zrem,3},
    {"zrange",kvolve_zrange,4}
};
struct kvolve_cmd_hash * kvolve_commands = NULL;

void kvolve_process_command(redisClient *c){

    kvolve_prevcall_check();

    if (c->argc == 3 && (strcasecmp((char*)c->argv[0]->ptr, "client") == 0)
            && (strcasecmp((char*)c->argv[1]->ptr, "setname") == 0)
            && (strncasecmp((char*)c->argv[2]->ptr, "update", 6) == 0)){
        kvolve_load_update((char*)(c->argv[2]->ptr)+6);
    } else if (c->argc == 3 && (strcasecmp((char*)c->argv[0]->ptr, "client") == 0) && 
            (strcasecmp((char*)c->argv[1]->ptr, "setname") == 0)){
        kvolve_check_version((char*)c->argv[2]->ptr);
    } else if(c->argc > 1) {
        struct version_hash * v = kvolve_version_hash_lookup((char*)c->argv[1]->ptr);
        kvolve_call fun = kvolve_lookup_kv_command(c);
        if(!fun){
            DEBUG_PRINT(("Function %s not implemented\n", (char*)c->argv[0]->ptr));
            return;
        }
        fun(c, v);
    }
}

/* NX -- Only set the key if it does not already exist*/
void kvolve_setnx(redisClient * c, struct version_hash * v){

    /* Do nothing if already at current namespace, do nothing*/
    if (lookupKeyRead(c->db, c->argv[1]))
        return;

    robj * present = kvolve_get_db_val(c, v);
    DEBUG_PRINT(("Present is = %p\n", (void*)present));
    /* If doesn't exist anywhere, do nothing */
    if (present == NULL)
        return;

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

void kvolve_mset(redisClient * c, struct version_hash * v){
    int i;
    redisClient * c_fake = createClient(-1);
    c_fake->db = c->db;
    c_fake->argc = 3;
    c_fake->argv = zmalloc(sizeof(void*)*3);

    assert(c->argc % 2 == 1);
    for (i=1; i < c->argc; i=i+2){
        c_fake->argv[1]= c->argv[i];
        c_fake->argv[2]= c->argv[i+1];
        kvolve_set(c_fake, v);
    }
    zfree(c_fake->argv);
    zfree(c_fake);
}

/* We only have to worry about namespace changes here. We need to do the rename
 * so it will be deleted properly (and return the right value count*/

void kvolve_del(redisClient * c, struct version_hash * v){
    kvolve_check_rename(c, v, c->argc);
}

/* check for update, the same as kvolve_get, but a substring */
void kvolve_getrange(redisClient *c, struct version_hash * v){
    kvolve_get(c, v);
}

/* will just check for update, and do if necessary. Remember, we must keep all
 * set elements at same version. this will do that.*/
void kvolve_sismember(redisClient * c, struct version_hash * v){
    kvolve_smembers(c, v);
}
void kvolve_srem(redisClient * c, struct version_hash * v){
    kvolve_smembers(c, v);
}
void kvolve_scard(redisClient * c, struct version_hash * v){
    kvolve_smembers(c, v);
}
void kvolve_spop(redisClient * c, struct version_hash * v){
    kvolve_smembers(c, v);
}
void kvolve_incrby(redisClient * c, struct version_hash * v){
    kvolve_incr(c, v);
}
void kvolve_getset(redisClient * c, struct version_hash * v){
    kvolve_get(c, v);
}
void kvolve_zcard(redisClient * c, struct version_hash * v){
    kvolve_update_all_zset(c, v);
}
void kvolve_zrem(redisClient * c, struct version_hash * v){
    kvolve_zcard(c, v);
}
void kvolve_zscore(redisClient * c, struct version_hash * v){
    kvolve_zcard(c, v);
}
void kvolve_zrange(redisClient * c, struct version_hash * v){
    kvolve_zcard(c, v);
}

/* the incr command blows away any version you pass it, because it creates its
 * own object.  Since incr values can ONLY be strings that convert to ints,
 * there is no way that there can be a meaninful value change.  Therefore, we
 * just need to make sure the name is current and go from there. */
void kvolve_incr(redisClient * c, struct version_hash * v){

    if(!v || !v->prev_ns) return;

    /* check if current at correct ns, or doesn't exist at all*/
    if(lookupKeyRead(c->db, c->argv[1]) || (kvolve_get_db_val(c, v)==NULL))
        return;

    /* at this point, we must update the namespace */
    kvolve_namespace_update(c, v);

}

void kvolve_mget(redisClient * c, struct version_hash * v){
    int i;
    redisClient * c_fake = createClient(-1);
    c_fake->db = c->db;
    c_fake->argc = 2;
    c_fake->argv = zmalloc(sizeof(void*)*2);

    for (i=1; i < c->argc; i++){
        c_fake->argv[1]= c->argv[i];
        kvolve_get(c_fake, v);
    }
    zfree(c_fake->argv);
    zfree(c_fake);
}

void kvolve_set(redisClient * c, struct version_hash * v){

    int flags;
    robj * oldobj = NULL;

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
    if(v->prev_ns != NULL){
        oldobj = kvolve_exists_old(c, v);
        if(oldobj){
            dbDelete(c->db,oldobj);
            zfree(oldobj);
        }
    }
}

void kvolve_get(redisClient * c, struct version_hash * v){
    kvolve_check_update_kv_pair(c, v, 1, NULL, REDIS_STRING, NULL);
}

void kvolve_smembers(redisClient * c, struct version_hash * v){

    int first = 1;
    if(v == NULL) 
        return;
    robj * o = kvolve_get_db_val(c, v);
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
        kvolve_check_update_kv_pair(c, v, first, e, REDIS_SET, NULL);
        e = setTypeNextObject(si);
        first = 0;
    }

    /* Update the version string in the set container to match the update we
     * just did on the set members .*/
    o->vers = v->versions[v->num_versions-1];
    zfree(c_fake->argv);
    zfree(c_fake);
}

void kvolve_sadd(redisClient * c, struct version_hash * v){
    robj * oldobj = NULL;
    int i;
    if(v == NULL) return;

    /* Check if the set exists or if we're creating a new set.  If we're
     * creating a new set, redis will create it during the call.  (We can't create
     * it ahead of time because redis doesn't allow empty sets. And we can't add
     * the element because it will throw off the return response.)  Therefore,
     * notify networking.c to patchup the set version after the call where the set
     * is created. */
    robj * o = kvolve_get_db_val(c, v);
    if (o == NULL) {
        kvolve_new_version(c, v);
        return;
    }

    /* make sure all set elements are at this current version and update them
     * all if necessary.  Don't let different members of the same set be at different
     * versions!! (would be a confusing mess.) This will check and return if current,
     * else update other set members to the current version */
    if (strcmp(o->vers, v->versions[v->num_versions-1])!=0)
        kvolve_smembers(c ,v);

    /* Set the version for the new element(s) that is not yet a member */
    for(i=2; i < c->argc; i++)
        c->argv[i]->vers = v->versions[v->num_versions-1];
        
    if((v->prev_ns != NULL) && (strcmp(o->vers, v->versions[v->num_versions-1])==0)){
        oldobj = kvolve_exists_old(c, v);
        if(oldobj){
            dbDelete(c->db,oldobj);
            zfree(oldobj);
        }
    }
}

void kvolve_zadd(redisClient * c, struct version_hash * v){
    robj * oldobj = NULL;
    if(v == NULL) return;

    /* Check if the zset exists or if we're creating a new set.*/
    robj * o = kvolve_get_db_val(c, v);
    if (o == NULL) {
        kvolve_new_version(c, v);
        return;
    }

    /* make sure all set elements are at this current version. Else update all*/
    kvolve_update_all_zset(c, v);

    if((v->prev_ns != NULL) && (strcmp(o->vers, v->versions[v->num_versions-1])==0)){
        oldobj = kvolve_exists_old(c, v);
        if(oldobj){
            dbDelete(c->db,oldobj);
            zfree(oldobj);
        }
    }
}

void kvolve_populateCommandTable(void){
    int j, i;
    char * ucase;
    int numcommands = sizeof(kvolveCommandTable)/sizeof(struct kvolve_cmd_hash_populate);

    for (j = 0; j < numcommands; j++) {
        struct kvolve_cmd_hash_populate *c = kvolveCommandTable+j;
        struct kvolve_cmd_hash * c_h = malloc(sizeof(struct kvolve_cmd_hash));
        struct kvolve_cmd_hash * c_hU = malloc(sizeof(struct kvolve_cmd_hash));
        c_h->cmd = c->cmd;
        c_h->call = c->call;
        c_h->min_args = c->min_args;
        HASH_ADD_KEYPTR(hh, kvolve_commands, c_h->cmd, strlen(c_h->cmd), c_h);
        /* also add upper case */
        ucase = calloc(strlen(c->cmd), sizeof(char));
        c_hU->call = c->call;
        c_hU->min_args = c->min_args;
        for(i = 0; c->cmd[i]; i++){
            ucase[i] = toupper(c->cmd[i]);
        }
        c_hU->cmd = ucase;
        HASH_ADD_KEYPTR(hh, kvolve_commands, c_hU->cmd, strlen(c_hU->cmd), c_hU);
    }
}

kvolve_call kvolve_lookup_kv_command(redisClient * c){

    struct kvolve_cmd_hash * c_h = NULL;
    char * lookup = (char*)c->argv[0]->ptr;
    if(!kvolve_commands)
        kvolve_populateCommandTable();
    HASH_FIND(hh, kvolve_commands, lookup, strlen(lookup), c_h);
    
    if(!c_h || (c->argc < c_h->min_args))
        return NULL;
    return c_h->call;
}

#define __GNUC__  // "re-unallow" malloc
