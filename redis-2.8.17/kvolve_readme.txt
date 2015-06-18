Changes made to original redis source code  (4 lines of code):

networking.c  (2 changes)
< #include "kvolve.h"
<             kvolve_process_command(c);

redis.h  (1 change)
<    char *vers;

object.c (1 change)
<     o->vers = NULL;
