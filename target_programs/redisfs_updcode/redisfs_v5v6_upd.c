#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "kvolve_upd.h"


void dir_ns_change(char ** key, void ** value){
    /* The new-version code will already query with the correct string,
       if we've reached this part of the update in the new namespace.
       Just preserve the string and return it */
    size_t s = strlen((char*)*value)+1;
    char * save = malloc(s);
    strcpy(save, *key);
    *key = save;
}
void add_compression(char ** key, void ** value){
   //TODO
}

struct kvolve_upd_info * get_update_func_list(void){

    struct kvolve_upd_info * head = malloc(sizeof(struct kvolve_upd_info));
    struct kvolve_upd_info * info2 = malloc(sizeof(struct kvolve_upd_info));

    /* Change the namespace from skx to skx:DIR */
    head->from_ns = "skx";
    head->to_ns = "skx:DIR";
    head->from_vers = "v5";
    head->to_vers = "v6";
    head->num_funs = 1;
    head->funs = calloc(head->num_funs, sizeof(kvolve_update_kv_fun));
    head->funs[0] = dir_ns_change;
    head->next = info2;

    /* Add compression to DATA members of the INODE namespace */
    info2->from_ns = "skx:INODE";
    info2->to_ns = "skx:INODE";
    info2->from_vers = "v5";
    info2->to_vers = "v6";
    info2->num_funs = 1;
    info2->funs = calloc(info2->num_funs, sizeof(kvolve_update_kv_fun));
    info2->funs[0] = add_compression;
    info2->next = NULL;

    return head;
}

