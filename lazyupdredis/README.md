# **Internals of Lazy Update Redis (LUR) with JSON**

For information on usage and the DSL, see the <a href="../README.md">README</a> up one directory.  This README describes the lazy update implementation and all the fun that goes with it.

![flow diagram goes here](../doc/flow.jpeg)
This is a very simplified diagram of the basic control flow.  (Actual a lot more version checking, concurrency, etc.)




### **Versioning**

##### Namespaces

Lazy Update Redis (LUR) uses namespaces to track versioning of keyspaces. This is useful so that LUR can tell which specific keys an update may apply to, rather than having to worry about updating all of the keys in the database.  The namespace is separated from the main keyname with a colon (```:```).  This namespace practice is a common preferred practice as documented in the Redis manual (under "<a href="http://redis.io/topics/data-types-intro#redis-keys">Redis keys</a>").

For example, a user might have some keys describing edge attributes with namespace ```edgeattr```, and some keys describing nodes with namespace ```node```:
```
edgeattr:n1@n9, edgeattr:n2@n3, edgeattr:n8@n10, edgeattr:n4@n1, ...
node:n1, node:n2, node:n3, ...
```


The first host that connects to a new namespace establishes that namespace, with a list of tuples of (```namespace```, ```version_name```).  For example, say a client connects as follows:
```python
r1 = lazyupdredis.connect([("node", "ver0"), ("edgeattr", "v0")])
```
This establishes the namespaces of ```node``` and ```edgeattr```.   Any additional hosts that attempt to connect to these namespaces must connect at ```ver0``` and ```v0``` respectively.

If a client tries to connect at a version not yet seen by Redis, it will be rejected.  As updates are applied, the version is updated to match a tag from the DSL,
where updates are labeled by their versions.  

A programmer is allowed to update any subset of namespaces.  Say a programmer applies the following update (by calling ```r1.do_upd("update_1.dsl")```):
```
# file update_1.dsl
for edgeattr:* v0->v1 {
# code here as described in DSL doc
};
```
Globally in Redis, this will bring the version of namespace ```edgeattr``` up to version ```v1```.  The namespace ```node``` will still be at ```ver0```.  (The keys are not yet updated to the new versions; this is done lazily.) 

The client that called the update (in this case ```r1```) will automatically be brought up to the versions that are in the updates it calls (```r1``` is now at ```v1``` for ```egdeattr``` and still at ```ver0``` for ```node```).  **TODO**: *This is not quite how things should be, but there's a bootstrapping problem about what/where calls the update.  This is currently magically assuming that the client updates to the new version after calling ```do_upd```*

Any new client that tries to connect must now connect at the current versions, or it will be rejected.  In this example, new clients should connect as:
```python
r2 = lazyupdredis.connect([("node", "ver0"), ("edgeattr", "v1")])
```
New clients can choose to connect to only a subset of existing namespaces, or create new namespaces, but they cannot connect to any other versions of the current namespaces.


##### No namespaces

If a Lazy Update Redis user chooses to not modify their keys, and does not prefix the keys with any ```namespace:``` sequence, the user must connect to a default namespace of ```*``` which is applied to all keys.  Note that the user must still provide a version number:
```python
#  connect to Redis using a default namespace
r = lazyupdredis.connect([("*", "v1.0")])
```
Now, when a user requests an update, all keys will be updated to the new version, and the data will be changed only if the DSL file matches.

For example, say a Lazy Redis User has some keys with no namespace:
```
this_one_key, some_other_entry, total_nonsense_schema, weird_name_here, some_other_nonsense
```
Then, if the user wants to update some of the keys based on glob matching, they supply a dsl file:
```
# file update_1.dsl
for *nonsense* v1.0->v1.1 {#some code here};
```
then all keys that contain the word nonsense (```total_nonsense_schema, some_other_nonsense```) will have the code in the DSL rule above above applied to the value, but **all** keys will be updated from ```v1.0->v1.1```.  (This adds overhead, so having namespaces is the more efficient way forward.)


### **The Update Process**

When a programmer calls for an update with the ```do_upd('dslfilename')``` command, Lazy Update Redis stores part of DSL file for use by other clients, and also generates the update code from the DSL for the client that requested the update.  

##### Processing the DSL file:
There are two types of DSL entries:

- ##### The "add" keys

  *Lazy Update Redis will compile the ```add``` commands and execute them immediately to create the new keys.  The ```add``` DSL code is not added to Redis.*

 Keys that the DSL writer wants to *add* are added non-lazily at update time...  This is because it would be difficult to track which keys have been added and which haven't, since normally these are  tracked for existing keys using a versioning string.  Adding an additional data structure to track which keys have been added and which haven't adds almost as much overhead as simply just adding the keys.  (**TODO:** However, for adding very large amounts of keys and scaling things up, this may no longer be true.)  

- ##### The "for" keys

 *Keys that the DSL writer wants to* update *using the ```for``` command are queued up for lazy updates.  This DSL code is stored in Redis for use by other clients*.
 
 The queued-up updates are stored in a per-client internal data structure called ```upd_dict``` the is described below.
 
After the update is requested and the keys are added or/and the lazy updates are queued up, execution returns to normal for the calling client.

##### The generated code/```upd_dict```

When the user requests an update and provides the DSL file, Lazy Update Redis generates the update functions and information to be loaded as a dynamic module.

The actual generated code is shown in full in this <a href ="../tests/example/">directory</a>. 
Here is the basic idea about how the generated module is used:
```python
# generated module myupdate.py
#
# (....functions for updating here...)
# (def group_1_update_category(.....), etc)

def get_update_tuples():
    return [('key:[1-4]', ['upd_fun_1', ..., 'upd_fun_x'], 'key', 'ver0', 'ver1'), ...]
```
This ```get_update_tuples()``` function contains all of the information about the update functions in the generated file and to which keys to apply the update.  Then, during update, the generated function is called *automatically* by Lazy Update Redis  as follows:

```python
m = __import__ (upd_module_name) # in this case myupdate.py
get_update_tuples = getattr(m, "get_update_tuples") # Gets a list of the functions to call
tups = get_update_tuples() # This calls the function in the new module
for (glob, funcs, ns, version_from, version_to) in tups:
    # loop through and load this all up into upd_dict
```

As you can see from the generated code and the load function, the ```upd_dict``` contains a list of:
* **keyglob** - This may be just ```namespace:*```, or something trickier with a range ```[]``` or a ```?```.  This is different from namespace in that it might just be a subset of keys in the namespace.
* **functions** - This is a set of functions to call that match the keyglob.  *These are all loaded up and ready to call.*
* **namespace** - This is stored separately from keyglob because things get a bit trickier when there is no namespace.  Keys must first match the namespace, and then they are matched against the keyglob.
* **version_from** - This update applies only to keys at this version
* **version_to** - This will update the keys to this version.

### **Lazy Update Redis entries** 
This section describes the actual Redis data keys and additional bookkeeping keys.

##### How the keys are actually stored:
LUR adds/removes a version tag as the user calls ```get```/```set```, transparently to the user.  Keys are actually stored in Redis as: ```version|namespace:value```.  For example, in a key named ```edgeattr:n2@n3``` at version ```v0```, the key will be stored in lazy Redis as ```v0|edgeattr:n2@n3```.  In the non-namespace case, the keys are stored with the version only such as ```v1.0|some_other_entry```.  Lazy Update Redis then checks to make sure the default namespace was declared to allow these keys.  More information on how ```get```/```set``` actually works is described in detail below.

##### Bookkeeping keys:
In addition to the actual data that a user my request to store in Redis, LUR stores some additional data for its internal bookkeeping:

* ```UPDATE_DSL_STRINGS``` - This is a **single** Redis hash key.  Each sub-key of this hash is ```(v0, v1, edgeattr)```, and the value is the DSL code (string) necessary to build the update between the two versions for the namespace.  This is used to build update dictionaries (described later) for each LUR client. Ex:

 ```python
 # called by Lazy Update Redis
 
 # returns "for edgeattr:* v0->v1 {...code ...};"  :
 self.hget("UPDATE_DSL_STRINGS",  "(v0, v1, edgeattr)") 
 
 # returns "for sillyns:* v1.0->v1.1 {#some code here};"  :
 self.hget("UPDATE_DSL_STRINGS",  "(v1.0, v1.1, sillyns)") 
 ```
* ```UPDATE_VERSIONS_(namespace)``` for each namespace - This is a Redis list key for EACH namespace of all the versions for the namespace.  For example:

 ```python
  # returns a list of all versions ["v0", "v1"] for namespace "edgeattr".
  self.lrange("UPDATE_VERSIONS_edgeattr", 0, -1) # -1 means end of list
  
    # returns a list of all versions ["v1.0", "v1.1"] for namespace " sillyns".
  self.lrange("UPDATE_VERSIONS_sillyns", 0, -1) # -1 means end of list
 ```

** NOTE:** These bookkeeping functions are never called by the user directly, and are hidden from the user on queries.

##### Keeping up-to-date

For each call to Lazy Update Redis, a O(1) lookup in Redis is performed to the bookkeeping keys (```UPDATE_DSL_STRINGS``` / ```UPDATE_VERSIONS_(namespace)```), to ensure that, the local copy of ```upd_dict```  local copy is up-to-date with the DSL stored in Redis.  (The local copy of```upd_dict``` is necessary because of module loading.)

Also, each time a new client connects, Lazy Update Redis verifies the currentness of the namespace version info requested by the client (described above in *Versioning*), and then Lazy Update Redis builds up its local ```upd_dict``` by pulling the DSL from Redis for all existing updates.

### **Lazy Updates**

Keys are updated only as they are requested.  This applies primarily to ```gets```, but some checking is also necessary for ```sets```.  Lazy updates are implemented by subclassing  <a href="https://github.com/andymccurdy/redis-py/blob/bc61eb925af5de3317937529413cca4a49c4cd3b/redis/client.py#L281">class StrictRedis</a> (by Andy McCurdy).  You can read all about the inherited/override methods in the <a href="../doc/lazyupdredis.lazyupdredis.LazyUpdateRedis-class.html"> pydoc</a> for LazyUpdateRedis.

##### set
This is the simpler of the two lazy functions.  
- First, LUR checks to make sure that the client is at the most current version of the namespace for the requested key.  
 - If not, it raises a ```DeprecationWarning```.  (The client may choose to catch this and gracefully update.)
- Since the client has been asserted to be at the current version, assuming the versioning was established correctly by the programmer, the set-to value should match the current schema.
 - LUR then sets the key to the provided value, and deletes any previous versions of the key, which brings the key up-to-date if necessary.
 - There is no need to apply the update function, because the user is setting the value specifically, blowing away the old data. 

##### get
This function actually performs lazy updates as necessary.
- First, LUR checks to make sure that the client is at the most current version of the namespace for the requested key. 
 - If not, it raises a ```DeprecationWarning```. (The client may choose to catch this and gracefully update.)
- LUR then checks to see if the requested key is already at the current version.  
 - If so, it returns the value and does nothing else.  (This should happen in the majority of the cases, which minimizes overhead.)
- If LUR does not find a key at the current version, then it tries to get a matching key at a previous version by iterating backwards through the version list from most current to least current.  
 - If no key is found, it returns None
- When a key is found at a previous version, LUR notes at which version, and looks up the update(s) to apply to bring the key up to the current version for the key's namespace.
 - If the client is at the current version, it is guaranteed to have the proper update modules loaded in its local ```upd_dict```. LUR then loops through the update functions (first matching the namespace, and then matching the keyglob), applying oldest to newest.
- After all of the updates are applied, LUR returns the updated value for the requested key.

All of this assumes that no ```WatchError``` occurs, in the case of concurrency violation, described next.  If a watch error occurs, the functions return ```False```.  **TODO:** False distinguishes from returning None, meaning that no such key exists.  Is this the best option?  Or should we not catch the ```WatchError``` and have the application writer check for that instead?

### **Concurrency** 
Redis provides some transaction methods described in the <a href = "http://redis.io/topics/transactions"> user manual</a>.  Lazy Update Redis uses these concurrency mechanisms to ensure correctness in both the bookkeeping data (data used to facilitate updates, which may be used by multiple clients) and the actual data that is being lazily updated.

These commands are (as described in <a href="http://redis.io/commands#transactions"> Redis doc</a>):
- **WATCH** - *"Marks the given keys to be watched for conditional execution"*. Note that this can conveniently be used to mark a key that does not yet exist, such as "v1|edge:n2", to prevent multiple updates 
- **MULTI** - *"Marks the start of a transaction block. Subsequent commands will be queued for atomic execution using EXEC."* 
- **EXEC** - "*Execute all commands issued after MULTI*".  This is conditional...if any of the "watched" keys are modified by a different client, the program throws a (caught) ```WatchError```

**The python wrappers of these are described <a href="https://github.com/andymccurdy/redis-py#pipelines">here</a>.**

These commands are fed into a pipeline, and either the entire pipeline is executed, or none of it is; it is a transaction.  There are two main places where LUR uses concurrency mechanisms: modifying the bookkeeping keys, and *updating* the actual data keys.  



##### Concurrency control usage #1: Versioning/Loading Updates
The goal of concurrency here is to allow modification of  Redis' lists of versions only when successfully loading the update information, and only when not interrupted by other clients that may be attempting to apply an update.

Here, LUR must protect ```UPDATE_DSL_STRINGS``` and also the list for the namespace(s) being modified  (```UPDATE_VERSIONS_(namespace)``` for each namespace).  LUR calls creates a pipeline for the transaction, calls ```WATCH``` on these keys,  calls ```MULTI``` to prepare the pipeline, puts the ```set``` calls into the pipeline, and then calls ```EXEC```.

If an error occurs the update loading function returns ```None```. **TODO, what should we return here...False? Retrying doesn't make sense, since the update should only be called once.**

For additional details, see <a href="https://github.com/plum-umd/schema_update/blob/921e12476188cbd73987a3c0c60160a1486c52a1/lazyupdredis/lazyupdredis.py#L182">the code</a>.

##### Concurrency control usage #2: Updating Key/Values
When updating the values, LUR removes the old version.  Here, transactions are used (by watching the updated key at old/new versions) to: 
- Ensure that an update only happens once, and 
- When an update happens, old keys are also removed....or both the update/remove are aborted.
 
For additional details, see <a href="https://github.com/plum-umd/schema_update/blob/921e12476188cbd73987a3c0c60160a1486c52a1/lazyupdredis/lazyupdredis.py#L320">the code</a>.



(*Note:* Lazy Update Redis does not automatically handle read/write collisions that would occur in the applications regardless of the use of LUR...those are left up to the application writer to write normal Redis concurrency as necessary when using any database in a distributed system.)

### **Updating all the keys right now (not lazily)**
If the user wants to update all of the keys at once (without waiting for laziness, for example, if you want to to force stale entries to be updated), then the user can call ```r.do_upd_all_now()``` to force all keys to update.  This function uses Redis' ```scan``` <a href = "http://redis.io/commands/scan#scan-guarantees">guarantees</a> to ensure that "A full iteration always retrieves all the elements that were present in the collection from the start to the end of a full iteration.".  This is particularly important, since the update changes the keyname when it changes the version string as part of the keyname.

To avoid blocking in the primary client application, the programmer may start a new thread and then call the ```do_upd_all_now()``` function; Redis continues to operate as normal during update.

TODO: How to notify all clients to clean out their update dictionaries?  (They will never be used again...) At this point, do we remove the old version and old DSL from Redis?  After this function runs, we should be able to essentially wipe out all of the DSL from Redis (since no new entries at the old version can be added once an update is loaded).  Should we also wipe out all of the old versions from the namespace lists?



