schema_update
=============

Requires:
Jansson_  (jansson.h), HiRedis_ (hiredis.h)

You'll also need to be able to run Redis_.

Program: 

* jsondiff_/ - This directory has the code to diff two .json schemas.  It generates a C source code file using calls to jansson to perform the diff to the json schema.


* redis_schema_upd_/ - This directory has the code to take the diff file you generate with jsondiff, connect to redis, and perform the diff over all the keys


* redis_schema_upd/redis_source_/ - This contains a makefile to link with redis...not currently used...in progress..

.. _Jansson: http://www.digip.org/jansson/
.. _HiRedis: https://github.com/redis/hiredis
.. _Redis: http://redis.io/download
.. _jsondiff: https://github.com/plum-umd/schema_update/jsondiff/
.. _redis_schema_upd: https://github.com/plum-umd/schema_update/redis_schema_upd/
.. _redis_source: https://github.com/plum-umd/schema_update/redis/redis_source/

