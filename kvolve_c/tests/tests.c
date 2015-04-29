#include <assert.h>
#include <stdlib.h>
#include "simpleclient.h"


/* test connection and version establishment */
int test1(void){

  kv_connect("127.0.0.1", 6379, "order@v0");
  //  reply = redisCommand(c,"SET %b %b", "bar", 3, "hello", 5);
  //  printf("SET (binary API): %s\n", reply->str);
  //  freeReplyObject(reply);

  //  /* Try a GET and two INCR */
  //  reply = redisCommand(c,"GET foo");
  //  printf("GET foo: %s\n", reply->str);
  //  freeReplyObject(reply);
  return 1;
}

int main(void){

  test1();
  return 0;
}
