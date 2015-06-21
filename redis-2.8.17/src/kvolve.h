#ifndef _KVOLVE_H
#define _KVOLVE_H
#include <bits/siginfo.h> // For redis.h 'siginfo_t' TODO why will this not work with signal.h??
#include "uthash.h"
#include "redis.h"
#include "kvolve_upd.h"
#include "kvolve_internal.h"


/************* Currently supported Redis commands ************/

/******* Strings ********/
/* supports all flags*/
void kvolve_set(redisClient * c, struct version_hash * v);
/* can also be set w flags, redis marked this as to-be-deprecated */
void kvolve_setnx(redisClient * c, struct version_hash * v);
/* not actually part of the redis API explicitly (usually set w flags) */
void kvolve_setxx(redisClient * c, struct version_hash * v);
void kvolve_mset(redisClient * c, struct version_hash * v);
void kvolve_get(redisClient * c, struct version_hash * v);
void kvolve_mget(redisClient * c, struct version_hash * v);
void kvolve_getset(redisClient * c, struct version_hash * v);
void kvolve_del(redisClient * c, struct version_hash * v);
void kvolve_incr(redisClient * c, struct version_hash * v);
void kvolve_incrby(redisClient * c, struct version_hash * v);
void kvolve_getrange(redisClient * c, struct version_hash * v);

/******* Sets ********/
void kvolve_sadd(redisClient * c, struct version_hash * v);
void kvolve_smembers(redisClient * c, struct version_hash * v);
void kvolve_sismember(redisClient * c, struct version_hash * v);
void kvolve_srem(redisClient * c, struct version_hash * v);
void kvolve_scard(redisClient * c, struct version_hash * v);
void kvolve_spop(redisClient * c, struct version_hash * v);

/******* Sorted Sets (zsets) ********/
void kvolve_zadd(redisClient *c, struct version_hash * v);
void kvolve_zcard(redisClient * c, struct version_hash * v);
void kvolve_zrem(redisClient * c, struct version_hash * v);
void kvolve_zscore(redisClient * c, struct version_hash * v);
void kvolve_zrange(redisClient * c, struct version_hash * v);

/****************************************************************/


/* gateway function, the hook into the kvolve system. */
void kvolve_process_command(redisClient *c);
/* The fptr and structure to lookup kvolve functions */
typedef void (*kvolve_call)(redisClient *c, struct version_hash * v);
struct kvolve_cmd_hash_populate{
    char * cmd; /* key */
    kvolve_call call;
    int min_args;
};
struct kvolve_cmd_hash{ //TODO use redis's dictAdd?
    char * cmd; /* key */
    kvolve_call call;
    int min_args;
    UT_hash_handle hh; /* makes this structure hashable */
};
void kvolve_populateCommandTable(void);
kvolve_call kvolve_lookup_kv_command(redisClient * c);

#endif
