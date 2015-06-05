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




/* Test updating with two namespaces.  Perform the updates on the two
 * keys.  Then load the 2nd udpate (namespace change), and perform the 
 * update.  Assert that the key at the old ns was deleted. */
void test_1_and_2_separate(void){

  redisReply *reply;

  system("../../redis-2.8.17/src/redis-server ../../redis-2.8.17/redis.conf &");
  sleep(2);
  printf("Inside test_1_and_2_separate\n");

  redisContext * c = redisConnect("127.0.0.1", 6379);
  reply = redisCommand(c, "client setname %s", "order@v0,user@u0");
  check(1, reply, "OK");

  reply = redisCommand(c,"SET %s %s", "order:111", "ffff");
  check(2, reply, "OK");
  reply = redisCommand(c,"SET %s %s", "order:222", "ffff");
  check(2, reply, "OK");
  reply = redisCommand(c,"SET %s %s", "user:bbbb", "9999");
  check(3, reply, "OK");

  printf("about to load update\n");
  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test1.so");
  check(4, reply, "OK");

  printf("done loading update\n");
  reply = redisCommand(c,"GET %s", "order:111");
  check(5, reply, "ffffUPDATED");
  reply = redisCommand(c,"GET %s", "user:bbbb");
  check(6, reply, "9999");

  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test2.so");
  check(7, reply, "OK");
  reply = redisCommand(c,"GET %s", "foo:order:111");
  check(8, reply, "ffffUPDATED");

  reply = redisCommand(c,"GET %s", "order:111");
  assert(reply->type == REDIS_REPLY_NIL);
  freeReplyObject(reply);

  /* test that old version is clobbered by set in ns change*/
  reply = redisCommand(c,"SET %s %s", "foo:order:222", "eeee");
  check(9, reply, "OK");

  reply = redisCommand(c,"keys %s", "*");
  assert(reply->elements == 3);
  freeReplyObject(reply);
   
  system("killall redis-server");
  sleep(2);
 
}


/* The same test as before, except test running the updates one after the
 * other.*/
void test_1_and_2_together(void){
  redisReply *reply;
  system("../../redis-2.8.17/src/redis-server ../../redis-2.8.17/redis.conf &");
  sleep(2);

  redisContext * c = redisConnect("127.0.0.1", 6379);
  reply = redisCommand(c, "client setname %s", "order@v0,user@u0");
  check(101, reply, "OK");

  reply = redisCommand(c,"SET %s %s", "order:111", "ffff");
  check(102, reply, "OK");

  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test1.so");
  check(103, reply, "OK");
  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test2.so");
  check(104, reply, "OK");

  reply = redisCommand(c,"GET %s", "foo:order:111");
  check(105, reply, "ffffUPDATED");

  reply = redisCommand(c,"GET %s", "order:111");
  assert(reply->type == REDIS_REPLY_NIL);
  freeReplyObject(reply);

  reply = redisCommand(c,"keys %s", "*");
  assert(reply->elements == 1);
  freeReplyObject(reply);

  system("killall redis-server");
  sleep(2);
}

void test_nx(void){
  redisReply *reply;
  system("../../redis-2.8.17/src/redis-server ../../redis-2.8.17/redis.conf &");
  sleep(2);

  redisContext * c = redisConnect("127.0.0.1", 6379);
  reply = redisCommand(c, "client setname %s", "order@v1");
  check(201, reply, "OK");

  reply = redisCommand(c,"SET %s %s", "order:111", "ffff");
  check(202, reply, "OK");

  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test2.so");
  check(203, reply, "OK");

  reply = redisCommand(c,"SET %s %s %s", "foo:order:111", "ffff", "nx");
  check(204, reply, "OK");

  system("killall redis-server");
  sleep(2);
}

int main(void){

  system("killall redis-server");
  sleep(2);
  //test_1_and_2_separate();
  //test_1_and_2_together();
  test_nx();
  printf("All pass.\n");
  return 0;
}
