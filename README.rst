schema_update
=============

**Requires:**

- You'll need to be able to run Redis_.
- 'pip install redis'
- 'pip install json'

**Program:**

- example_json_/ 
   * This directory contains test JSON files
- jsondiffpatch_generator_/ 
   * decode.py  - A helper library to get rid of unicode (may be deleted later?)
   * do_upd.py - A non-lazy update for redis
   * json_delta_diff.py  - Some nice json diff functions I borrowed from jsondelta_, (thank you Philip J. Roberts)
   * json_patch_creator.py - This is the main file to create the init dsl file and then generate the update functions
- util_/
   * loadstuff.py - Load up some test data in redis



**Running  (quickly jotting down........):**

1. **start redis:**   (your_redis_dir)/src$ ./redis-server

2. **load some data:** util$ python loadstuff.py ../example_jsonbulk/sample.txt

3. **make the DSL template file:** jsondiffpatch_generator$ python json_patch_creator.py --t ../example_json/sample1.json ../example_json/sample2.json  (This will generate the DSL template file 'generated_dsl_init' for you to fill out)

4. **(fill out the 'generated_dsl_init' file, or just use example_json_/\*init\*)**

5. **create dsu.py**: jsondiffpatch_generator$ python json_patch_creator.py --d ../example_json/sample_init

6. **run the update:** jsondiffpatch_generator$ python do_upd.py



.. _Redis: http://redis.io/download
.. _jsondiffpatch_generator: https://github.com/plum-umd/schema_update/tree/master/jsondiffpatch_generator
.. _example_json: https://github.com/plum-umd/schema_update/tree/master/example_json
.. _util: https://github.com/plum-umd/schema_update/tree/master/util
.. _jsondelta: http://www.phil-roberts.name/json_delta/

