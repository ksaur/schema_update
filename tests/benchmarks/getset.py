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
import random, time
from lazyupdredis import *
from threading import Thread
from time import sleep
from random import randint




def do_getset(r, num_getsets, key_range):

    for i in range(num_getsets):
        rand1 = str(random.randint(0, key_range))
        rand2 = str(random.randint(0, key_range))
        r.set("edgeattr:" + rand1, "str"+rand1)
        r.get("edgeattr:" + rand2)
    

def bench_getset(tname, num_clients, num_getsets, keyrange, args):
    """ 
    args (list) are for lazyredis.  If no args given, use normal StrictRedis
    
    """

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

    start = time.time()
    thread_arr = list()
    for t in range(num_clients):
        if args:
            r = lazyupdredis.connect(args)
        else:
            r = redis.StrictRedis()
        thread = (Thread(target = do_getset, args = (r, num_getsets, keyrange)))
        thread_arr.append(thread)
        thread.start()

    for t in thread_arr:
        print "joining" + str(t)
        t.join()

    end = time.time()
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    return end - start



def main():

    # non-hooked redis commands to work as orginally specified
    actualredis = redis.StrictRedis()
    actualredis.flushall()

    print bench_getset("normal_redis_getset", 5, 5000, 5000, None)
    actualredis.flushall()
    print bench_getset("lazy_redis_getset", 5, 5000, 5000, [("edgeattr", "v0")])


if __name__ == '__main__':
    main()
