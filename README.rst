schema_update
=============

**Requires:**

- You'll need to be able to run Redis_.
- 'pip install redis'
- 'pip install json'

**Program:**
   
- src_/
   * decode.py  - A helper library to get rid of unicode (may be deleted later?)
   * do_upd.py - A non-lazy update for redis
   * json_delta_diff.py  - Some nice json diff functions I borrowed from jsondelta_, (thank you Philip J. Roberts)
   * json_patch_creator.py - This is the main file to create the init dsl file and then generate the update functions
- doc_/
   * index.html - documentation for the python functions
- tests_/
   * Examples of loading the db and performing the update
   * example_json_/
      + This directory contains test JSON files
- util_/
   * loadstuff.py - Load up some test data in redis

**The DSL File:**

This is how you tell the patch generator what to generate.  There are 4 commands:

+-------------+-----------------------+-----------+
| Directive   | Pattern               | code      |
+=============+=======================+===========+
| INIT        | key->value, or value  | (yes)     |
+-------------+-----------------------+-----------+
| DEL         | key->value, or value  | (no)      |
+-------------+-----------------------+-----------+
| REN         | oldpath->newpath      | (no)      |
+-------------+-----------------------+-----------+
| UPD         | key->value, or value  | (yes)     |
+-------------+-----------------------+-----------+

* The "directive" column is the action to be performed: initializing a new field, deleting a field, renaming a field, or updating the value contained in a field.
* The "pattern" column consists of a "key" which is a keyglob_ (basically, a regular expression matching the key format), and a "value", which is a json path to the value to be updated.
* The "code" column consists of python code.

See an example_.  Briefly:

::

 for keys key* {  // For all keys in redis beginning with "key"
 INIT ["dob"]: {$out = "01/01/1970"}  // add a top-level JSON field named "DOB" 
                                      // initialized to "01/01/1970"
 };


**Running  (quickly jotting down........):**

1. **start redis:**   (your_redis_dir)/src$ ./redis-server

2. **load some data:** util$ python loadstuff.py ../tests/data/example_jsonbulk/sample.txt

3. **make the DSL template file:** src$ python json_patch_creator.py --t ../tests/data/example_json/sample1.json ../tests/data/example_json/sample2.json  (This will generate the DSL template file 'generated_dsl_init' for you to fill out)

4. **(fill out the 'generated_dsl_init' file, or just use example_json_/\*init\*)**

5. **create dsu.py**: src$ python json_patch_creator.py --d ../tests/data/example_json/sample_init

6. **run the update:** src$ python do_upd.py



.. _Redis: http://redis.io/download
.. _keyglob: http://redis.io/commands/keys
.. _example:    https://github.com/plum-umd/schema_update/blob/master/tests/data/example_json/sadalage_init
.. _src: https://github.com/plum-umd/schema_update/tree/master/src
.. _doc: https://github.com/plum-umd/schema_update/tree/master/doc
.. _tests: https://github.com/plum-umd/schema_update/tree/master/tests
.. _example_json: https://github.com/plum-umd/schema_update/tree/master/tests/data/example_json
.. _util: https://github.com/plum-umd/schema_update/tree/master/util
.. _jsondelta: http://www.phil-roberts.name/json_delta/

