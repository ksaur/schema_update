
#include <hiredis/hiredis.h>
#include "kvolve.h"
#include <string.h>

void kvolve_set(char * buf){

  char *saveptr;
  char *cmd = strtok_r(buf, " ", &saveptr); //GET
  char *orig_key = strtok_r(NULL, " ", &saveptr); //key
  char *orig_val = strtok(strtok_r(NULL, " ", &saveptr), "\r"); //value
  char *flags = strtok(strtok_r(NULL, " ", &saveptr), "\r"); //flags

  printf("cmd = %s\n", cmd);
  printf("orig_key = %s\n", orig_key);
  printf("orig_val = %s\n", orig_val);
  printf("flags = %s\n", flags);
}


void kvolve_get(char * buf){


  char *saveptr;
  char *cmd = strtok_r(buf, " ", &saveptr); //GET
  char *orig_key = strtok(strtok_r(NULL, " ", &saveptr), "\r"); //key

  printf("cmd = %s\n", cmd);
  printf("orig_key = %s\n", orig_key);

}

