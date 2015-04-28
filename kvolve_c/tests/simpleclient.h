#ifndef _SIMPLECLIENT_H
#define _SIMPLECLIENT_H

struct ns_vers_args{

  char * ns;
  char * vers;
  struct ns_vers_args * next;
};

void connect(const char *ip, int port, struct ns_vers_args * args);

#endif
