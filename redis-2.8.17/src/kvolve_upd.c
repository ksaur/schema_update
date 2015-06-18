#include <signal.h> // For redis.h 'siginfo_t'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <assert.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <dlfcn.h>
#undef __GNUC__  // allow malloc (needed for uthash)  (see redis.h ln 1403)
#include "kvolve_internal.h"
#include "kvolve.h"
#include "redis.h"
#include "kvolve_upd.h"

extern int processInlineBuffer(redisClient *c);

/* This API function allows the update-writer to call into redis from the
 * update function (mu). */
void kvolve_upd_redis_call(char* userinput){
    redisClient * c_fake = createClient(-1);
    size_t buff = strlen(userinput)+3;
    char * q = malloc(buff);
    /* add redis protocol fun */
    sprintf(q,"%s\r\n",userinput);
    c_fake->querybuf = sdsnew(q);
    /* parse the user input string */
    processInlineBuffer(c_fake);
    /* lookup the newly parsed command */
    c_fake->cmd = lookupCommandOrOriginal(c_fake->argv[0]->ptr);
    /* run through kvolve (set vers, and set flag to not run updates on this
     * value, else infinite loop!), then call properly*/
    kvolve_process_command(c_fake);
    call(c_fake, 0);
    /* teardown */
    freeClient(c_fake);
    free(q);
}


#define __GNUC__  // "re-unallow" malloc
