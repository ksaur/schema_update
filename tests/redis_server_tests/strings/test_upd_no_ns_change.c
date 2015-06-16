#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "kvolve_upd.h"

/* test updating multiple namespaces */
/* test with multiple functions */
/* test with value change */

void test_fun_1(char ** key, void ** value){
    printf("ORDER CALLEDDDDDDDDDD\n");
}

void test_fun_2_updval(char ** key, void ** value){
    size_t s = strlen("UPDATED")+strlen((char*)*value)+1;
    char * cons = calloc(s,sizeof(char));
    strcat(cons, *value);
    strcat(cons, "UPDATED");
    *value = cons;
}

void test_fun_2(char ** key, void ** value){
    printf("USER CALLEDDDDDDDDDD\n");
}


struct kvolve_upd_info * get_update_func_list(void){

    struct kvolve_upd_info * info = malloc(sizeof(struct kvolve_upd_info));
    struct kvolve_upd_info * info2 = malloc(sizeof(struct kvolve_upd_info));
    info->from_ns = "order";
    info->to_ns = "order";
    info->from_vers = "v0";
    info->to_vers = "v1";
    info->num_funs = 2;
    info->funs = calloc(info->num_funs, sizeof(kvolve_update_kv_fun));
    info->funs[0] = test_fun_1;
    info->funs[1] = test_fun_2_updval;
    info->next = info2;

    info2->from_ns = "user";
    info2->to_ns = "user";
    info2->from_vers = "u0";
    info2->to_vers = "u1";
    info2->num_funs = 1;
    info2->funs = calloc(info->num_funs, sizeof(kvolve_update_kv_fun));
    info2->funs[0] = test_fun_2;
    info2->next = NULL;
    return info;
}

int main(void){
   get_update_func_list();
   return 0;
}

