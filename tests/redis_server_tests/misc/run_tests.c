#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <hiredis/hiredis.h>

#define DEBUG


void check(int test_num, redisReply *reply, char * expected){
#ifdef DEBUG
  printf("(%d) Expected: %s, Got: %s\n", test_num, expected, reply->str);
#endif
  assert(strncmp(reply->str, expected, strlen(expected))==0);
  freeReplyObject(reply);
}

void check_int(int test_num, redisReply *reply, int expected){
#ifdef DEBUG
  printf("(%d) Expected: %d, Got: %lld\n", test_num, expected, reply->integer);
#endif
  assert(reply->integer == expected);
  freeReplyObject(reply);
}


const char * server_loc = "../../../redis-2.8.17/src/redis-server ../../../redis-2.8.17/redis.conf &";
const char * user_call = "update/home/ksaur/AY1415/schema_update/tests/redis_server_tests/misc/user_call.so";



void test_client_call(void){
  redisReply *reply;
  system(server_loc);
  sleep(2);

  redisContext * c = redisConnect("127.0.0.1", 6379);
  reply = redisCommand(c, "client setname %s", "order@v0");
  check(1, reply, "OK");

  reply = redisCommand(c, "SET %s  %s", "order:111", "oooo");
  check(2, reply, "OK");

  reply = redisCommand(c,"keys %s", "*");
  assert(reply->elements == 1);
  freeReplyObject(reply);

  reply = redisCommand(c,"client setname %s", user_call);
  check(3, reply, "OK");

  /* This get should trigger the creation of the other key */
  reply = redisCommand(c, "GET %s", "order:111");
  check(4, reply, "oooo");

  reply = redisCommand(c, "GET %s", "order:222");
  check(5, reply, "wwwww");

  reply = redisCommand(c,"keys %s", "*");
  assert(reply->elements == 2);
  freeReplyObject(reply);

  printf("Redis shutdown:\n");
  system("killall redis-server");
  sleep(2);
}


int main(void){

  system("killall redis-server");
  sleep(2);
  test_client_call();
  printf("All pass.\n");
  return 0;
}
