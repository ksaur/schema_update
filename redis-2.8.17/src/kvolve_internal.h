#ifndef _KVOLVE_INTERNAL_H
#define _KVOLVE_INTERNAL_H
#include <bits/siginfo.h> // For redis.h 'siginfo_t' TODO why will this not work with signal.h??
#include "uthash.h"
#include "redis.h"
#include "kvolve_upd.h"


#define DEBUG
#ifdef DEBUG
# define DEBUG_PRINT(x) printf x
#else
# define DEBUG_PRINT(x) do {} while (0)
#endif


/* copied from t_string.c */
#define REDIS_SET_NO_FLAGS 0
#define REDIS_SET_NX (1<<0)     /* Set if key not exists. */
#define REDIS_SET_XX (1<<1)     /* Set if key exists. */

struct version_hash{
    char * ns; /* key */
    char * prev_ns; /* key */
    char ** versions; 
    struct kvolve_upd_info ** info; 
    int num_versions;
    UT_hash_handle hh; /* makes this structure hashable */
};

struct version_hash * get_vers_list(void);
struct version_hash * version_hash_lookup(char * lookup);
struct version_hash * kvolve_create_ns(char *ns_lookup, char *prev_ns, char * v0);
int kvolve_check_version(char * vers_str);
int kvolve_update_version(char * upd_code);
void kvolve_internal_rename(redisClient * c, struct version_hash * v);
char * kvolve_prev_name(char * orig_key, char *old_ns);
int kvolve_get_flags(redisClient *c);
//int kvolve_exists_anywhere(redisClient * c);
//int kvolve_get_all_versions(redisClient * c, robj *** arr);
robj * kvolve_get_curr_ver(redisClient * c);
void kvolve_check_update_kv_pair(redisClient * c);

#endif
