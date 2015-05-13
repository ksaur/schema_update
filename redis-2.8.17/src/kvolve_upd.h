#ifndef _KVOLVE_UPD_H
#define _KVOLVE_UPD_H

typedef void (*kvolve_update_kv_fun)(char * key, void * value);

struct kvolve_upd_info{
  char * from_ns;
  char * to_ns;
  char * from_vers;
  char * to_vers;
  kvolve_update_kv_fun * funs;
  int num_funs;
};

#endif
