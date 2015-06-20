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

/* This structure stores the user-supplied update data */
struct kvolve_upd_info{
  char * from_ns;
  char * to_ns;
  char * from_vers;
  char * to_vers;
  kvolve_upd_fun * funs;
  int num_funs;
};

/* This structure stores the user-supplied version info */
struct version_hash{
    char * ns; /* key */
    char * prev_ns; /* key */
    char ** versions;
    struct kvolve_upd_info ** info;
    int num_versions;
    UT_hash_handle hh; /* makes this structure hashable */
};

/* Lookup the current version for the keyname @lookup */
struct version_hash * kvolve_version_hash_lookup(char * lookup);

/* Create a new namespace and insert it into the hash table */
struct version_hash * kvolve_create_ns(char *ns_lookup, char *prev_ns, char * v0, struct kvolve_upd_info * list);

/* Used on client connect, validates the requested namespaces.  If valid,
 * return 1, else return 0 */
int kvolve_check_version(char * vers_str);

/* Call dlopen on the user code provided at @upd_code, which will trigger the
 * auto calling of the user-supplied function kvolve_declare_update() (because
 * of __attribute__((constructor))),  which will load the user code into the
 * hash table */
void kvolve_load_update(char * upd_code);

/* Update the namespace only of the keynamed @v->argv[1], based on the update
 * version info stored in @v.*/
void kvolve_namespace_update(redisClient * c, struct version_hash * v);

/* Get the keyname from @orig_key and combine it with @old_ns.
 * Allocates memory for the prev name string and returns it. */
char * kvolve_construct_prev_name(char * orig_key, char *old_ns);

/* Get the flags stored on a set (xx, nx, etc), returned as a bitmap int. */
int kvolve_get_flags(redisClient *c);

/* Return the value (robj) currently stored in the database.  Used when there is
 * a namespace change.  Ex: if the user requested foo:bar:baz, but the key is
 * stored in the database as foo:bar due to a namespace change, this will
 * retrieve the object currently stored under the old name.*/
robj * kvolve_get_db_val(redisClient * c);

/* THIS IS THE UPDATE FUNCTION.  It's used by both strings and sets.
 *   @c : the client provided at kvolve entry
 *   @check_key : if check_key is 0, this function will not try to update the
 *       key.  This is used on repetitve calls for sets (key_not_checked,
 *       set_item1_not_checked), (key_already_checked, set_item2_not_checked), etc.
 *   @o : This option is used by set/zsets/etc types only (always NULL for strings). If
 *       non-NULL, this function will try to update this 'o' object, rather than
 *       looking it up from @c.
 *   @type : The container type of the to-be-updated element (Ex: REDIS_ZSET if @o
 *        belongs to a zset).
 *   @s : If a zset, a pointer to the score.  Else NULL
 */
void kvolve_check_update_kv_pair(redisClient * c, int key_check, robj * o, int type, double * s);

/* Update a member of a set adding the new version (@new_val)
 * and delete the old version.  This is called by the update function. */
void kvolve_update_set_elem(redisClient * c, char * new_val, robj ** o);

/* Update a member of a zset adding the new version (@new_val)
 * and delete the old version.  This is called by the update function.
 * //TODO support score updates */
void kvolve_update_zset_elem(redisClient * c, char * new_val, robj ** o, double s);

/* Check if a rename is necessary, and if so, rename.  @nargs is the number of
 * keys stored in @c->argv to check.  The @nargs is necessary for thing such as
 * sets, where you only want to check the key once.  (Calls such as delete may
 * be calls with multiple keys, so we must check all of the keys */
void kvolve_check_rename(redisClient * c, int nargs);

/* Return 1 if key present in outdated ns, else return 0. */
int kvolve_exists_old(redisClient * c);

/* check if updated needed for robjs of REDIS_ZSET */
void kvolve_update_all_zset(redisClient * c);

/* Redis doesn't allow empty sets/zset/lists/hashes, so when a new one is
 * created, it's not possible to set the version string before the call happens
 * without throwing off the return response to the client and counters/etc.
 * This function will retrieve the name of the new (z)set/list/hash, and set the
 * version on the next call to kvolve (before the user can possibly make any
 * other calls) */
void kvolve_prevcall_check(void);

/* Stores the keyname when to creating a new (z)set/list/hash */
void kvolve_new_version(redisClient *c, int type);
/* Sets the keyname after creating a new set */
void kvolve_newset_version_setter(void);
/* Sets the keyname after creating a new zset */
void kvolve_newzset_version_setter(void);



#endif
