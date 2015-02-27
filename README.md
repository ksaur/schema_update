# **Lazy Update Redis with JSON**

## Requires:

- You'll need <a href ="http://redis.io/download">Redis</a>.  This is basically done by pulling down the tarball:
```
$ wget http://download.redis.io/releases/redis-2.8.19.tar.gz
$ tar xzf redis-2.8.19.tar.gz
$ cd redis-2.8.19
$ make
```
- Running Redis (must be running before you start anything else):
```
$ src/redis-server
```
 
- Also, you'll need some python libraries for the update functionality to build: 
```
$ pip install -r requirements.txt
```

- You must then install the lazy redis update libary:
```
$ sudo python setup.py develop
```

## Your Schema:
This updating tool works for updating string keys that map to JSON values. 

-   **In order to facilitate lazy updating, you must separate your namespace with a colon, such as ```key:333``` or ```edgeattr:n9@n5.``` ** 
  
-   For example, here, ```edgeattr``` is the namespace, and ```edgeattr:*``` is all the keys in that namespace:
```
for edgeattr:* v0->v1 {...more below...};
```

- Redis keys usually follow a standard naming convention, described in the <a href = "http://redis.io/topics/data-types-intro"> Redis doc</a>:

 ```
"Try to stick with a schema. For instance "object-type:id" is a good idea, as in "user:1000". Dots or dashes are often used for multi-word fields, as in "comment:1234:reply.to" or "comment:1234:reply-to""
```

## DSL:
The DSL describes the update

- The basic DSL doc is <a href ="doc">here</a>

- However, it's probably easiest to check out some <a href="tests/data/example_json">contrived examples</a> (see any file in that directory ending in a *_init*)

- The basic DSL format is this:
```
#The basic template
for namespace:keyglob versionfrom->versionto {
COMMAND ["fieldname"] {somepython}
}; #semicolon
```
```
#Such as:
for edgeattr:* v0->v1 {
UPD ["outport"] {$out = 777}
};
```
- The first line is of the format ```for (keylob) version_old->version_new {```, where  <a href ="http://redis.io/commands/KEYS"> keyglob</a> which is a simplified regex (```?, *, []```).


## Connecting to Lazy Update Redis:
Lazy Update Redis operates on namespaces and versions to know which keys have been been updated.  Lazy Update Redis is essentially a series of wrappers around normal redis functions.  When a user requests a key, Lazy Update Redis will determine whether or not that a key is out of date for the namespace version, and perform the update if necessary.

For this to work, the user must connect at a specific namespace and version.  For the example above (```for edgeattr:* v0->v1```), the user has namespace ```edgeattr``` and initial version ```v0```. If, for example, a user additionally has some keys such as ```key:n``` starting at ```ver0``` of an app, start redis as follows:

```python
# connect to Redis
r = lazyupdredis.connect([("key", "ver0"), ("edgeattr", "v0")])
```
Note that this is a list of tuples in the format of ```("namespace", "version")```

**You can now use Lazy Update Redis exactly as you would use normal Redis.**

```python
r.get("key:8282")
```


## Performing the update:

Once you have your DSL file, performing the update takes a single function call, with the DSL file as a parameter:
```python
r.do_upd("data/example_json/lazy_1_init")
```

This command will immediately perform any adding of new keys specified in the update DSL with ```add```, and will queue up the rest of the updates specified with ```for``` in the update DSL to be performed when that key is queried.

----
**Directory/Repo Structure and import files:**
   
- lazyupdredis/
   * **lazyupdredis.py** - This is the wrapper around redis that performs all the lazy stuff
   * **json_patch_creator.py** - This is the main file to create the init dsl file and then generate the update functions
   * decode.py  - A helper library to get rid of unicode (may be deleted later?)
   * json_delta_diff.py  - (Deprecated, here for backward compat) Some nice json diff functions I borrowed from jsondelta for detecting the added/removed json fields automatically (thank you Philip J. Roberts)
- doc/
   * dsl.html - some notes on the DSL for specifying updates.  This is a work in progress
- tests/
   * Examples/tests for loading the db and performing the update
   * data/example_json/
      + This directory contains test JSON files
- util/
   * print_redis.py - A quick way to view all of the content in Redis, for debugging











