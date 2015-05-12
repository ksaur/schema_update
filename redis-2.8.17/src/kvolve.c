#include <signal.h> // For redis.h 'siginfo_t'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#undef __GNUC__  // allow malloc (needed for uthash)  (see redis.h ln 1403)
#include "uthash.h"
#include "kvolve.h"
#include "redis.h"


struct version_hash{
    char * ns; /* key */
    char ** versions; 
    int num_versions;
    UT_hash_handle hh; /* makes this structure hashable */
};

static struct version_hash * vers_list = NULL;

/* return 1 to halt normal execution flow. return 0 to continue as normal */
int kvolve_process_command(redisClient *c){
  
    if (c->argc > 2 && strcasecmp((char*)c->argv[0]->ptr, "client") == 0 && 
                 strcasecmp((char*)c->argv[1]->ptr, "setname") == 0) {
        kvolve_append_version((char*)c->argv[2]->ptr);
        return 0;
    } else if (c->argc > 2 && strcasecmp((char*)c->argv[0]->ptr, "set") == 0){
        kvolve_set(c);
        return 1;
    } /*else if (c->argc > 2 && strcasecmp((char*)c->argv[0]->ptr, "get") == 0){
        kvolve_set(c);
        return 1;
    } */
 
    return 0;
}
/* return 1 if appended new version.  else return 0 */
int kvolve_append_version(char * vers_str){
  
    int toprocess =  strlen(vers_str);
    char * cpy = malloc(strlen(vers_str)+1);
    strcpy(cpy, vers_str);

    /* TODO verification/validation.....*/
    while(1) {
        char * ns_lookup; 
        char * vers;
        if (strcmp(cpy, vers_str) == 0)
            ns_lookup = strtok(cpy, "@");
        else
            ns_lookup = strtok(NULL, "@"); /* We've already started processing */
        vers = strtok(NULL, ",");
        int pos = strlen(vers);
        printf("%s %s %s %d %d", ns_lookup, vers, vers_str, toprocess, pos);
  
        struct version_hash *e = NULL;
  
        HASH_FIND(hh, vers_list, ns_lookup, strlen(ns_lookup), e);  /* id already in the hash? */
        if (e==NULL){
            e = (struct version_hash*)malloc(sizeof(struct version_hash));
            e->ns = malloc(strlen(ns_lookup)+1);
            strcpy(e->ns, ns_lookup); 
            e->num_versions = 1;
            e->versions = calloc(10,sizeof(char*)); /* TODO, dynamically resize array */
            e->versions[0] = malloc(strlen(vers)+1);
            strcpy(e->versions[0], vers);
            HASH_ADD_KEYPTR(hh, vers_list, e->ns, strlen(e->ns), e);  /* id: name of key field */
        } else if(strcmp(e->versions[e->num_versions-1], vers) == 0){
            // TODO do we need to do something here?
        } else{
            
            /* TODO correct version validation!!!!! */
            e->num_versions++;
            if(e->num_versions > 10){
                /* TODO realloc*/
                printf("CANNOT APPEND, REALLOC NOT IMPLEMENTED, TOO MANY VERSIONS. ");
                return 0;
            }
            /* TODO validation!!!!!!!! */
            e->versions[e->num_versions-1] = malloc(strlen(vers)+1);
            strcpy(e->versions[e->num_versions-1], vers);
        }
        if(&vers[pos] == &cpy[toprocess])
            return 1;
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

void kvolve_set(redisClient * c){
    struct version_hash *v = NULL;
    size_t initlen;
    int ret, num_vers;
    sds new_keyname_sds;
    char * outbuf;

    struct ns_keyname ns_k = split_namespace_key((char*)c->argv[1]->ptr);
    char * ns = ns_k.ns;
    char * suffix = ns_k.keyname;

    /* get the current version for the namespace */
    HASH_FIND(hh, vers_list, ns, strlen(ns), v);  
    /* TODO something better than assert fail.
     * Also, should we support 'default namespace' automatically? */
    assert(v != NULL);
    
    /* allocate outbuf +3 (|, :, \n) */
    outbuf = malloc(strlen(v->versions[v->num_versions-1])+strlen(ns)+strlen(suffix)+3);
    initlen = sprintf(outbuf, "%s|%s:%s", v->versions[v->num_versions-1], ns, suffix);
    new_keyname_sds = sdsnewlen(outbuf, initlen); // don't free this. added to db
    free(outbuf);
    c->argv[1]->ptr = new_keyname_sds; // ->ptr will be freed in teardown w others

    /* Do the actual set */
    ret = processCommand(c);

    /* TODO: examine flags.... */

    /* Now check to see if deletions are necessary */
    num_vers = v->num_versions;
    while(num_vers > 1){
        outbuf = malloc(strlen(v->versions[num_vers-2])+strlen(ns)+strlen(suffix)+3);
        initlen = sprintf(outbuf, "%s|%s:%s", v->versions[num_vers-2], ns, suffix);
        sds tmp = sdsnewlen(outbuf, initlen);
        free(outbuf);
        robj * todel = createObject(REDIS_STRING, tmp);
        dbDelete(c->db, todel);
        zfree(todel);
        sdsfree(tmp);
        num_vers--;
    }

    if(ret == REDIS_OK) 
        resetClient(c);

}

//int kvolve_get(char * buf, char * outbuf, int from, redisContext * c){
//
//  redisReply *reply;
//  DEBUG_PRINT(("BUF IS \'%s\'", buf));
//  char * carr_ret = strchr(buf, '\r');
//  strncpy(carr_ret, "\0", 1);
//
//  size_t bytes_written, bytes_towrite;
//  char *saveptr;
//  char *cmd = strtok_r(buf, " ", &saveptr); //GET
//  char *orig_key = strtok_r(NULL, " ", &saveptr); //key
//  struct ns_keyname ns_k = split_namespace_key(orig_key);
//  char * ns = ns_k.ns;
//  char * suffix = ns_k.keyname;
//  struct version_hash *v = NULL;
//  int i, pos=0;
//
//  /* get the current version for the namespace */
//  HASH_FIND(hh, vers_list, ns, strlen(ns), v);  
//  /* TODO something better than assert fail.
//   * Also, should we support 'default namespace' automatically? */
//  assert(v != NULL);
//
//  /* The "express route" where we find a key at the current version and
//   * immediately return. */
//  sprintf(outbuf, "%s|%s:%s", v->versions[v->num_versions-1], ns, suffix);
//  reply = redisCommand(c,"GET %s", outbuf);
//
//  /* TODO implement ### delimiter */
//  if(reply->type == REDIS_REPLY_STRING){
//    /* Key is already at current version. */
//    bytes_towrite = sprintf(outbuf, "$%d\r\n%s\r\n", reply->len, reply->str);
//    bytes_written = write(from, outbuf, bytes_towrite);
//    freeReplyObject(reply);
//    if (bytes_written == -1) 
//        return 1;
//    return 0;
//  }
//  freeReplyObject(reply);
//
//  /* Check for key at _any_ version. */
//  /* TODO, "*" namespace */
//  for(i=0; i<v->num_versions; i++){
//    pos+=sprintf(outbuf+pos, "%s|%s:%s ", v->versions[i], ns, suffix);
//  }
//  reply = redisCommand(c,"MGET %s", outbuf);
//  for(i=0; i<v->num_versions; i++){
//    if(reply->element[i]->type != REDIS_REPLY_NIL)
//       break;
//  }
//  freeReplyObject(reply);
//  if(i == v->num_versions){
//    /* TODO mark #####*/
//    //reply = redisCommand(c,"SETNX %s", TODO); 
//    //freeReplyObject(reply);
//    bytes_written = write(from, "$-1\r\n", 5);
//    if (bytes_written == -1) 
//        return 1;
//    return 0;
//    
//  }
//  
//  /* TODO: ('SETNX', all_potential_keys[0], "#### ####") */
//  bytes_written = write(from, "+OK\r\n", 5);
//
//
//  // Now reconstruct buffer. 
//  pos = 0;
//  // perform checks in case garbage input
//  if(cmd && orig_key){
//    pos = strlen(cmd); // advance past cmd
//    strncpy(buf+pos, " ", 1); // add a space 
//    pos++;
//    strcpy(buf+pos, orig_key);
//    pos += strlen(orig_key);
//    strncpy(buf+pos, "\r\n", 2);
//  }
//
//  return 0;
//}

#define __GNUC__  // "re-unallow" malloc
