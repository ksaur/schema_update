//gcc -g redisfs_v0v6_nonlazy.c -o compress -lhiredis -lz
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <zlib.h>
#include <time.h>
#include <hiredis/hiredis.h>

void upd_fun_add_compression(redisContext * c, char * key, void * value, size_t val_len){

    char callstr[256];
    char inode_info[256];
    char * split = strrchr(key, ':');
    redisReply *reply;

    /* This update is only for the DATA member of the INODE namespace
     * (skx:INODE:inode:DATA), where 'inode' is the inode number.
     * Return if not the ":DATA" member. */
    if((split == NULL) || (strncmp(":DATA", split, 5) != 0))
        return;

    ///printf("About to update: [%s],[%d]\n", *key, *val_len);

    /* The next several lines from redisfs.c v.7 (ln 848)*/
    int c_size = val_len;
    if ( val_len <= 16384 )
      c_size = 1024 * 16;
    else
      c_size = ( val_len * 2) + 1;

    char *compressed = malloc(c_size );
    uLongf compressed_len = c_size;
    int ret = compress2((void *)compressed, &compressed_len, value, val_len,
                  Z_BEST_SPEED);
    if (ret != Z_OK)
    {
        fprintf(stderr, "UPDATER: compress2() failed - aborting write for %s\n", key);
        free(compressed);
    }

    /* Now set the modification time.  We don't need to set size, since the
     * size of the decompressed data didn't change. (See
     * redisfs.7/src/redisfs.c:909 for orig...they set 'size' not 'compressed_len'.)
     * Grab the prefix by substracting from the split point.(ex: "skx:INODE:inode")*/
    snprintf(inode_info, (split-key)+1, "%s\0", key);
    sprintf(callstr, "%s:MTIME", inode_info);
    reply = redisCommand(c,"set %s %d", callstr, (int)time(NULL));
    free(reply);
    /* Set the new value and length (don't touch key),
     * to be stored in redis by kvolve */
    reply = redisCommand(c,"set %s %b", key, compressed, compressed_len);
    free(reply);
}

int main(int argc, char* argv[]){

   redisReply *reply;
   redisReply *reply2;
   redisReply *reply3;
   int i;

   redisContext * c = redisConnect("127.0.0.1", 6379);
   reply = redisCommand(c,"keys %s", "*DATA*");
   for (i =0; i < reply->elements; i++){
     redisReply * curr = reply->element[i];
     reply2 = redisCommand(c,"get %s", curr->str);
     char * split = strrchr(curr->str, ':');
     char * newname = malloc(strlen(curr->str));
     strcpy(newname, curr->str);
     size_t len = split - curr->str + 1;
     strcpy(newname+len,"SIZE");
     reply3 = redisCommand(c, "GET %s", newname);
     size_t sz = atoi(reply3->str);

     upd_fun_add_compression(c, curr->str, reply2->str, sz);
     freeReplyObject(reply2);
     freeReplyObject(reply3);
   } 
   freeReplyObject(reply);

 

}
