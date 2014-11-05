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
#include "jsondiff.h"

/* Global redis instance for storing code to output. Could use a hashmap, but
 * this seem appropriate... */
redisContext *redis;
redisReply *reply;


/* Return the length of the string appended */
int rsadd(const char * key, const char * value)
{
   int ret;
   reply = redisCommand(redis, "SADD %s %s", key, value);
   ret = reply->integer;
   if(reply->integer == 0)
      printf("WARNING: %s already added\n", value);
   freeReplyObject(reply);
   return ret;
}

/* Return the length of the string appended */
int rappend(const char * key, const char * value)
{
   int ret;
   reply = redisCommand(redis, "APPEND %s %s", key, value);
   ret = reply->integer;
   ret = reply->integer;
   freeReplyObject(reply);
   return ret;
}

/* Add the JSON field @key to the JSON object @root */
int radd(const char * root, const char * key, command cmd)
{
   int ret = 0, size = 0;
   char * defval;
   char * app_cmd;

   if(cmd == SET_CMD)
   {
      size = asprintf(&defval, "%s%s", "DEFAULT_", key);
      if(size == -1)
      {
         printf("ERROR creating a DEFAULT string for %s\n", key);
         return -1;
      }

      size = asprintf(&app_cmd, "%s%s%s%s%s", SET_CMD_STR, key, ", ",
                      defval, ");\n");

      if(size == -1)
      {
         printf("ERROR creating a cmd string for %s\n", key);
         return -1;
      }

      /* add the #define for the user to fill out. */
      rsadd(DEFINE_KEY, defval); 
      free(defval);
   }
   else if(cmd ==  DEL_CMD)
   {


      size = asprintf(&app_cmd, "%s%s%s%s", DEL_CMD_STR, key, defval, ");\n");
      if(size == -1)
      {
         printf("ERROR creating a cmd string for %s\n", key);
         return -1;
      }
   }
   else
   {
      printf("ERROR: unknown function command %d\n", cmd);
   }


   /* add a command to modify @key in @root */
   ret = rappend(root, app_cmd);


   free(app_cmd);
   return ret;
}

/* Write out the header to file */
void rprintheader(void)
{

   int i;
   printf("\n\n"); //TODO put all to file instead of printing
   printf("/* file: jsondiff.c\n * Generated structures to migrate schema.\n");
   printf(" * TODO: (somehow enable the user to) fill in the initialization\n");
   printf(" *       values for (your_new_default_val).\n */\n\n");
   printf("#include <jansson.h>\n");

   /* Print out all of the #defines for the user to fill in */
   reply = redisCommand(redis, "SMEMBERS %s", DEFINE_KEY);
   for(i=0; i<reply->elements; i++)
   {
      printf("#define %s (your_new_default_val)\n", reply->element[i]->str);
   }
   freeReplyObject(reply);

   /* Print of all the forward declarations. */
   printf("\n\n/* Declarations */\n");
   reply = redisCommand(redis, "SMEMBERS %s", TOP_DECLS_KEY);
   for(i=0; i<reply->elements; i++)
   {
      printf("%s\n", reply->element[i]->str);
   }
   freeReplyObject(reply);
   printf("\n\n/* Migration functions */\n");

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
      reply_local = redisCommand(redis, "TYPE %s", key);

      /* If it's not a string, don't print.
       * (All strings in the database are functions to print.
       * All sets, etc are auxillary, so skip them here.) */
      if(strncmp(reply_local->str, "string", 6) != 0)
      {
         freeReplyObject(reply_local);
         continue;
      }
      freeReplyObject(reply_local);
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

/* Print the forward calls for this object */
// TODO merge old/new....
// TODO make sure functions exists!!!!!!!!!
// TODO forward decls!!
void diff_objects_continue(json_t * old, json_t * new, const char * root)
{
   const char *key;
   json_t *value;

   json_object_foreach(old, key, value)
   {
      json_t * value = json_object_get(old, key);
      if(json_is_object(value))
      {
         char * cmd;
         int err = asprintf(&cmd, "\t%s%s%s", "upd_", key, "(obj);\n\n");
         rappend(root, cmd);
         free(cmd);
      }
   }
}

/* This loop checks for objects in "in" that are not present in the "out".
 * Called for new->old and old->new */
void diff_objects_iter(json_t * in, json_t * out, const char *root, command cmd)
{
   const char *key;
   json_t *value;

   /* Iterate over every key-value pair of object */
   json_object_foreach(in, key, value)
   {
      json_t * outvalue = json_object_get(out, key);
      if(json_is_object(value))
      {
         if(outvalue == NULL)
            radd(root, key, cmd);
         else
            diff_objects(outvalue, value, key);
      }
      else if(json_is_string(value) || json_is_number(value) ||
              json_is_boolean(value) || json_is_null(value))
      {
         //printf("Found string = %s\n", key);
         if(outvalue == NULL)
            radd(root, key, cmd);
      }
      else if(json_is_array(value))
      {
         //printf("Found array = %s\n", key);
         if(outvalue == NULL)
            printf("OMG TOODO (%s)\n", key);
         /* TODO: for now, just going to process the FIRST element of the
            array.  I'm not sure yet what our stated assumptions will be.
            Currently I'm assuming that all array elements are identical,
            and that the number of array elements does not matter. */

         /* get and process the head array element */
         // TODO TESTING
         else  // oldvalue is not NULL
            diff_objects_iter(json_array_get(outvalue,  0),
                              json_array_get(value,  0), NULL, cmd);
      }
   }
}

/* Diff two JSON objects */
void diff_objects(json_t * old, json_t * new, const char *root)
{

   char * header, * decl;
   int err;

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
         err = asprintf(&header, "%s%s%s%s%s", "struct upd_", root,
                        "(json_t * parent){\n\tjson_t * obj = "
                        "json_object_get(parent, ", root, ");\n\n");
         if(err == -1)
         {
            printf("ERROR: Problem creating header\n");
            return;
         }

         rappend(root, header);
         free(header);

         /* Call the iteration functions to create the diff function calls */
         diff_objects_iter(old, new, root, DEL_CMD);
         diff_objects_iter(new, old, root, SET_CMD);

         /* Insert function call for @root to forward declaration */
         err = asprintf(&decl, "%s%s%s", "struct upd_", root,
                        "(json_t * parent);");
         if(err == -1)
         {
            printf("ERROR: Problem creating header\n");
            return;
         }

         /* add the function declaration to the set of top decls */
         rsadd(TOP_DECLS_KEY, decl); 
         free(decl);

         /* Insert function calls for subsequent objects */
         diff_objects_continue(old, new, root);

         /* Print the trailer*/
         rappend(root, "};");
      }
      else
      {
         freeReplyObject(reply);
         printf("Already processed %s.\n", root);
      }
   }
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
   const char *key;
   json_t *newvalue, *oldvalue;
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
   json_object_foreach(new, key, newvalue)
   {

      /* JSON container: object. Look inside */
      if (json_is_object(new))
      {
         /* get the corresponding old object for comparison */
         oldvalue = json_object_get(old, key);
         if(!oldvalue)
            printf("Warning: No matching object (%s) in old version\n", key);
         else
            diff_objects(oldvalue, newvalue, key);
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
         //TODO implement!!!
         diff_objects(json_array_get(old,  0), json_array_get(new,  0), NULL);

      }
      else
      {
         printf("ERROR. Outermost object must be a container (array or object.)\n");
         return -1;
      }
   }


   /* Dump the header to file */
   rprintheader();

   /* Dump keys to file */
   riterall(0);

   /* Disconnects and frees the context */
   redisFree(redis);
   return 0;
}
