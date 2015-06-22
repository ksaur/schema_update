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
    double newscore = 23;
    struct zset_scoreval * sv = (struct zset_scoreval*)value;
    size_t s = strlen("UPDATED")+strlen(sv->setelem)+1;
    char * cons = calloc(s,sizeof(char));
    strcat(cons, sv->setelem);
    strcat(cons, "UPDATED");
    sv->setelem = cons;
    sv->score = &newscore;
}

void test_fun_2(char ** key, void ** value, size_t * val_len){
    printf("USER CALLEDDDDDDDDDD\n");
}

void kvolve_declare_update(){
    kvolve_upd_spec("order", "order", 5, 6, 2, test_fun_1, test_fun_2_updval);
    kvolve_upd_spec("user", "user", 5, 6, 1, test_fun_2);
}

