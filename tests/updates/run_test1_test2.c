#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <hiredis/hiredis.h>


void check(redisReply *reply, char * expected){
  assert(strncmp(reply->str, expected, strlen(expected))==0);
  freeReplyObject(reply);
}


/* Test updating with two namespaces.  Perform the updates on the two
 * keys.  Then load the 2nd udpate (namespace change), and perform the 
 * update.  Assert that the key at the old ns was deleted. */
void test_1_and_2_separate(void){

  redisReply *reply;

  redisContext * c = redisConnect("127.0.0.1", 6379);
  reply = redisCommand(c, "client setname %s", "order@v0,user@u0");
  check(reply, "OK");

  reply = redisCommand(c,"SET %s %s", "order:111", "ffff");
  check(reply, "OK");
  reply = redisCommand(c,"SET %s %s", "user:bbbb", "9999");
  check(reply, "OK");

  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test1.so");
  check(reply, "OK");

  reply = redisCommand(c,"GET %s", "order:111");
  check(reply, "ffffUPDATED");
  reply = redisCommand(c,"GET %s", "user:bbbb");
  check(reply, "9999");

  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test2.so");
  check(reply, "OK");
  reply = redisCommand(c,"GET %s", "foo:order:111");
  check(reply, "ffffUPDATED");

  reply = redisCommand(c,"GET %s", "order:111");
  assert(reply->type == REDIS_REPLY_NIL);
  freeReplyObject(reply);

  reply = redisCommand(c,"keys %s", "*");
  assert(reply->elements == 2);
  freeReplyObject(reply);

}


/* The same test as before, except test running the updates one after the
 * other.*/
void test_1_and_2_together(void){
  redisReply *reply;

  redisContext * c = redisConnect("127.0.0.1", 6379);
  reply = redisCommand(c, "client setname %s", "order@v0,user@u0");
  check(reply, "OK");

  reply = redisCommand(c,"SET %s %s", "order:111", "ffff");
  check(reply, "OK");

  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test1.so");
  check(reply, "OK");
  reply = redisCommand(c,"client setname %s", 
       "update/home/ksaur/AY1415/schema_update/tests/updates/test2.so");
  check(reply, "OK");

  reply = redisCommand(c,"GET %s", "foo:order:111");
  check(reply, "ffffUPDATED");

  reply = redisCommand(c,"GET %s", "order:111");
  assert(reply->type == REDIS_REPLY_NIL);
  freeReplyObject(reply);

  reply = redisCommand(c,"keys %s", "*");
  assert(reply->elements == 1);
  freeReplyObject(reply);

}

int main(void){

  //test_1_and_2_separate();
  test_1_and_2_together();
  printf("All pass.\n");
  return 0;
}
