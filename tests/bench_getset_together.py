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


def do_get(r, unused, num_getsets, key_range, unused2):

    for i in range(num_getsets):
        rand = str(random.randint(1, key_range))
        r.get("edgeattr:" + rand)

def do_set(r, unused, num_getsets, key_range, data):

    for i in range(num_getsets):
        rand = str(random.randint(1, key_range))
        r.set("edgeattr:" + rand, data)
    

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
    num_keys = 5000    # the possible range of keys to iterate
    num_funcalls = 10000 # (x2 hits to redis because it's set/get). done over random keys (1 - num_keys)
    num_clients = 50
    # in the redis bench, the default is a 2 byte buffer full of x's, plus a nullterm. ("xxxxxxxx\n")
    # in python, one char alone is like...14 bytes.  but...we'll just use the same string.
    data = "xxxxxxxx"
     
    f = open('normal.txt', 'w')
    g = open('lazy.txt', 'w')
    for i in range(3):
        start_redis(redis_loc)
        set = bench("normal_redis_set", do_set, num_clients,  num_funcalls, num_keys, None, data)
        get = bench("normal_redis_get", do_get, num_clients,  num_funcalls, num_keys, None, None)
        f.write(str(set+get)+"\t")
        f.flush()
        stop_redis()

        start_redis(redis_loc)
        set =bench("lazy_redis_set", do_set, num_clients,  num_funcalls, num_keys, [("edgeattr", "v0")], data)
        get =bench("lazy_redis_get", do_get, num_clients,  num_funcalls, num_keys, [("edgeattr", "v0")], None)
        g.write(str(set+get)+"\t")
        g.flush()
        stop_redis()
    f.close()
    g.close()

 

if __name__ == '__main__':
    main()
