/* dumpall_updateall.c:  This is a first step towards updating JSON strings in
 * redis.  It gets all keys, and then updates them all at once.  All of this is
 * done outside of redis*/

#include <hiredis/hiredis.h>
#include <jansson.h>

redisContext *redis;
redisReply *reply;

/* redisconnect to Redis using hiredis bindings */
void redisconnect(const char * host, int port)
{
   struct timeval timeout = { 1, 500000 }; // 1.5 seconds
   redis = redisConnectWithTimeout(host, port, timeout);
   if (redis == NULL || redis->err)
   {
      if (redis)
      {
         printf("Connection error: %s\n", redis->errstr);
         redisFree(redis);
      }
      else
      {
         printf("Connection error: can't allocate redis context\n");
      }
      exit(1);
   }
   /* wipe out all old keys from previous run */
   reply =redisCommand(redis, "FLUSHDB");
   if(strncmp(reply->str,"OK", 2) != 0)
      printf("WARNING. Could not flush old keys.\n");
   freeReplyObject(reply);
}

int main(int argc, char *argv[])
{

   const char *host = (argc > 1) ? argv[1] : "127.0.0.1";
   int port = (argc > 2) ? atoi(argv[2]) : 6379;

   redisconnect(host, port);

   return 0;
}
