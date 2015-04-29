#include <hiredis/hiredis.h>
#include "simpleclient.h"


void kv_connect(const char *ip, int port, char * args){
  redisContext *c = redisConnect(ip, port);
  redisCommand(c, "client setname %s", args);
}


