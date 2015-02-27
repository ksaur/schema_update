# **Internals of Lazy Update Redis with JSON**

(For information on usage and the DSL, see the README up one directory.  This readme is on the lazy update implementation and all the fun that goes with it.)

### Versioning

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


### How the keys are actually stored
Keys are actually stored in redis as: ```version|namespace:value```.  For example, in the edgeattr example above, keys will be stored in lazy redis as ```v0|edgeattr:n2@n3```.  In the non-namspace case, the keys are stored with the version only such as ```v1.0|some_other_entry```.  Lazy Update Redis then checks to make sure the default namespace was declared to allow these keys.

These versions are added and removed on the fly behind the scenes by Lazy Update Redis so that Redis can be used as normal by clients, as described below.

### The Update process
##### The "for" keys

##### The "add" keys


### Establishing a new connection
##### upd_dict per client
##### lists of namespace versions


##### Generating the code from the stored update


### Lazy Updates
##### sets
##### gets

### Concurrency 
Redis provides some transaction methods described in the <a href = "http://redis.io/topics/transactions"> user manual</a>.  Lazy Update Redis uses these concurrency mechanisms to ensure correcteness in both the bookkeeping data (data used to facilitate updates, which may be used by multiple clients) and the actual data that is being lazily updated.
##### list concurrency


##### update concurrency

### Pull thread
TODO implement!!!

