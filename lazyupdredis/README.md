# **Internals of Lazy Update Redis with JSON**

(For information on usage and the DSL, see the README up one directory.  This readme is on the lazy update implementation and all the fun that goes with it.)

### **Versioning**

##### Namespaces

Lazy Redis Updates uses namespaces to track versioning of keyspaces.  The namespace is separated from the main keyname with a colon (```:```).  This namespace practice is a common prefered practice as documented in the redis manual (under "<a href="http://redis.io/topics/data-types-intro">Redis keys</a>").

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

If a client tries to connect at a version not yet seen by Redis, it will be rejected.  As updates are applied, the version is updated from the dsl.

Inside the DSL, updates are labeled by their  versions.  A programmer is allowed to update any subset of clients.  Say a programmer applies the following update (by calling ```r1.do_upd("update_1.dsl")```):
```
# file update_1.dsl
for edgeattr:* v0->v1 {#somecode};
```
Globally in Redis, this will bring the version of namespace ```edgeattr``` up to version ```v1```.  The namespace ```node``` will still be at ```ver0```.   

The client that called the update (in this case ```r1```) will automatically be brought up to the versions that are in the updates it calls (```r1``` is now at ```v1``` for ```egdeattr``` and still at ```ver0``` for ```node```).

Any new client that tries to connect must now connect at the current versions, or it will be rejected:

```python
r2 = lazyupdredis.connect([("node", "ver0"), ("edgeattr", "v1")])
```

##### No namespaces

If a Lazy Update Redis user chooses to not modify their keys, and does not prefix the keys with any ```namespace:``` sequence, the user must connect to a default namespace of ```*``` which is applied to all keys.  Note that the user must still provide a version number
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
then all keys that contain the word nonsense (```total_nonsense_schema, some_other_nonsense```) will have the code in the DSL rule above above applied to the value, but **all** keys will be updated from ```v1.0->v1.1```.


### **How the keys are actually stored**
Keys are actually stored in redis as: ```version|namespace:value```.  For example, in the edgeattr example above, keys will be stored in lazy redis as ```v0|edgeattr:n2@n3```.  In the non-namspace case, the keys are stored with the version only such as ```v1.0|some_other_entry```.  Lazy Update Redis then checks to make sure the default namespace was declared to allow these keys.

These versions are added and removed on the fly behind the scenes by Lazy Update Redis so that Redis can be used as normal by clients, as described below.

### **The Update process**

When a programmer calls for an update with the ```doupd('dslfilename')``` command, Lazy Update Redis stores part of DSL file for use by other clients, and also generates the update code for the client that requested the udpate.  

#### Processing the DSL file:
There are two types of DSL entries:

- ##### The "add" keys

  *Lazy Update Redis will compile the ```add``` commands and execute them immediately to create the new keys.  The ```add``` DSL code is not added to redis.*

 Keys that the DSL writer wants to *add* are added non-lazily at update time...  This is because it would be difficult to track which keys have been added and which haven't, since normally these are  tracked for existing keys using a versioning string.  Adding an additional datastructure to track which keys have been added and which haven't adds almost as much overhead as simply just adding the keys.  (**TODO:** However, for adding very large amounts of keys and scaling things up, this may no longer be true.)  

- ##### The "for" keys

 *Keys that the DSL writer wants to **update** using the ```for``` command are queued up for lazy updates.  This DSL code is stored in redis for use by other clients*.
 
 The queued-up updates are stored in a per-client internal data structure called ```upd_dict``` the is described below.
 
After the update is requested and the keys are added or/and the lazy updates are queued up, execution returns to normal for the calling client.

### The generated code/```upd_dict```

When the user requests an update and provides the DSL file, Lazy Update Redis generates the update functions and information to be loaded as a dynamic module.

The actual generated code is discussed in full in this <a href ="../tests/example/README.md">readme</a>. 
Here is the basic idea about how the generated module is used:
```python
# generated module myupdate.py
#
# (....functions for updating here...)
# (def group_1_update_category(.....), etc)

def get_update_tuples():
    return [('key:[1-4]', ['group_1_update_category', 'group_1_update__id', 'group_1_update_order'], 'key', 'ver0', 'ver1'), ...]
```
This ```get_update_tuples()``` function contains all of the information about the update functions in the generated file and to which keys to apply the update.  Then, during update, the generated function is called *automatically* by Lazy Update Redis  as follows:

```python
m = __import__ (upd_module_name) # in this case myupdate.py
get_update_tuples = getattr(m, "get_update_tuples") # This gets a list of the functions to call
tups = get_update_tuples() # This calls the function in the new module
for (glob, funcs, ns, version_from, version_to) in tups:
    # loop through and load this all up into upd_dict
```

As you can see from the generated code and the load function, the ```upd_dict``` contains a list of:
* **keyglob** - This may be just ```namespace:*```, or something trickier with a range ```[]``` or a ```?```.  This is different from namespace in that it might just be a subset of keys in the namespace.
* **functions** - This is a set of functions to call that match the keyglob.  *These are all loaded up and ready to call.*
* **namespace** - This is stored separately from keyglob because things get a bit trickier when there is no namespace.  Keys must first match the namespace, and then they are matched agaisnt the keyglob.
* **version_from** - This update applies only to keys at this version
* **version_to** - This will update the kesy to this version.

##### **Keeping up-to-date**

For each call to Lazy Update Redis, a O(1) lookup in Redis is performed, to ensure that, the local copy of ```upd_dict```  local copy is up-to-date with the DSL stored in Redis.  (The local copy of```upd_dict``` is necessary because of module loading.)

Also, each time a new client connects, Lazy Update Redis verifies the currentness of the namespace version info requested by the client (described above in *Versioning*), and then Lazy Update Redis builds up its local ```upd_dict``` by pulling the DSL from Redis for all existing updates.

### **Lazy Updates**
##### sets
##### gets

### **Concurrency** 
Redis provides some transaction methods described in the <a href = "http://redis.io/topics/transactions"> user manual</a>.  Lazy Update Redis uses these concurrency mechanisms to ensure correcteness in both the bookkeeping data (data used to facilitate updates, which may be used by multiple clients) and the actual data that is being lazily updated.
##### list concurrency


##### update concurrency

### **Pull thread**
*TODO implement!!!*

