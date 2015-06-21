#include <signal.h> // For redis.h 'siginfo_t'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <assert.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <dlfcn.h>
#include <stdarg.h>
#undef __GNUC__  // allow malloc (needed for uthash)  (see redis.h ln 1403)
#include "uthash.h"
#include "kvolve_internal.h"
#include "redis.h"
#include "kvolve_upd.h"
#include "kvolve.h"

extern int processInlineBuffer(redisClient *c);
extern double zzlGetScore(unsigned char *sptr);
static struct version_hash * vers_list = NULL;
#define KV_INIT_SZ 20

redisDb * prev_db = NULL;
char * kvolve_set_version_fixup = NULL;
char * kvolve_zset_version_fixup = NULL;
redisClient * c_fake_user = NULL; // for the user's mu code calls

/* this flag indicates that an update function is being processed.  (Prevents
 * recursion in case of user making calls during update function*/
int upd_fun_running = 0;

struct version_hash * kvolve_create_ns(char *ns_lookup, char *prev_ns, char * v0, struct kvolve_upd_info * list){
    struct version_hash *tmp, * v = (struct version_hash*)malloc(sizeof(struct version_hash));
    int i;
    v->ns = malloc(strlen(ns_lookup)+1);
    strcpy(v->ns, ns_lookup); 
    v->prev_ns = NULL;
    if (prev_ns){
        v->prev_ns = malloc(strlen(prev_ns)+1);
        strcpy(v->prev_ns, prev_ns); 
        HASH_FIND(hh, vers_list, prev_ns, strlen(prev_ns), tmp);
        v->num_versions = 1+ tmp->num_versions;
        v->versions = calloc(KV_INIT_SZ,sizeof(char*)); //TODO check resize
        v->info = calloc(KV_INIT_SZ,sizeof(struct kvolve_upd_info*));
        for(i = 0; i< tmp->num_versions; i++){
            v->versions[i] = tmp->versions[i];
            v->info[i] = tmp->info[i];
        }
        v->versions[tmp->num_versions] = malloc(strlen(v0)+1);
        strcpy(v->versions[tmp->num_versions], v0);
        v->info[tmp->num_versions] = list;
    } else {
        v->num_versions = 1;
        v->versions = calloc(KV_INIT_SZ,sizeof(char*));
        v->versions[0] = malloc(strlen(v0)+1);
        v->info = calloc(KV_INIT_SZ,sizeof(struct kvolve_upd_info*));
        v->info[0] = NULL;
        strcpy(v->versions[0], v0);
    }
    HASH_ADD_KEYPTR(hh, vers_list, v->ns, strlen(v->ns), v);  /* id: name of key field */
    return v;
}


/* Get the keyname from @orig_key and combine it with @old_ns.  
 * Allocates memory for the new string and returns it. */
char * kvolve_construct_prev_name(char * orig_key, char *old_ns){
    char * name = strrchr(orig_key, ':');
    char * ret = malloc(strlen(name)+strlen(old_ns) +1);
    strcpy(ret, old_ns);
    strcat(ret, name);
    return ret;
}

/* returns a robj for the key if present in outdated ns. Caller must free*/
robj * kvolve_exists_old(redisClient * c){

    struct version_hash * v = kvolve_version_hash_lookup((char*)c->argv[1]->ptr);
    struct version_hash * tmp = v;
    robj * key, * val;
    if(v == NULL) return NULL;

    /* first check the obvious (current) */
    val = lookupKeyRead(c->db, c->argv[1]);
    if(val) return NULL;

    /* Iterate prev namespaces */
    while(tmp && tmp->prev_ns){
        char * old = kvolve_construct_prev_name((char*)c->argv[1]->ptr, tmp->prev_ns);
        key = createStringObject(old,strlen(old));
        free(old);
        val = lookupKeyRead(c->db, key);
        if (val){
            return key;
        }
        zfree(key);
        if(!tmp->prev_ns)
            break;
        tmp = kvolve_version_hash_lookup(tmp->prev_ns);
    }
    return NULL;
}

/* return 1 if OK.  else return 0. TODO don't allow connect if err */
int kvolve_check_version(char * vers_str){
  
    int toprocess =  strlen(vers_str);
    char * cpy = malloc(strlen(vers_str)+1);
    strcpy(cpy, vers_str);

    while(1) {
        char * ns_lookup; 
        char * vers;
        if (strcmp(cpy, vers_str) == 0)
            ns_lookup = strtok(cpy, "@");
        else
            ns_lookup = strtok(NULL, "@"); /* We've already started processing */
        vers = strtok(NULL, ",");
        int pos = strlen(vers);
  
        struct version_hash *v = NULL;
  
        HASH_FIND(hh, vers_list, ns_lookup, strlen(ns_lookup), v);  /* id already in the hash? */
        if (v==NULL){
            kvolve_create_ns(ns_lookup, NULL, vers, NULL);
        } else if (strcmp(v->versions[v->num_versions-1], vers) != 0){
            printf("ERROR, INVALID VERSION (%s). System is at \'%s\' for ns \'%s\'\n", 
                   vers, v->versions[v->num_versions-1], v->ns);
            //TODO don't let it connect.
            return 0;
        } 
        if (&vers[pos] == &cpy[toprocess])
            return 1;
    }
}

int kvolve_get_flags(redisClient *c){
    int flags = REDIS_SET_NO_FLAGS;
    int j;

    for (j = 3; j < c->argc; j++) {
        char *a = c->argv[j]->ptr;

        if ((a[0] == 'n' || a[0] == 'N') &&
            (a[1] == 'x' || a[1] == 'X') && a[2] == '\0') {
            flags |= REDIS_SET_NX;
        } else if ((a[0] == 'x' || a[0] == 'X') &&
                   (a[1] == 'x' || a[1] == 'X') && a[2] == '\0') {
            flags |= REDIS_SET_XX;
        }

    }
    return flags;
}

void kvolve_load_update(char * upd_code){

    void *handle;
    char *errstr;
    int err;
    struct stat s;
  
    DEBUG_PRINT(("Updating with %s\n", upd_code));
    err = stat(upd_code, &s);
    if(-1 == err) {
        printf("ERROR, update file %s does not exist.\n", upd_code);
        return;
    }

    /* The GLOBAL flag for 3rd party libraries.  The DEEPBIND flag so that
     * previous versions of 'kvolve_upd_spec' are replaced with the one about to be
     * loaded.*/

    handle = dlopen(upd_code, RTLD_NOW | RTLD_GLOBAL | RTLD_DEEPBIND);
    if (handle == NULL){
        errstr = dlerror();
        printf ("A dynamic linking error occurred: (%s)\n", errstr);
        return;
    }
}

/* This API function allows the update-writer to call into redis from the
 * update function (mu). */
char * kvolve_upd_redis_call(char* userinput){

    /* free from prev if necessary*/
    if(c_fake_user)
        freeClient(c_fake_user);
    c_fake_user = createClient(-1);
    size_t buff = strlen(userinput)+3;
    char * q = malloc(buff);
    /* add redis protocol fun */
    sprintf(q,"%s\r\n",userinput);
    c_fake_user->querybuf = sdsnew(q);
    free(q);
    /* parse the user input string */
    processInlineBuffer(c_fake_user);
    /* lookup the newly parsed command */
    c_fake_user->cmd = lookupCommandOrOriginal(c_fake_user->argv[0]->ptr);
    /* run through kvolve (set vers, and set flag to not run updates on this
     * value, else infinite loop!), then call properly*/
    kvolve_process_command(c_fake_user);
    call(c_fake_user, 0);
    return c_fake_user->buf;
}

/* This is the API function that the update-writer calls to load the updates */
void kvolve_upd_spec(char *from_ns, char * to_ns, char * from_vers, char * to_vers, int n_funs, ...){

    int i;
    struct version_hash * v;
    struct kvolve_upd_info * info;
    va_list arguments;

    /* Initializing arguments to store all values after num */
    va_start(arguments, n_funs);

    HASH_FIND(hh, vers_list, from_ns, strlen(from_ns), v);
    /* make sure namespace exists */
    if (v == NULL){
        printf("No such namespace (%s) to upgrade.\n", from_ns);
        return;
    } else if (strcmp(from_ns, to_ns) != 0){
        /* check if namespace exists already */
        HASH_FIND(hh, vers_list, to_ns, strlen(to_ns), v);
        if (v != NULL){
            printf("Cannot merge into existing ns (%s) from ns (%s).\n",
                   to_ns, from_ns);
            return;
        }
    } else {
        /* make sure update was not already loaded */
        for (i = 0; i < v->num_versions; i++){
            if (strcmp(v->versions[i], to_ns) == 0){
                printf("ERROR, previous version %s already loaded...\n", to_ns);
                return;
            }
        }
    }
    /* If not a new ns, make sure the previous version exists */
    if (v && v->prev_ns == NULL && strcmp(v->versions[v->num_versions-1], from_vers) != 0){
        printf("No such version (%s) to upgrade for ns (%s).\n",
               from_vers, from_ns);
        return;
    }

    /* If we've made it this far, create the info stucture */
    info = malloc(sizeof(struct kvolve_upd_info));
    info->from_ns = from_ns;
    info->to_ns = to_ns;
    info->from_vers = from_vers;
    info->to_vers = to_vers;
    info->num_funs = n_funs;
    info->funs = calloc(n_funs, sizeof(kvolve_upd_fun));
    for (i = 0; i<n_funs; i++){
        info->funs[i] = va_arg(arguments, kvolve_upd_fun);
    }
    /* If v is null, we need a new namespace */
    if (!v)
        v = kvolve_create_ns(to_ns, from_ns, to_vers, info);
    if (v->num_versions > KV_INIT_SZ){ /*TODO change this when resize impl'ed */
        /* TODO, dynamically resize array */
        printf("CANNOT APPEND, REALLOC NOT IMPLEMENTED, TOO MANY VERSIONS.\n");
        return;
    }
    v->versions[v->num_versions] = malloc(strlen(to_vers)+1);
    strcpy(v->versions[v->num_versions], to_vers);
    v->info[v->num_versions] = info;
    v->num_versions++;
 
}

/* Looks for a prepended namespace in @lookup (longest matching prefix), and
 * then lookups and returns the version information in the hashtable if it
 * exists, else returns null.  */
struct version_hash * kvolve_version_hash_lookup(char * lookup){
    struct version_hash *v = NULL;
    char * ns;
    size_t len;

    /* Split out the namespace from the key, if a namespace exists. */
    char * split = strrchr(lookup, ':');
    if (split == NULL){
        DEBUG_PRINT(("WARNING: No namespace declared for key %s\n", lookup));
        return NULL;
    }
    len = split - lookup + 1;
    ns = malloc(len);
    snprintf(ns, len, "%s", lookup);

    /* Get the current version for the namespace, if it exists */
    HASH_FIND(hh, vers_list, ns, len-1, v);

    /* If not found, recurse search for next longest prefix */
    if(!v && strrchr(ns, ':'))
        v = kvolve_version_hash_lookup(ns);
    free(ns);
    return v;
}


/* return the VALUE with the namespace that's currently in the db */
robj * kvolve_get_db_val(redisClient * c){

    struct version_hash * v = kvolve_version_hash_lookup((char*)c->argv[1]->ptr);
    struct version_hash * tmp = v;
    robj * key, * val;
    if(v == NULL) return NULL;

    /* first check the obvious (current) */
    val = lookupKeyRead(c->db, c->argv[1]);
    if(val) return val;

    /* Iterate prev namespaces */
    while(tmp && tmp->prev_ns){
        char * old = kvolve_construct_prev_name((char*)c->argv[1]->ptr, tmp->prev_ns);
        DEBUG_PRINT(("creating with old = %s\n", old));
        key = createStringObject(old,strlen(old));
        free(old);
        val = lookupKeyRead(c->db, key);
        zfree(key);
        if (val) return val;
        if(!tmp->prev_ns)
            break;
        tmp = kvolve_version_hash_lookup(tmp->prev_ns);
    }
    return NULL;
}


void kvolve_namespace_update(redisClient * c, struct version_hash * v) {

    redisClient * c_fake = createClient(-1);
    c_fake->argc = 3;
    c_fake->argv = zmalloc(sizeof(void*)*3);
    char * old = kvolve_construct_prev_name((char*)c->argv[1]->ptr, v->prev_ns);
    c_fake->argv[1] = createStringObject(old,strlen(old));
    c_fake->argv[2] = c->argv[1]; 
    sds ren = sdsnew("rename");
    c_fake->cmd = lookupCommand(ren);
    c_fake->cmd->proc(c_fake);
    DEBUG_PRINT(("Updated key (namespace) from %s to %s\n", 
                 old, (char*)c_fake->argv[2]->ptr));

    zfree(c_fake->argv[1]);
    zfree(c_fake->argv);
    zfree(c_fake);
    sdsfree(ren);
    free(old);
}


/* checks if rename is necessary then performs it (for nargs args) .*/
void kvolve_check_rename(redisClient * c, int nargs){

    int i;
    robj * o;
    struct version_hash * v = kvolve_version_hash_lookup((char*)c->argv[1]->ptr);

    /* return immediately if there is no chance of ns change */
    if(!v || !v->prev_ns)
        return;

    redisClient * c_fake = createClient(-1);
    c_fake->db = c->db;
    c_fake->argc = 2;
    c_fake->argv = zmalloc(sizeof(void*)*2);

    for (i=1; i < nargs; i++){
        c_fake->argv[1]= c->argv[i];
        o = kvolve_get_db_val(c_fake);
        if (!o)
            continue;

        // strings stored as ints don't have vers. Check for rename manually.
        if (o->type == REDIS_STRING && o->encoding == REDIS_ENCODING_INT){
            kvolve_namespace_update(c_fake, v);
        } else if(strcmp(o->vers, v->versions[v->num_versions-1])!=0){
            kvolve_namespace_update(c_fake, v);
        }
    }
    zfree(c_fake->argv);
    zfree(c_fake);
}

/* THIS IS THE UPDATE FUNCTION. See header for documentation */
void kvolve_check_update_kv_pair(redisClient * c, int check_key, robj * o, int type, double * s){

    int i, key_vers = -1, fun;
    struct version_hash * v;

    /* Make sure that we're not here because of user update code (kvolve_user_call)*/
    if (upd_fun_running == 1)
        return;

    v = kvolve_version_hash_lookup((char*)c->argv[1]->ptr);
    if(v == NULL) return;

    /* If the object wasn't passed in (set type, not string type),
     * then look it up (as a robj with version info) */
    if (!o){
        o = kvolve_get_db_val(c);
        if (!o) return;
    }

    /* String types that have integer values don't have versions because redis
     * uses shared.integer[val] objects to encode these.  (Because the values may
     * be shared by multiple keys, there's no safe way to store the version as they
     * may not be consistent.) However, the keys could still be renamed, check for
     * this, then return. */
    if (o->type == REDIS_STRING && o->encoding == REDIS_ENCODING_INT){
        kvolve_check_rename(c, 2);
        return;
    }

    /* Check to see if the version is current, if so, return. */
    if (strcmp(o->vers, v->versions[v->num_versions-1])==0)
        return;

    /* Key is present at an older version. Time to update, get version. */
    upd_fun_running = 1;
    for (i = 0; i < v->num_versions; i++){
        if (strcmp(v->versions[i], o->vers) == 0){
            key_vers = i;
            break;
        }
    }
    
    /* check if we need to rename the key based on a new namespace */
    if(check_key && v->info[key_vers+1] && 
                 (strcmp(v->info[key_vers+1]->from_ns, v->ns)!=0)){
        kvolve_namespace_update(c, v);
    }

    /* call all update functions */
    for ( ; key_vers < v->num_versions-1; key_vers++){
        /* in some cases, there may be multiple updates */
        if (!v->info[key_vers+1]){
            printf("Warning: no update functions for %s:%s\n", 
                   v->ns, v->versions[key_vers+1]); 
            o->vers = v->versions[key_vers+1];
            continue;
        }
        for (fun=0; fun < v->info[key_vers+1]->num_funs; fun++){
            char * key = (char*)c->argv[1]->ptr;
            char * val = (char*)o->ptr;
            size_t val_len = sdslen((sds)o->ptr);
            /* next line calls the update func (mods key/val as specified): */
            v->info[key_vers+1]->funs[fun](&key, (void*)&val, &val_len);

            if (check_key && (key != (char*)c->argv[1]->ptr)){
                /* The key will automatically be renamed if a namespace change
                 * is specified in 'struct version_hash'.  However, this gives the user a
                 * chance to do some further custom modifications if necessary. */ 
                DEBUG_PRINT(("Updated key (custom) from %s to %s\n", 
                             (char*)c->argv[1]->ptr, key));
                sdsfree(c->argv[1]->ptr); // free old memory
                c->argv[1]->ptr = sdsnew(key); // memcpy's key (user alloc'ed)
                free(key); // free user-update-allocated memory
                /* This will write the user-modified key to disk */
                kvolve_namespace_update(c, v);
            }
            if (val != (char*)o->ptr){
                DEBUG_PRINT(("Updated value from %s to %s\n", (char*)o->ptr, val));
                if (type == REDIS_STRING){
                    sdsfree(o->ptr);
                    o->ptr = sdsnewlen(val, val_len);
                    free(val);
                    /* This will notify any client watching key (normally called 
                     * automatically, but we bypassed by changing val directly */
                    signalModifiedKey(c->db,o);
                    server.dirty++;
                } else if (type == REDIS_SET){
                    kvolve_update_set_elem(c, val, &o);
                } else if (type == REDIS_ZSET){
                    kvolve_update_zset_elem(c, val, &o, *s);
                } else {
                    printf("UPDATE NOT IMPLEMENTED FOR TYPE %d\n", type);
                    assert(0); //TODO impl.
                }
            }
        }
        /* Update the version string in the key to match the update we just did.*/
        o->vers = v->versions[key_vers+1];
    }
    upd_fun_running = 0;
}

void kvolve_update_set_elem(redisClient * c, char * new_val, robj ** o){

    sds cmd = NULL;
    robj * new;
    /* add new */
    redisClient * c_fake = createClient(-1);
    c_fake->db = c->db;
    c_fake->argc = 3;
    c_fake->argv = zmalloc(sizeof(void*)*3);
    c_fake->argv[1] = c->argv[1];
    new = createStringObject(new_val,strlen(new_val));
    c_fake->argv[2] = new;
    cmd = sdsnew("sadd");
    c_fake->cmd = lookupCommand(cmd);
    sdsfree(cmd);
    c_fake->cmd->proc(c_fake);

    /* delete old */
    c_fake->argv[2] = *o;
    cmd = sdsnew("srem");
    c_fake->cmd = lookupCommand(cmd);
    sdsfree(cmd);
    c_fake->cmd->proc(c_fake);

    zfree(c_fake->argv);
    zfree(c_fake);
    *o = new;
}

void kvolve_update_zset_elem(redisClient * c, char * new_val, robj ** o, double s){

    sds ren = NULL;
    robj * new, *scoreobj;
    char output[50];

    snprintf(output,50,"%f",s);

    /* add new */
    redisClient * c_fake = createClient(-1);
    c_fake->db = c->db;
    c_fake->argc = 4;
    c_fake->argv = zmalloc(sizeof(void*)*3);
    c_fake->argv[1] = c->argv[1];
    new = createStringObject(new_val,strlen(new_val));
    scoreobj = createStringObject(output,strlen(output));
    c_fake->argv[2] = scoreobj;
    c_fake->argv[3] = new;
    ren = sdsnew("zadd");
    c_fake->cmd = lookupCommand(ren);
    sdsfree(ren);
    c_fake->cmd->proc(c_fake);

    /* delete old */
    c_fake->argv[2] = *o;
    c_fake->argc = 3;
    (*o)->encoding = REDIS_ENCODING_RAW;
    ren = sdsnew("zrem");
    c_fake->cmd = lookupCommand(ren);
    sdsfree(ren);
    c_fake->cmd->proc(c_fake);

    zfree(c_fake->argv);
    zfree(c_fake);
    zfree(scoreobj);
    *o = new; //TODO check freeing
}

void kvolve_update_all_zset(redisClient * c){

    robj * o = kvolve_get_db_val(c);
    struct version_hash * v = kvolve_version_hash_lookup((char*)c->argv[1]->ptr);
    /* return if object isn't present or is already current */
    if(!o || strcmp(o->vers, v->versions[v->num_versions-1])==0)
        return;
    if(o->encoding == REDIS_ENCODING_ZIPLIST){
        DEBUG_PRINT(("Type %d not implemented for zset\n", o->encoding)); //TODO
        return;
    }

    unsigned char *p = ziplistIndex(o->ptr,0);
    unsigned char *vstr;
    unsigned int vlen;
    long long vll;
    robj * elem;
    int first = 1;
    int i = 0;
    int zset_len = zsetLength(o);
    double * score_array = calloc(zset_len, sizeof(double));
    robj ** robj_array = calloc(zset_len, sizeof(robj*));

    // iterate over the zset and get the objects/scores
    while(p) { //db.c:515
        ziplistGet(p,&vstr,&vlen,&vll);
        //TODO impl score update?
        if(vstr){
            elem = createStringObject((char*)vstr,vlen);
            elem->vers = o->vers;
            elem->type = o->type;
            elem->encoding = o->encoding;
            p = ziplistNext(o->ptr,p);
            ziplistGet(p,&vstr,&vlen,&vll);
            score_array[i] = zzlGetScore(p);
            robj_array[i] = elem;
            i++;
        }
        p = ziplistNext(o->ptr,p);
    }
    // now modify the zset
    for(i=0; i<zset_len; i++){
        kvolve_check_update_kv_pair(c, first, robj_array[i], o->type, &score_array[i]);
        zfree(robj_array[i]);
        first = 0;
    }
    free(score_array);
    free(robj_array);

    o->vers = v->versions[v->num_versions-1];
}


void kvolve_prevcall_check(void){
    if(kvolve_set_version_fixup != NULL)
        kvolve_newset_version_setter();
    else if(kvolve_zset_version_fixup != NULL)
        kvolve_newzset_version_setter();

}

void kvolve_newset_version_setter(void){
    robj * o, * key;
    setTypeIterator *si;
    struct version_hash * v;
    v = kvolve_version_hash_lookup(kvolve_set_version_fixup);
 
    if(v){
        key = createStringObject(kvolve_set_version_fixup, strlen(kvolve_set_version_fixup));
        o = lookupKeyRead(prev_db, key);
        zfree(key);
        /* set the version for the set object */
        o->vers = v->versions[v->num_versions-1];
        /* only store the version in the set elements if the encoding supports it. */
        if(o->encoding == REDIS_ENCODING_INTSET){
            free(kvolve_set_version_fixup);
            kvolve_set_version_fixup = NULL;
            return;
        }
        si = setTypeInitIterator(o);
        robj * e = setTypeNextObject(si);
        while(e){
            e->vers = v->versions[v->num_versions-1];
            e = setTypeNextObject(si);
        }
    }
    free(kvolve_set_version_fixup);
    kvolve_set_version_fixup = NULL;

}

void kvolve_newzset_version_setter(void){
    robj * o, *key;
    struct version_hash * v;
    v = kvolve_version_hash_lookup(kvolve_zset_version_fixup);
    if (v){
        key = createStringObject(kvolve_zset_version_fixup, strlen(kvolve_zset_version_fixup));
        o = lookupKeyRead(prev_db, key);
        zfree(key);
        /* set the version for the zset object */
        o->vers = v->versions[v->num_versions-1];
    }
    free(kvolve_zset_version_fixup);
    kvolve_zset_version_fixup = NULL;

}

void kvolve_new_version(redisClient *c, int type){
    if(type == REDIS_SET){
        kvolve_set_version_fixup = malloc(sdslen(c->argv[1]->ptr)+1);
        strcpy(kvolve_set_version_fixup, (char*)c->argv[1]->ptr);
    } else if (type == REDIS_ZSET){
        kvolve_zset_version_fixup = malloc(sdslen(c->argv[1]->ptr)+1);
        strcpy(kvolve_zset_version_fixup, (char*)c->argv[1]->ptr);
    }
    prev_db = c->db;
}

#define __GNUC__  // "re-unallow" malloc

