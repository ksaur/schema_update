#include <stdlib.h>
#include <stdio.h>
#include "kvolve_upd.h"


void test_fun_1(char * key, void * value){
    printf("CALLEDDDDDDDDDD\n");

}

struct kvolve_upd_info * get_update_func_list(void){

    struct kvolve_upd_info * info = malloc(sizeof(struct kvolve_upd_info));
    info->from_ns = "order";
    info->to_ns = "order";
    info->from_vers = "v0";
    info->to_vers = "v1";
    info->num_funs = 1;
    info->funs = calloc(info->num_funs, sizeof(kvolve_update_kv_fun));
    info->funs[0] = test_fun_1;
    return info;
}

int main(void){
   get_update_func_list();
   return 0;
}

