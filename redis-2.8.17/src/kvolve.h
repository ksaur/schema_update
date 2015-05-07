#ifndef _KVOLVE_H
#define _KVOLVE_H
#include <bits/siginfo.h> // For redis.h 'siginfo_t' TODO why will this not work with signal.h??
#include "redis.h"


#define DEBUG
#ifdef DEBUG
# define DEBUG_PRINT(x) printf x
#else
# define DEBUG_PRINT(x) do {} while (0)
#endif

int kvolve_process_command(redisClient *c);
int kvolve_append_version(char * vers_str);
//int kvolve_set(char * buf, char * outbuf, int from, redisContext * c);
//int kvolve_get(char * buf, char * outbuf, int from, redisContext * c);

#endif
