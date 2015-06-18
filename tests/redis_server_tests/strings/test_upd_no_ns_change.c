#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "kvolve_upd.h"

/* test updating multiple namespaces */
/* test with multiple functions */
/* test with value change */

void test_fun_1(char ** key, void ** value, size_t * val_len){
    printf("ORDER CALLEDDDDDDDDDD\n");
}

void test_fun_2_updval(char ** key, void ** value, size_t * val_len){
    size_t s = strlen("UPDATED")+strlen((char*)*value)+1;
    char * cons = calloc(s,sizeof(char));
    strcat(cons, *value);
    strcat(cons, "UPDATED");
    *value = cons;
    *val_len = s;
}

void test_fun_2(char ** key, void ** value, size_t * val_len){
    printf("USER CALLEDDDDDDDDDD\n");
}

void kvolve_declare_update(){
    kvolve_upd_spec("order", "order", "v0", "v1", 2, test_fun_1, test_fun_2_updval);
    kvolve_upd_spec("user", "user", "u0", "u0", 1, test_fun_2);
}

