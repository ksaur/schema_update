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
void test_update_separate(void){

  redisReply *reply;

  system("../../redis-2.8.17/src/redis-server ../../redis-2.8.17/redis.conf &");
  sleep(2);
  printf("Inside test_update_separate\n");

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
       "update/home/ksaur/AY1415/schema_update/tests/updates/test_upd_no_ns_change.so");
  check(4, reply, "OK");

  printf("done loading update\n");
  reply = redisCommand(c,"GET %s", "order:111");
  check(5, reply, "ffffUPDATED");
  reply = redisCommand(c,"GET %s", "user:bbbb");
  check(6, reply, "9999");

  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test_upd_with_ns_change.so");
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
void test_update_consecu(void){
  redisReply *reply;
  system("../../redis-2.8.17/src/redis-server ../../redis-2.8.17/redis.conf &");
  sleep(2);

  redisContext * c = redisConnect("127.0.0.1", 6379);
  reply = redisCommand(c, "client setname %s", "order@v0,user@u0");
  check(101, reply, "OK");

  reply = redisCommand(c,"SET %s %s", "order:111", "ffff");
  check(102, reply, "OK");

  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test_upd_no_ns_change.so");
  check(103, reply, "OK");
  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test_upd_with_ns_change.so");
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
       "update/home/ksaur/AY1415/schema_update/tests/updates/test_upd_with_ns_change.so");
  check(203, reply, "OK");

  reply = redisCommand(c,"SET %s %s %s", "foo:order:111", "gggg", "nx");
  assert(reply->type == REDIS_REPLY_NIL);

  // Make sure that the name got changed
  reply = redisCommand(c,"GET %s", "order:111");
  assert(reply->type == REDIS_REPLY_NIL);
  freeReplyObject(reply);

  // Make sure that the VALUE did NOT get changed (should be ffff not gggg).
  reply = redisCommand(c,"GET %s", "foo:order:111");
  check(204, reply, "ffff");

  // Make sure it still works without ns change
  reply = redisCommand(c,"SET %s %s %s", "foo:order:111", "pppp", "nx");
  assert(reply->type == REDIS_REPLY_NIL);

  reply = redisCommand(c,"GET %s", "foo:order:111");
  check(205, reply, "ffff");

  reply = redisCommand(c,"keys %s", "*");
  assert(reply->elements == 1);
  freeReplyObject(reply);

  printf("Redis shutdown:\n");
  system("killall redis-server");
  sleep(2);
}
/* Redis allows "setnx" as an actual (to-be-deprecated) command or "set ... nx" as flags
   http://redis.io/commands/set
   http://redis.io/commands/setnx */
void test_setnx(void){
  redisReply *reply;
  system("../../redis-2.8.17/src/redis-server ../../redis-2.8.17/redis.conf &");
  sleep(2);

  redisContext * c = redisConnect("127.0.0.1", 6379);
  reply = redisCommand(c, "client setname %s", "order@v1");
  check(301, reply, "OK");

  reply = redisCommand(c,"SET %s %s", "order:111", "ffff");
  check(302, reply, "OK");

  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test_upd_with_ns_change.so");
  check(303, reply, "OK");

  reply = redisCommand(c,"SETNX %s %s", "foo:order:111", "gggg");
  assert(reply->type == REDIS_REPLY_INTEGER);
  assert(reply->integer == 0);

  // Make sure that the name got changed
  reply = redisCommand(c,"GET %s", "order:111");
  assert(reply->type == REDIS_REPLY_NIL);
  freeReplyObject(reply);

  // Make sure that the VALUE did NOT get changed (should be ffff not gggg).
  reply = redisCommand(c,"GET %s", "foo:order:111");
  check(304, reply, "ffff");

  // Make sure it still works without ns change
  reply = redisCommand(c,"SETNX %s %s", "foo:order:111", "pppp");
  assert(reply->type == REDIS_REPLY_INTEGER);
  assert(reply->integer == 0);

  reply = redisCommand(c,"GET %s", "foo:order:111");
  check(305, reply, "ffff");

  reply = redisCommand(c,"keys %s", "*");
  assert(reply->elements == 1);
  freeReplyObject(reply);

  printf("Redis shutdown:\n");
  system("killall redis-server");
  sleep(2);
}
void test_xx(void){
  redisReply *reply;
  system("../../redis-2.8.17/src/redis-server ../../redis-2.8.17/redis.conf &");
  sleep(2);

  redisContext * c = redisConnect("127.0.0.1", 6379);
  reply = redisCommand(c, "client setname %s", "order@v1");
  check(206, reply, "OK");

  reply = redisCommand(c,"SET %s %s", "order:111", "ffff");
  check(207, reply, "OK");

  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test_upd_with_ns_change.so");
  check(208, reply, "OK");

  reply = redisCommand(c,"SET %s %s %s", "foo:order:111", "gggg", "xx");
  check(209, reply, "OK");

  // Make sure that the name got changed
  reply = redisCommand(c,"GET %s", "order:111");
  assert(reply->type == REDIS_REPLY_NIL);
  freeReplyObject(reply);

  // Make sure that the value DID get changed 
  reply = redisCommand(c,"GET %s", "foo:order:111");
  check(210, reply, "gggg");

  // Make sure it still works without ns change
  reply = redisCommand(c,"SET %s %s %s", "foo:order:111", "pppp", "xx");
  check(211, reply, "OK");

  reply = redisCommand(c,"GET %s", "foo:order:111");
  check(212, reply, "pppp");

  reply = redisCommand(c,"keys %s", "*");
  assert(reply->elements == 1);
  freeReplyObject(reply);

  printf("Redis shutdown:\n");
  system("killall redis-server");
  sleep(2);
}

void test_mset(void){
  redisReply *reply;
  system("../../redis-2.8.17/src/redis-server ../../redis-2.8.17/redis.conf &");
  sleep(2);

  redisContext * c = redisConnect("127.0.0.1", 6379);
  reply = redisCommand(c, "client setname %s", "order@v1");
  check(301, reply, "OK");

  reply = redisCommand(c,"MSET %s %s %s %s", "order:111", "ffff", "order:222", "wwww");
  check(302, reply, "OK");

  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test_upd_with_ns_change.so");
  check(303, reply, "OK");

  reply = redisCommand(c,"GET %s", "foo:order:111");
  check(304, reply, "ffff");
  reply = redisCommand(c,"GET %s", "foo:order:222");
  check(305, reply, "wwww");

  // Make sure that the old got deleted
  reply = redisCommand(c,"GET %s", "order:111");
  assert(reply->type == REDIS_REPLY_NIL);
  freeReplyObject(reply);
  reply = redisCommand(c,"GET %s", "order:222");
  assert(reply->type == REDIS_REPLY_NIL);
  freeReplyObject(reply);
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
  //test_update_separate();
  //test_update_consecu();
  //test_nx();
  //test_xx();
  //test_setnx();
  test_mset();
  printf("All pass.\n");
  return 0;
}
