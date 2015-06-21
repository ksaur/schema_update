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
void kvolve_set(redisClient * c);
/* can also be set w flags, redis marked this as to-be-deprecated */
void kvolve_setnx(redisClient * c); 
/* not actually part of the redis API explicitly (usually set w flags) */
void kvolve_setxx(redisClient * c);
void kvolve_mset(redisClient * c);
void kvolve_get(redisClient * c);
void kvolve_mget(redisClient * c);
void kvolve_getset(redisClient * c);
void kvolve_del(redisClient * c);
void kvolve_incr(redisClient * c);
void kvolve_incrby(redisClient * c);
void kvolve_getrange(redisClient * c);

/******* Sets ********/
void kvolve_sadd(redisClient * c);
void kvolve_smembers(redisClient * c);
void kvolve_sismember(redisClient * c);
void kvolve_srem(redisClient * c);
void kvolve_scard(redisClient * c);
void kvolve_spop(redisClient * c);

/******* Sorted Sets (zsets) ********/
void kvolve_zadd(redisClient *c);
void kvolve_zcard(redisClient * c);
void kvolve_zrem(redisClient * c);
void kvolve_zscore(redisClient * c);
void kvolve_zrange(redisClient * c);

/****************************************************************/


/* gateway function, the hook into the kvolve system. */
void kvolve_process_command(redisClient *c);
/* The fptr and structure to lookup kvolve functions */
typedef void (*kvolve_call)(redisClient *c);
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
