/* dumpall_updateall.c:  This is a first step towards updating JSON strings in
 * redis.  It gets all keys, and then updates them all at once.  All of this is
 * done outside of redis
 *
 * Assume you have some strings stored as keys mapping to JSON objects.
 * This will iterate over all keys and run the generated update functions.
 **/

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
}

int main(int argc, char *argv[])
{

   int i;
   const char *host = (argc > 1) ? argv[1] : "127.0.0.1";
   int port = (argc > 2) ? atoi(argv[2]) : 6379;
   json_t *old;
   json_error_t error;
   const char *key;
   json_t *newvalue, *oldvalue;

   redisconnect(host, port);

   /* iterate through all keys */
   redisReply * all_keys_arr = redisCommand(redis, "KEYS %s", "*");
   for(i=0; i<all_keys_arr->elements; i++)
   {
      char * curr_key = all_keys_arr->element[i]->str;
      printf("Found key = %s\n", curr_key);
      /* check to make sure that the type of key is a string */

      reply = redisCommand(redis, "TYPE %s", curr_key);
      if(strncmp(reply->str, "string", 6) !=0 )
      {
         printf ("TODO: key (%s) not a string.  Not implemented!!!\n", curr_key);
         freeReplyObject(reply);
      }
      else
      {
         freeReplyObject(reply);
         reply = redisCommand(redis, "GET %s", curr_key);
         printf ("Value for (%s) is %s \n", curr_key, reply->str);
         old = json_loads(reply->str, 0, &error);
         if (json_is_object(old))
         {
            printf("Loaded object into json for key %s\n", curr_key);

            /* Assume here should only be one object per redis JSON entry.
             * There is no way with Jansson to get the name of the object
             * except by looping, so hence the loop. Iterate once, then break*/
            json_object_foreach(old, key, oldvalue)
            {
               printf("key = %s\n", key);
               update_json(old, key);
               freeReplyObject(reply);
               char * new = json_dumps(old, JSON_INDENT(2)); //indent for \"'s
               if(new==NULL)
               {
                  printf("ERROR: Could not parse key (%s) into json\n", curr_key);
                  break;
               }
               reply = redisCommand(redis, "SET %s \"%s\"", curr_key, new);
               if((reply->len != 2) || (strncmp(reply->str, "OK", 2) != 0))
               {
                  printf("ERROR: Could not write updated key (%s) back to redis\n",
                         curr_key);
               }
               freeReplyObject(reply);
               /* Break out of iterator... see comment at top of loop*/
               break;

            }
         }
         else
         {
            printf("Failed to load object into json for key %s\n", curr_key);
            freeReplyObject(reply);
         }
      }
   }
   freeReplyObject(all_keys_arr);

   return 0;
}
