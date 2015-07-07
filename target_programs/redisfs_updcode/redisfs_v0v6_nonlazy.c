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

    ///printf("About to update: [%s],[%d]\n", *key, *val_len);

    /* The next several lines from redisfs.c v.7 (ln 848)*/
    int c_size = *val_len;
    if ( *val_len <= 16384 )
      c_size = 1024 * 16;
    else
      c_size = ( *val_len * 2) + 1;

    char *compressed = malloc(c_size );
    uLongf compressed_len = c_size;
    int ret = compress2((void *)compressed, &compressed_len, *value, *val_len,
                  Z_BEST_SPEED);
    if (ret != Z_OK)
    {
        fprintf(stderr, "compress2() failed - aborting write for %s\n", *key);
        free(compressed);
    }

    /* Now set the modification time.  We don't need to set size, since the
     * size of the decompressed data didn't change. (See
     * redisfs.7/src/redisfs.c:909 for orig...they set 'size' not 'compressed_len'.)
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
    kvolve_upd_spec("skx", "skx:DIR", 0, 6, 0);
    kvolve_upd_spec("skx:INODE", "skx:INODE", 0, 6, 1, upd_fun_add_compression);
}

