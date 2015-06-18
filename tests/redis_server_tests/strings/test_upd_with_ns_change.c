#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "kvolve_upd.h"

/* test with key change */

void test_fun_ns_change(char ** key, void ** value, size_t * val_len){
    /* No need to do anything here unless additional mods are necessary.
     * Namespace will update automatically*/
}

struct kvolve_upd_info * get_update_func_list(void){

    struct kvolve_upd_info * info = malloc(sizeof(struct kvolve_upd_info));

    info->from_ns = "order";
    info->to_ns = "foo:order";
    info->from_vers = "v1";
    info->to_vers = "fv2";
    info->num_funs = 1;
    info->funs = calloc(info->num_funs, sizeof(kvolve_update_kv_fun));
    info->funs[0] = test_fun_ns_change;
    info->next = NULL;
    return info;
}

int main(void){
   get_update_func_list();
   return 0;
}

