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
const char * no_ns_change = "update/home/ksaur/AY1415/schema_update/tests/redis_server_tests/sets/test_upd_no_ns_change.so";
const char * w_ns_change = "update/home/ksaur/AY1415/schema_update/tests/redis_server_tests/sets/test_upd_with_ns_change.so";


void test_sadd_smembers_nschange(void){
  redisReply *reply;
  system(server_loc);
  sleep(2);

  redisContext * c = redisConnect("127.0.0.1", 6379);
  reply = redisCommand(c, "client setname %s", "order@v1");
  check(101, reply, "OK");

  reply = redisCommand(c,"SADD %s %s %s", "order:111", "ffff", "wwww");
  check_int(102, reply, 2);

  reply = redisCommand(c,"SADD %s %s %s", "order:222", "xxxx", "yyyy");
  check_int(103, reply, 2);

  reply = redisCommand(c,"SADD %s %s %s", "order:333", "qqqq", "eeee");
  check_int(104, reply, 2);

  reply = redisCommand(c,"SADD %s %s %s", "order:444", "aaaa", "nnnn");
  check_int(105, reply, 2);

  reply = redisCommand(c,"client setname %s", w_ns_change); 
  check(106, reply, "OK");

  reply = redisCommand(c,"SMEMBERS %s", "foo:order:111");
  assert(strcmp(reply->element[0]->str, "wwww") == 0  || strcmp(reply->element[0]->str, "ffff") == 0 );
  assert(strcmp(reply->element[1]->str, "wwww") == 0  || strcmp(reply->element[1]->str, "ffff") == 0 );
  freeReplyObject(reply);

  reply = redisCommand(c,"SADD %s %s", "foo:order:222", "zzzz");
  check_int(107, reply, 1);

  /* test that modifying any member of the set (above) applies the update to all members */
  reply = redisCommand(c,"SISMEMBER %s %s", "foo:order:222", "xxxx");
  check_int(108, reply, 1);

  /* test that calling sismember triggers an update */
  reply = redisCommand(c,"SISMEMBER %s %s", "foo:order:333", "qqqq");
  check_int(108, reply, 1);

  /* test that calling srem correctly deletes after update*/
  reply = redisCommand(c,"SREM %s %s", "foo:order:444", "aaaa");
  check_int(109, reply, 1);
  reply = redisCommand(c,"SISMEMBER %s %s", "foo:order:444", "aaaa");
  check_int(110, reply, 0);

  printf("Redis shutdown:\n");
  system("killall redis-server");
  sleep(2);
}

void test_sadd_smembers_valchange(void){
  redisReply *reply;
  system(server_loc);
  sleep(2);

  redisContext * c = redisConnect("127.0.0.1", 6379);
  reply = redisCommand(c, "client setname %s", "order@v0,user@u0");
  check(201, reply, "OK");

  reply = redisCommand(c,"SADD %s %s %s", "order:111", "ffff", "wwww");
  check_int(202, reply, 2);

  reply = redisCommand(c,"SADD %s %s %s", "order:222", "xxxx", "yyyy");
  check_int(203, reply, 2);

  reply = redisCommand(c,"SADD %s %s %s", "order:333", "qqqq", "eeee");
  check_int(204, reply, 2);

  reply = redisCommand(c,"SADD %s %s %s", "order:444", "aaaa", "nnnn");
  check_int(205, reply, 2);

  reply = redisCommand(c,"SCARD %s", "order:444");
  check_int(206, reply, 2);

  reply = redisCommand(c,"client setname %s", no_ns_change); 
  check(207, reply, "OK");

  reply = redisCommand(c,"SMEMBERS %s", "order:111");
  assert(strcmp(reply->element[0]->str, "wwwwUPDATED") == 0  || strcmp(reply->element[0]->str, "ffffUPDATED") == 0 );
  assert(strcmp(reply->element[1]->str, "wwwwUPDATED") == 0  || strcmp(reply->element[1]->str, "ffffUPDATED") == 0 );
  freeReplyObject(reply);

  reply = redisCommand(c,"SADD %s %s", "order:222", "zzzzUPDATED");
  check_int(208, reply, 1);

  /* test that modifying any member of the set (above) applies the update to all members */
  reply = redisCommand(c,"SISMEMBER %s %s", "order:222", "xxxxUPDATED");
  check_int(209, reply, 1);

  /* test that calling sismember triggers an update */
  reply = redisCommand(c,"SISMEMBER %s %s", "order:333", "qqqqUPDATED");
  check_int(210, reply, 1);

  /* test that calling srem correctly deletes after update*/
  reply = redisCommand(c,"SREM %s %s", "order:444", "aaaaUPDATED");
  check_int(211, reply, 1);
  reply = redisCommand(c,"SISMEMBER %s %s", "order:444", "aaaaUPDATED");
  check_int(212, reply, 0);
  reply = redisCommand(c,"SISMEMBER %s %s", "order:444", "aaaa");
  check_int(213, reply, 0);
  reply = redisCommand(c,"SCARD %s", "order:444");
  check_int(214, reply, 1);

  printf("Redis shutdown:\n");
  system("killall redis-server");
  sleep(2);

}

int main(void){

  system("killall redis-server");
  sleep(2);
  test_sadd_smembers_nschange();
  test_sadd_smembers_valchange();
  printf("All pass.\n");
  return 0;
}
