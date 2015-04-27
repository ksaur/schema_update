
#include <hiredis/hiredis.h>
#include "kvolve.h"
#include <string.h>

void kvolve_set(char * buf){

  printf ("BUF IS \'%s\'", buf);
  char* carr_ret = strchr(buf, '\r');
  // only grab the first line, there's garabage at the end
  //strncpy(((char*)carr_ret-buf), "\0", 1);
  strncpy(carr_ret, "\0", 1);


  char *saveptr;
  char *cmd = strtok_r(buf, " ", &saveptr); //GET
  char *orig_key = strtok_r(NULL, " ", &saveptr); //key
  char *orig_val = strtok_r(NULL, " ", &saveptr); //value
  char *flags = strtok_r(NULL, " ", &saveptr); //flags

  //printf("cmd = %s\n", cmd);
  //printf("orig_key = %s\n", orig_key);
  //printf("orig_val = %s\n", orig_val);
  //printf("flags = %s\n", flags);


  // Now reconstruct buffer. 
  int pos = 0;
  // perform checks in case garbage input
  if(cmd && orig_key && orig_val){
    pos = strlen(cmd); // advance past cmd
    strncpy(buf+pos, " ", 1); // add a space 
    pos++;
    strcpy(buf+pos, orig_key);
    pos += strlen(orig_key);
    strncpy(buf+pos, " ", 1);
    pos++;
    strcpy(buf+pos, orig_val);
    pos+= strlen(orig_val);
    // optional
    if(flags){
      strncpy(buf+pos, " ", 1);
      pos++;
      strcpy(buf+pos, flags);
      pos+= strlen(flags);
    }
    strncpy(buf+pos, "\r\n", 2);
  }
}


void kvolve_get(char * buf){


  char *saveptr;
  char *cmd = strtok_r(buf, " ", &saveptr); //GET
  char *orig_key = strtok_r(NULL, " ", &saveptr); //key

  //printf("cmd = %s\n", cmd);
  //printf("orig_key = %s\n", orig_key);

  // Now reconstruct buffer. 
  int pos = 0;
  // perform checks in case garbage input
  if(cmd && orig_key){
    pos = strlen(cmd); // advance past cmd
    strncpy(buf+pos, " ", 1); // add a space 
    pos++;
    strcpy(buf+pos, orig_key);
    pos += strlen(orig_key);
    strncpy(buf+pos, "\r\n", 2);
  }

}

