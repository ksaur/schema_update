#ifndef _KVOLVE_H
#define _KVOLVE_H


#define DEBUG
#ifdef DEBUG
# define DEBUG_PRINT(x) printf x
#else
# define DEBUG_PRINT(x) do {} while (0)
#endif

void kvolve_set(char * buf);
void kvolve_get(char * buf);

#endif
