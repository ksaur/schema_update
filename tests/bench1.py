"""
The built-in redis benchmark (redis-bench) is designed to benchmark _redis_, 
not the redis client.  However, the basic idea in this benchmark is the same...
test a large number of gets/sets on a large number of clients.

This benchmark is meant to compare the standard install redis client (pyredis)
against the lazy update redis client (lazyupdredis).
"""
import json
import sys, os
import redis
import random, time, logging
from lazyupdredis import *
from threading import Thread
from time import sleep
from random import randint
sys.path.append("data/example_jsonbulk/")
import sample_generate


def do_updnow(r, unused1, unused2, unused3):
    upd = r.do_upd_all_now("data/example_jsonbulk/sample_1_sadalage_init")
    logging.info("updated" + str(upd))
    return None

def do_lazyupd(r, unused, num_iters, key_range):

    for i in range(num_iters):
        rand1 = str(random.randint(0, key_range))
        r.get("customer:" + rand1)


def do_getset(r, unused, num_getsets, key_range):

    for i in range(num_getsets):
        rand1 = str(random.randint(0, key_range))
        rand2 = str(random.randint(0, key_range))
        r.set("edgeattr:" + rand1, "str"+rand1)
        r.get("edgeattr:" + rand2)
    

def bench(tname, fun_name, num_clients, num_funcalls, keyrange, args):
    """ 
    @param args: used lazyredis.  If no args given, uses unmodified StrictRedis
    @type args: list of tuples [("ns", "vers"), ...]
    
    """

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

    start = time.time()
    thread_arr = list()
    for t_num in range(num_clients):
        if args:
            r = lazyupdredis.connect(args)
        else:
            r = redis.StrictRedis()
        thread = (Thread(target = fun_name, args = (r, t_num, num_funcalls, keyrange)))
        thread_arr.append(thread)
        thread.start()

    for t in thread_arr:
        print "joining: " + str(t)
        t.join()

    end = time.time()
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    return end - start



def main():

#    logging.basicConfig(level=logging.DEBUG)


    # non-hooked redis commands to work as orginally specified
    actualredis = redis.StrictRedis()

    # test get-sets
    actualredis.flushall()
    num_keys = 5000    # the possible range of keys to iterate
    num_funcalls = 5000 # (x2 hits to redis because it's set/get). done over random keys (1 - num_keys)
    num_clients = 5
    print bench("normal_redis_getset", do_getset, num_clients, num_keys, num_funcalls, None)
    actualredis.flushall()
    print bench("lazy_redis_getset", do_getset, num_clients, num_keys, num_funcalls, [("edgeattr", "v0")])


#    # test do all now
#    actualredis.flushall()
#    num_keys = 5000    # keys to add
#    num_funcalls = 1
#    num_clients = 1
#    sample_generate.gen_1_sadalage(num_keys)
#    print bench("RIGHTNOW_redis_sadalage1", do_updnow, num_clients, num_funcalls, num_keys, [("customer", "v0")])
#    print str(len(actualredis.keys("v0*"))) + " keys not updated, ",
#    print str(len(actualredis.keys("v1*"))) + " keys updated."


    # test lazy
    actualredis.flushall()
    r = lazyupdredis.connect([("customer", "v0")])
    num_keys = 5000    # the possible range of keys to iterate
    num_funcalls = 10000 # done over random keys (1 - num_keys)
    num_clients = 5
    sample_generate.gen_1_sadalage(num_keys)
    r.do_upd("data/example_jsonbulk/sample_1_sadalage_init")
    print bench("lazy_redis_sadalage1", do_lazyupd, num_clients, num_funcalls, num_keys, [("customer", "v1")])
    print str(len(actualredis.keys("v0*"))) + " keys not yet updated, ",
    print str(len(actualredis.keys("v1*"))) + " keys updated."


    # test lazy updates on a large scale
 

if __name__ == '__main__':
    main()
