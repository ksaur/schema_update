#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "uthash.h"
#include "kvolve.h"

struct ns_keyname{
  char * ns;
  char * keyname;
};

struct version_hash{
  char * ns; /* key */
  char ** versions; 
  int num_versions;
  UT_hash_handle hh; /* makes this structure hashable */
};

static struct version_hash * vers_list = NULL;

/* return 1 if appended new version.  else return 0 */
int kvolve_append_version(char * vers_str){

 // printf("GOT VERSION STRING OF %s\n", vers_str);
//  return 1;
  char *ns_lookup = "order";
  char *vers = "v0";

  struct version_hash *e = NULL;

  HASH_FIND(hh, vers_list, &ns_lookup, strlen(ns_lookup), e);  /* id already in the hash? */
  if (e==NULL){
    e = (struct version_hash*)malloc(sizeof(struct version_hash));
    e->ns = malloc(strlen(ns_lookup)+1);
    strcpy(e->ns, ns_lookup); 
    e->num_versions = 1;
    *e->versions = calloc(10,sizeof(char*)); /* TODO, dynamically resize array */
    e->versions[0] = malloc(strlen(vers)+1);
    strcpy(e->versions[0], vers);
    HASH_ADD_KEYPTR(hh, vers_list, e->ns, strlen(e->ns), e);  /* id: name of key field */
  } else{
    /* TODO correct version validation!!!!! */
    e->num_versions++;
    if(e->num_versions > 10){
      /* TODO realloc*/
      printf("CANNOT APPEND, REALLOC NOT IMPLEMENTED, TOO MANY VERSIONS. ");
      return 0;
    }
    strcpy(e->versions[e->num_versions-1], vers);
  }
  return 1;
}

/* Split the original key into (namespace, keyname) */
struct ns_keyname split_namespace_key(char * orig_key){
  char * split = strrchr(orig_key, ':');
  struct ns_keyname ns_k;
  if (split == NULL){ //TODO testing
    ns_k.ns = "*";
    ns_k.keyname = orig_key;
  } else {
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

