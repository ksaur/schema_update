#ifndef _KVOLVE_H
#define _KVOLVE_H
#include <bits/siginfo.h> // For redis.h 'siginfo_t' TODO why will this not work with signal.h??
#include "uthash.h"
#include "redis.h"
#include "kvolve_upd.h"
#include "kvolve_internal.h"

extern int processInlineBuffer(redisClient *c);


/* gateway function, the hook into the kvolve system. */
void kvolve_process_command(redisClient *c);

/************* Currently supported Redis commands ************/

/******* Strings ********/
/* supports all flags*/
void kvolve_set(redisClient * c);
/* can also be set w flags, redis marked this as to-be-deprecated */
void kvolve_setnx(redisClient * c, struct version_hash * v); 
/* not actually part of the redis API explicitly (usually set w flags) */
void kvolve_setxx(redisClient * c, struct version_hash * v);
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

#endif
