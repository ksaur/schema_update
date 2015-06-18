#ifndef _KVOLVE_UPD_H
#define _KVOLVE_UPD_H


/* This API call allows the user to call redis in the update function.
 *    Ex: kvolve_user_call("set order:222 wwwww");
 */
void kvolve_user_call(char * userinput);


/* This is the typedef for the function prototype that the user must write.
 *    Ex: void test_fun_1(char ** key, void ** value, size_t * val_len){...}
 *
 *  @key : A modifiable pointer to the key.  If the user specifies a namespace
 *         change in the update info, that namespace change will be applied automatically.
 *         In case of a namespace change, @key will be the already-modified key.
 *         Note: No user-written function is necessary to update namespaces unless
 *            additional modifications are necessary. This parameter allows the user
 *            to do some additional changes to a specific key if desired.
 *
 *         If a change to the key is desired, set "*key" in this function.
 *
 *  @value : A modifiable pointer to the data.  If a change to the value is
 *         desired, set "*value" in this function.
 *
 *  @val_en : The modifiable length of the data. This is necessary because not all @value
 *         will be null-terminated (Ex: binary file data).  If a change to the value is
 *         performed, this length must be updated by setting *val_len to the new length.
 */
typedef void (*kvolve_update_kv_fun)(char ** key, void ** value, size_t * val_len);



/* This structure forms the linked list that stores the user-supplied update data */
struct kvolve_upd_info{
  char * from_ns;
  char * to_ns;
  char * from_vers;
  char * to_vers;
  kvolve_update_kv_fun * funs;
  int num_funs;
  struct kvolve_upd_info * next;
};

#endif
