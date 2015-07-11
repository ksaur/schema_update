#ifndef _KVOLVE_H
#define _KVOLVE_H


#define DEBUG
#ifdef DEBUG
# define DEBUG_PRINT(x) printf x
#else
# define DEBUG_PRINT(x) do {} while (0)
#endif

int kvolve_set(char * buf, char * outbuf, int from, redisContext * c);
int kvolve_get(char * buf, char * outbuf, int from, redisContext * c);

#endif
