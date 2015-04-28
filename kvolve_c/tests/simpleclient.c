#include <hiredis/hiredis.h>
#include "simpleclient.h"
#include "../kvolve.h"


void connect(const char *ip, int port, struct ns_vers_args * args){
  redisContext *r = redisConnect(ip, port);
  struct ns_vers_args * iter = args;
  while(iter){
    kvolve_append_version(args->ns, args->vers);
    iter = args->next;
  }
}


