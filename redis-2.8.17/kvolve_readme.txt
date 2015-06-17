Changes made to original redis source code  (5 lines of code):

networking.c  (3 changes)
< #include "kvolve.h"
<             if (kvolve_process_command(c))
<                 return;

redis.h  (1 change)
<    char *vers;

object.c (1 change)
<     o->vers = NULL;
