#ifndef _KVOLVE_UPD_H
#define _KVOLVE_UPD_H

/*****************************************************
 Connecting to Redis-KVolve:

    Connect to Redis as normal, and then immediately after connecting call:
       Ex: client setname order@v0,user@u0
    In the form of [namespace]@[version],[namespace]@[version]

*****************************************************/


/*****************************************************
 Writing the Update Function:

	To write the update, the update-writer uses one function call to
      describe each update (version info), with optional parameters of update
      functions to perform along with updating the version info.

	The specifics are described below, but here is a brief example of appending
      a string "UPDATED" to all values of keys in the namespace "order":

      -------------------------------------------------------------------
      void test_fun_updval(char ** key, void ** value, size_t * val_len){  // The update function prototype
          size_t s = strlen("UPDATED")+strlen((char*)*value)+1;
          char * cons = calloc(s,sizeof(char));
          strcat(cons, *value);
          strcat(cons, "UPDATED");
          *value = cons;   // Set the updated value
          *val_len = s;    // Set the updated value length (necessary to allow binary strings)
      }

      void kvolve_declare_update(){  // Place your update calls here
          kvolve_upd_spec("order", "order", "v0", "v1", 1, test_fun_updval);  // This describes the update
      }
      -------------------------------------------------------------------
*****************************************************/

/* This is the typedef for the function prototype that the user must write.
 *    Ex: void test_fun_1(char ** key, void ** value, size_t * val_len){...}
 *
 *    @key : A modifiable pointer to the key.  If the user specifies a namespace
 *           change in the update info, that namespace change will be applied automatically.
 *           In case of a namespace change, @key will be the already-modified key.
 *           Note: No user-written function is necessary to update namespaces unless
 *              additional modifications are necessary. This parameter allows the user
 *              to do some additional changes to a specific key if desired.
 *
 *           If a change to the key is desired, set "*key" in this function.
 *
 *    @value : A modifiable pointer to the data.  If a change to the value is
 *           desired, set "*value" in this function.
 *
 *    @val_en : The modifiable length of the data. This is necessary because not all @value
 *           will be null-terminated (Ex: binary file data).  If a change to the value is
 *           performed, this length must be updated by setting *val_len to the new length.
 */
typedef void (*kvolve_upd_fun)(char ** key, void ** value, size_t * val_len);

/* This function specifies an update.  There must be 1 more calls to this function per update.
 *    Ex: kvolve_upd_specify("order", "order:region", "v0", "v1", upd_fun_name);
 *
 *    @from_ns : The namespace we're updating from. This must have already been
 *           declared by a connecting program.
 *
 *    @to_ns : The namespace we're updating to. This will be equal to @from_ns unless
 *           there is a namespace change
 *    @from_vers : The version we're updating from. This must have already been
 *           declared by a connecting program.
 *    @to_vers : The version we're updating to.  These must be uniquely named.
 *    @n_funs : The number of functions of type kvolve_upd_fun for this update
 *    @... : One or more function pointers to type kvolve_upd_fun.
 */
void kvolve_upd_spec(char *from_ns, char * to_ns, char * from_vers, char * to_vers, int n_funs, ...);

/* This is the function where to place the calls to kvolve_upd_spec.  This will
 * load up all of the update information */
void kvolve_declare_update() __attribute__((constructor));

/* This is an optional helper call that allows the update-writer to call redis
 * in the update function.
 *    Ex: kvolve_upd_redis_call("set order:222 wwwww");
 * //TODO clarify this function.  this currently only works for sets, there is no return type (ex: gets wont work)...maybe implement this...TODO
 */
void kvolve_upd_redis_call(char * userinput);



/*****************************************************
 Compiling the Update Function:

    Compile the above function to a shared object by adding these flags:
       -shared -fPIC -g your_upd_fun_file.c -o your_upd_name.so -ldl -I../redis-2.8.17/src/

    (Make sure to change the correct location of the includes, or install)
*****************************************************/


/*****************************************************
 Calling the Update Function:

    Updates may be requested within the program or outside the program by issuing
    the following command to redis:
       client setname update/your_upd_name.so

	This will automatically advance the namespace for the calling client, all
       other programs connected to the updated namespace must update.

*****************************************************/

#endif
