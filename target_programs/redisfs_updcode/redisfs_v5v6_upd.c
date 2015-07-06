#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <zlib.h>
#include <time.h>
#include "kvolve_upd.h"


void upd_fun_add_compression(char ** key, void ** value, size_t * val_len){

    char callstr[256];
    char inode_info[256];
    char * split = strrchr(*key, ':');

    /* This update is only for the DATA member of the INODE namespace
     * (skx:INODE:inode:DATA), where 'inode' is the inode number.
     * Return if not the ":DATA" member. */
    if((split == NULL) || (strncmp(":DATA", split, 5) != 0))
        return;

    /* There's a bug in redisfs for values shorter than 3...this wouldn't normally be here...*/
    if(strlen((char*)*value)<3)
        return;
    //printf("About to update: %s, %s\n", *key, (char*)*value);

    /* The next several lines from redisfs.c v.6 (ln 848)*/
    char *compressed = malloc((*val_len * 2) + 1);
    uLongf compressed_len = ((*val_len * 2) + 1); //uLongf from zlib
    int ret = compress2((void *)compressed, &compressed_len, *value, *val_len,
                  Z_BEST_SPEED);
    if (ret != Z_OK)
    {
        fprintf(stderr, "compress2() failed - aborting write for %s\n", *key);
        free(compressed);
    }

    /* Now set the modification time.  We don't need to set size, since the
     * size of the decompressed data didn't change. (See
     * redisfs.6/src/redisfs.c:878 for orig.)
     * Grab the prefix by substracting from the split point.(ex: "skx:INODE:inode")*/
    snprintf(inode_info, (split-*key)+1, "%s\0", *key);
    sprintf(callstr, "set %s:MTIME %d", inode_info, (int)time(NULL));
    kvolve_upd_redis_call(callstr);

    /* Set the new value and length (don't touch key),
     * to be stored in redis by kvolve */
    *value = compressed;
    *val_len = compressed_len;
}


/* This is the update structure for redisfs.5 to redisfs.6 */
void kvolve_declare_update(){
    kvolve_upd_spec("skx", "skx:DIR", 5, 6, 0);
    kvolve_upd_spec("skx:INODE", "skx:INODE", 5, 6, 1, upd_fun_add_compression);
}

