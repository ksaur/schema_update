#ifndef _KVOLVE_H
#define _KVOLVE_H
#include <bits/siginfo.h> // For redis.h 'siginfo_t' TODO why will this not work with signal.h??
#include "uthash.h"
#include "redis.h"
#include "kvolve_upd.h"
#include "kvolve_internal.h"


int kvolve_process_command(redisClient *c);
void kvolve_set(redisClient * c);
void kvolve_get(redisClient * c);
void kvolve_setnx(redisClient * c, struct version_hash * v);
void kvolve_setxx(redisClient * c, struct version_hash * v);

#endif
