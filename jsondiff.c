/*
 * ksaur: Diff two JSON files, output C code to run the diff using Jansson.
 *
 * This uses the Jansson library: (https://github.com/akheron/jansson)
 *
 * Jansson is free software; you can redistribute it and/or modify
 * it under the terms of the MIT license. See LICENSE for details.
 */

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <hiredis/hiredis.h>
#include <jansson.h>

/* Global redis instance for storing code to output. Could use a hashmap, but
 * this seem appropriate... */
redisContext *redis;
redisReply *reply;


/* Return the length of the string appended */
int rappend(const char * key, const char * value)
{
   reply = redisCommand(redis, "APPEND %s %s", key, value);
   int ret = reply->integer;
   freeReplyObject(reply);
   return ret;
}

/* Add the JSON field @key to the JSON object @root */
/* TODO make this less horribly inefficient...sprintf? */
int radd(const char * root, const char * key)
{
   int ret = 0;
   ret += rappend(root, "\tjson_object_set(out, ");
   ret += rappend(root, key);
   ret += rappend(root, ", DEFAULT_");
   ret += rappend(root, key);
   ret += rappend(root, ");\n");
   return ret;
}

/* Write all of the update code/structs out from the database */
void riterall(int scan_at)
{

   int num_to_iter, i, next_bucket;
   redisReply *reply_local;

   /* SCAN is a cursor based iterator. Two tokens: first is
    * where to scan next, second is the data for this hashbucket. */
   reply = redisCommand(redis, "SCAN %d", scan_at);

   if(reply->elements != 2)
   {
      printf("ERROR DUMPING DB\n");
      freeReplyObject(reply);
      return;
   }

   /* The second element of the reply is all keys in the @scan_at bucket */
   num_to_iter = reply->element[1]->elements;
   for(i = 0; i < num_to_iter; i++)
   {
      char * key = reply->element[1]->element[i]->str;
      reply_local = redisCommand(redis, "GET %s", key);
      /* TODO printing to file? */
      if(reply_local)
      {
         printf("%s\n", reply_local->str);
         freeReplyObject(reply_local);
      }
   }

   next_bucket = atoi(reply->element[0]->str);
   freeReplyObject(reply);

   //TODO. not tested. test with larger DB.
   /* if there is more than one bucket, continue on. */
   if(next_bucket != 0)
      riterall(next_bucket);


}

/* Diff two JSON objects */
void diff_objects(json_t * old, json_t * new, const char *root)
{

   const char *key;
   json_t *value;

   if(root == NULL && (!json_is_object(new) || !json_is_object(old)))
   {
      printf("ERROR  Old and New should both be roots....\n");
      return;
   }

   /* Print the header */
   if(root !=NULL)
   {

      /* Check if we have already processed this JSON object */
      reply = redisCommand(redis, "EXISTS %s", root);
      if(reply->integer == 0)
      {
         freeReplyObject(reply);
         printf("Processing %s:\n", root);
         rappend(root, "struct upd_");
         rappend(root, root);
         rappend(root, "{\n");
      }
      else
      {
         freeReplyObject(reply);
         printf("Already processed %s.\n", root);
      }
   }

   /* Iterate over every key-value pair of object
    *  This loop checks for objects in the NEW that are not present
    *  in the OLD */
   json_object_foreach(new, key, value)
   {
      json_t * oldvalue = json_object_get(old, key);
      if(json_is_object(value))
      {
         if(oldvalue == NULL)
            radd(root, key);
         else
            diff_objects(oldvalue, value, key);
      }
      else if(json_is_string(value) || json_is_number(value) ||
              json_is_boolean(value) || json_is_null(value))
      {
         //printf("Found string = %s\n", key);
         if(oldvalue == NULL)
            radd(root, key);
      }
      else if(json_is_array(value))
      {
         //printf("Found array = %s\n", key);
         if(oldvalue == NULL)
            printf("OMG TOODO (%s)\n", key);
         /* TODO: for now, just going to process the FIRST element of the
            array.  I'm not sure yet what our stated assumptions will be.
            Currently I'm assuming that all array elements are identical,
            and that the number of array elements does not matter. */

         /* get and process the head array element */
         // TODO TESTING
         else  // oldvalue is not NULL
            diff_objects(json_array_get(oldvalue,  0), json_array_get(value,  0), NULL);
      }
   }
   /* Iterate over every key-value pair of object
    *  This loop checks for objects in the OLD that are not present
    *  in the NEW */
   //TODO fixup
   //json_object_foreach(old, key, value){
   //   json_t * newvalue = json_object_get(new, key);
   //   if(json_is_object(value)){
   //      if(newvalue == NULL)
   //         j += sprintf(buffer+j, "\tjson_object_set(out, "
   //            "\"%s\", DEFAULT_%s);\n", key, key);
   //      else  // oldvalue is not NULL
   //         diff_objects(newvalue, value, key);
   //   }
   //    else if(json_is_string(value) || json_is_number(value) ||
   //         json_is_boolean(value) || json_is_null(value)){
   //      //printf("Found string = %s\n", key);
   //      if(newvalue == NULL)
   //         j += sprintf(buffer+j, "\tjson_object_set(out, \"%s\", DEFAULT_%s);\n", key, key);
   //   }
   //    else if(json_is_array(value)){
   //      //printf("Found array = %s\n", key);
   //      if(newvalue == NULL)
   //         printf("OMG TOODO (%s)\n", key);
   //      /* TODO: for now, just going to process the FIRST element of the
   //         array.  I'm not sure yet what our stated assumptions will be.
   //         Currently I'm assuming that all array elements are identical,
   //         and that the number of array elements does not matter. */

   //      /* get and process the head array element */
   //      // TODO TESTING
   //      else  // oldvalue is not NULL
   //         diff_objects(json_array_get(value,  0), json_array_get(newvalue,  0), NULL);
   //   }
   //}
   /* Print the trailer*/
   if(root !=NULL)
      rappend(root, "};");
}


// TODO....do we need to do something special for each type? This version spells them all out.
//        else if(json_is_string(value)){
//         //printf("Found string = %s\n", key);
//         if(oldvalue == NULL)
//            j += sprintf(buffer+j, "\tjson_object_set(out, \"%s\", DEFAULT_%s);\n", key, key);
//      }
//        else if(json_is_number(value)){
//         //printf("Found number = %s\n", key);
//         if(oldvalue == NULL)
//            j += sprintf(buffer+j, "\tjson_object_set(out, \"%s\", DEFAULT_%s);\n", key, key);
//      }
//        else if(json_is_boolean(value)){
//         //printf("Found boolean = %s\n", key);
//         if(oldvalue == NULL)
//            j += sprintf(buffer+j, "\tjson_object_set(out, \"%s\", DEFAULT_%s);\n", key, key);
//      }
//        else if(json_is_null(value)){
//         //printf("Found null = %s\n", key);
//         if(oldvalue == NULL)
//            j += sprintf(buffer+j, "\tjson_object_set(out, \"%s\", DEFAULT_%s);\n", key, key);
//      }

/* Print JSON keys to string (ignore values, not necessary. */
void print_object(json_t * data)
{
   const char *key;
   json_t *value;

   // TODO Assertions that this is an object (not sure about that assumption)
   // ...need more test data.

   /* Iterate over every key-value pair of object */
   json_object_foreach(data, key, value)
   {
      if(json_is_object(value))
      {
         printf("Found object = %s\n", key);
         print_object(value);
      }
      else if(json_is_string(value))
         printf("Found string = %s\n", key);
      else if(json_is_number(value))
         printf("Found number = %s\n", key);
      else if(json_is_boolean(value))
         printf("Found boolean = %s\n", key);
      else if(json_is_null(value))
         printf("Found null = %s\n", key);
      else if(json_is_array(value))
      {
         printf("Found array = %s\n", key);
         /* TODO: for now, just going to process the FIRST element of the
            array.  I'm not sure yet what our stated assumptions will be.
            Currently I'm assuming that all array elements are identical,
            and that the number of array elements does not matter. */

         /* get and process the head array element */
         print_object(json_array_get(value, 0));
      }
   }
}


/*http://stackoverflow.com/questions/2029103/
   correct-way-to-read-a-text-file-into-a-buffer-in-c*/
char * request(char * filename)
{
   char * buf = NULL;
   FILE *fp = fopen(filename, "r");
   if (fp != NULL)
   {
      /* Go to the end of the file. */
      if (fseek(fp, 0L, SEEK_END) == 0)
      {
         /* Get the size of the file. */
         long bufsize = ftell(fp);
         if (bufsize == -1)
         {
            printf("Error reading in file %s\n", filename);
            return NULL;
         }

         /* Allocate our buffer to that size. */
         buf = malloc(sizeof(char) * (bufsize + 1));

         /* Go back to the start of the file. */
         if (fseek(fp, 0L, SEEK_SET) != 0)
         {
            printf("Error reading in file %s\n", filename);
            return NULL;
         }

         /* Read the entire file into memory. */
         size_t newLen = fread(buf, sizeof(char), bufsize, fp);
         if (newLen == 0)
         {
            fputs("Error reading file", stderr);
         }
         else
         {
            buf[++newLen] = '\0'; /* Just to be safe. */
         }
      }
      fclose(fp);
      return buf;
   }
   printf("Error reading in file %s\n", filename);
   return NULL;
}

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
   size_t i;
   char *text, *text2;
   json_t *old, *new;
   json_error_t error, error2;
   const char *host = (argc > 1) ? argv[1] : "127.0.0.1";
   int port = (argc > 2) ? atoi(argv[2]) : 6379;

   // TODO args.
   text = request("./example_json/simple1.json");
   text2 = request("./example_json/simple2.json");
   if(!text || !text2)
      return 1;

   old = json_loads(text, 0, &error);
   new = json_loads(text2, 0, &error2);
   free(text);
   free(text2);

   redisconnect(host, port);


   if(!old)
   {
      fprintf(stderr, "error: on line %d: %s\n", error.line, error.text);
      return 1;
   }
   if(!new)
   {
      fprintf(stderr, "error: on line %d: %s\n", error2.line, error2.text);
      return 1;
   }


   /* This loops over all of the new json fields.
    * Assume drop any fields in the old not in the new  */
   for (i = 0; i < json_object_size(new); i++)
   {

      /* JSON container: object */
      if (json_is_object(new))
      {
         //print_object(new);
         diff_objects(old, new, NULL);
      }
      ///* JSON container: array */
      else if (json_is_array(new))
      {
         /* TODO: for now, just going to process the FIRST element of the
            array.  I'm not sure yet what our stated assumptions will be.
            Currently I'm assuming that all array elements are identical,
            and that the number of array elements does not matter. */

         /* get and process the head array element */
         // TODO this code not tested
         //print_object(json_array_get(new,  0));
         diff_objects(json_array_get(old,  0), json_array_get(new,  0), NULL);

      }
      else
      {
         printf("ERROR. Outermost object must be a container (array or object.)\n");
         return -1;
      }
   }


   /* Dump keys to file */
   riterall(0);

   /* Disconnects and frees the context */
   redisFree(redis);
   return 0;
}
