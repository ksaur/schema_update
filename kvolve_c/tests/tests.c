#include <assert.h>
#include <stdlib.h>
#include "simpleclient.h"


/* test connection and version establishment */
int test1(void){

  struct ns_vers_args * single = malloc(sizeof(struct ns_vers_args));
  single->ns = "order";
  single->vers = "v0";
  single->next = NULL;
  
  connect("127.0.0.1", 6379, single);
  return 1;
}

int main(void){

  test1();
  return 0;
}
