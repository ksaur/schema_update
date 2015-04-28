
#include <hiredis/hiredis.h>
#include "kvolve.h"
#include <string.h>

struct ns_keyname{
  char * ns;
  char * keyname;
};


void foo(){}

/* Split the original key into (namespace, keyname) */
struct ns_keyname split_namespace_key(char * orig_key){
  char * split = strrchr(orig_key, ':');
  struct ns_keyname ns_k;
  if (split == NULL){
    ns_k.ns = "*";
    ns_k.keyname = orig_key;
  } else {
    foo();
    orig_key[split - orig_key] = '\0'; // clobber the ':'
    ns_k.ns = orig_key; 
    ns_k.keyname = split+1;
  }
  return ns_k;
}

void kvolve_set(char * buf){

  DEBUG_PRINT(("BUF IS \'%s\'", buf));
  char * carr_ret = strchr(buf, '\r');
  strncpy(carr_ret, "\0", 1);

  char * saveptr;
  char * cmd = strtok_r(buf, " ", &saveptr); //GET
  char * orig_key = strtok_r(NULL, " ", &saveptr); //key
  char * orig_val = strtok_r(NULL, " ", &saveptr); //value
  char * flags = strtok_r(NULL, " ", &saveptr); //flags
  struct ns_keyname ns_k = split_namespace_key(orig_key);
  char * ns = ns_k.ns;
  char * suffix = ns_k.keyname;



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

