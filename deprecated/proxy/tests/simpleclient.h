#ifndef _SIMPLECLIENT_H
#define _SIMPLECLIENT_H

redisContext * kv_connect(const char *ip, int port, char * args);

#endif
