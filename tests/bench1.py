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


def do_getset(r, unused, num_getsets, key_range, data):

    for i in range(num_getsets):
        rand1 = str(random.randint(0, key_range))
        rand2 = str(random.randint(0, key_range))
        r.set("edgeattr:" + rand1, data)
        r.get("edgeattr:" + rand2)
    

def bench(tname, fun_name, num_clients, num_funcalls, keyrange, args, data):
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
        thread = (Thread(target = fun_name, args = (r, t_num, num_funcalls, keyrange, data)))
        thread_arr.append(thread)
        thread.start()

    for t in thread_arr:
        print "joining: " + str(t)
        t.join()

    end = time.time()
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    return end - start

def start_redis(redis_loc):
    # also wipe out state persisted to disk
    cmd = "rm dump.rdb"
    os.system(cmd)
    print "DB wiped from disk"
    logging.info("Starting redis ...\n")
    print (redis_loc +"redis-server " + redis_loc + "redis.conf 2>&1 &")
    os.system(redis_loc +"redis-server " + redis_loc + "redis.conf 2>&1 &")
    sleep(2)

def stop_redis():
    logging.info("Killing redis ...\n")
    cmd = "killall redis-server"
    os.system(cmd)
    sleep(2)
    # also wipe out state persisted to disk
    cmd = "rm dump.rdb"
    os.system(cmd)
    print "DB wiped from disk"


def main():

#    logging.basicConfig(level=logging.DEBUG)

    redis_loc = "/fs/macdonald/ksaur/redis-2.8.19/src/"


    # test get-sets
    #actualredis.flushall()
    num_keys = 5000    # the possible range of keys to iterate
    num_funcalls = 10000 # (x2 hits to redis because it's set/get). done over random keys (1 - num_keys)
    num_clients = 50
    # in the redis bench, the default is a 2 byte buffer full of x's, plus a nullterm. ("xxxxxxxx\n")
    # in python, one char alone is like...14 bytes.  but...we'll just use the same string.
    data = "xxxxxxxx"
     
    start_redis(redis_loc)
    print bench("normal_redis_getset", do_getset, num_clients, num_keys, num_funcalls, None, data)
    stop_redis()

    start_redis(redis_loc)
    print bench("lazy_redis_getset", do_getset, num_clients, num_keys, num_funcalls, [("edgeattr", "v0")], data)
    stop_redis()

#    # test do all now
#    start_redis(redis_loc)
#    # non-hooked redis commands to work as orginally specified
#    actualredis = redis.StrictRedis()
#    num_keys = 5000    # keys to add
#    num_funcalls = 1
#    num_clients = 1
#    sample_generate.gen_1_sadalage(num_keys)
#    print bench("RIGHTNOW_redis_sadalage1", do_updnow, num_clients, num_funcalls, num_keys, [("customer", "v0")])
#    print str(len(actualredis.keys("v0*"))) + " keys not updated, ",
#    print str(len(actualredis.keys("v1*"))) + " keys updated."
#    stop_redis()
#
#
#    # test lazy
#    start_redis(redis_loc)
#    # non-hooked redis commands to work as orginally specified
#    actualredis = redis.StrictRedis()
#    actualredis.flushall()
#    r = lazyupdredis.connect([("customer", "v0")])
#    num_keys = 5000    # the possible range of keys to iterate
#    num_funcalls = 10000 # done over random keys (1 - num_keys)
#    num_clients = 5
#    sample_generate.gen_1_sadalage(num_keys)
#    r.do_upd("data/example_jsonbulk/sample_1_sadalage_init")
#    print bench("lazy_redis_sadalage1", do_lazyupd, num_clients, num_funcalls, num_keys, [("customer", "v1")])
#    print str(len(actualredis.keys("v0*"))) + " keys not yet updated, ",
#    print str(len(actualredis.keys("v1*"))) + " keys updated."
#    stop_redis()


    # test lazy updates on a large scale
 

if __name__ == '__main__':
    main()
