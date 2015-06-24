Changes made to original redis source code  (7 lines of code):

4 lines of code to implement the version tag:

networking.c  (2 changes)
< #include "kvolve.h"
<             kvolve_process_command(c);

redis.h  (1 change)
<    int vers;

object.c (1 change)
<     o->vers = -1;



3 lines of code so it can be stored to the database:
rdb.c:
int vers;
if ((vers = rdbLoadType(&rdb)) == -1) goto eoferr;
val->vers = vers;
