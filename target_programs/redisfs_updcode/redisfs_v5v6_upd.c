#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <zlib.h>
#include "kvolve_upd.h"


//void upd_fun_dir_ns_change(char ** key, void ** value, size_t * val_len){
//  /* Done automatically */
//}

void upd_fun_add_compression(char ** key, void ** value, size_t * val_len){

    char * split = strrchr(*key, ':');

    /* This update is for the DATA member of the INODE namespace
     * (skx:INODE:inode:DATA).  We also need to update (skx:INODE:inode:SIZE) and
     * (skx:INODE:inode:MTIME), but that can only be done along with the DATA
     * update.  Therefore, return if not ":DATA". */
    if((split == NULL) || (strncmp(":DATA", split, 5) != 0))
        return;

    // The next several lines from redisfs.c v.6 (ln 848)
    char *compressed = malloc((*val_len * 2) + 1);
    uLongf compressed_len = ((*val_len * 2) + 1); //uLongf from zlib
    int ret = compress2((void *)compressed, &compressed_len, *value, *val_len,
                  Z_BEST_SPEED);
    if (ret != Z_OK)
    {
        fprintf(stderr, "compress2() failed - aborting write for %s\n", *key);
        free(compressed);
    }
    *value = compressed;
    *val_len = compressed_len;
    

//        reply = redisCommand(_g_redis, "SET %s:INODE:%d:SIZE %d",
//                             _g_prefix, inode, size);
//        freeReplyObject(reply);
//
//        reply = redisCommand(_g_redis, "SET %s:INODE:%d:MTIME %d",
//                             _g_prefix, inode, time(NULL));
//        freeReplyObject(reply);


}

struct kvolve_upd_info * get_update_func_list(void){

    struct kvolve_upd_info * head = malloc(sizeof(struct kvolve_upd_info));
    struct kvolve_upd_info * info2 = malloc(sizeof(struct kvolve_upd_info));

    /* Change the namespace from skx to skx:DIR */
    head->from_ns = "skx";
    head->to_ns = "skx:DIR";
    head->from_vers = "v5";
    head->to_vers = "v6";
    head->num_funs = 0;
    head->funs = NULL;
    head->next = info2;

    /* Add compression to DATA members of the INODE namespace */
    info2->from_ns = "skx:INODE";
    info2->to_ns = "skx:INODE";
    info2->from_vers = "v5";
    info2->to_vers = "v6";
    info2->num_funs = 1;
    info2->funs = calloc(info2->num_funs, sizeof(kvolve_update_kv_fun));
    info2->funs[0] = upd_fun_add_compression;
    info2->next = NULL;

    return head;
}

