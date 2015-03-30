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


def do_updnow(r, unused1, unused2, unused3, unused4):
    upd = r.do_upd_all_now("data/example_jsonbulk/sample_1_sadalage_init")
    logging.info("updated" + str(upd))
    return None

def do_lazyupd(r, unused, num_iters, key_range, unused2):

    for i in range(num_iters):
        rand1 = str(random.randint(1, key_range))
        r.get("customer:" + rand1)


def do_get(r, unused, num_getsets, key_range, unused2):

    for i in range(num_getsets):
        rand = str(random.randint(1, key_range))
        r.get("edgeattr:" + rand)

def do_set(r, unused, num_getsets, key_range, data):

    for i in range(num_getsets):
        rand = str(random.randint(1, key_range))
        r.set("edgeattr:" + rand, data)

def do_set_wmisses(r, unused, num_getsets, key_range, data):

    max = sys.maxint
    ctr = 0
    for i in range(num_getsets):
        if ctr > 16: # miss for 17,18,19
            rand = str(random.randint(key_range+1,max))
        else: # hit for 0-16
            rand = str(random.randint(1, key_range))
        r.set("edgeattr:" + rand, data)
        if ctr == 19:
            ctr = 0
        else:
            ctr = ctr + 1
    

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
    num_keys = 20000    # the possible range of keys to iterate
    num_funcalls = 10000 # (x2 hits to redis because it's set/get). done over random keys (1 - num_keys)
    num_clients = 50
    reduced = int(num_keys*.85)
    # in the redis bench, the default is a 2 byte buffer full of x's, plus a nullterm. ("xxxxxxxx\n")
    # in python, one char alone is like...14 bytes.  but...we'll just use the same string.
    data = "xxxxxxxx"
     
    f = open('normal_gets_nomiss.txt', 'a')
    f.write("num_keys: " + str(num_keys) + "\tnum_funcalls: " + str(num_funcalls) + "\tnum_clients: " +str(num_clients) +"\n")
    f.write("gets\t#keys\n")

    g = open('lazy_gets_nomisses.txt', 'a')
    g.write("num_keys: " + str(num_keys) + "\tnum_funcalls: " + str(num_funcalls) + "\tnum_clients: " +str(num_clients) +"\n")
    g.write("gets\t#keys\n")

    normalmisses = open('normal_gets_misses.txt', 'a')
    normalmisses.write("num_keys: " + str(num_keys*.85) + "\tgetting: " + str(num_keys) + "\tnum_funcalls: " + str(num_funcalls) + "\tnum_clients: " +str(num_clients) +"\n")
    normalmisses.write("gets\t#keys\n")

    misses = open('lazy_gets_misses.txt', 'a')
    misses.write("num_keys: " + str(num_keys*.85) + "\tgetting: " + str(num_keys) + "\tnum_funcalls: " + str(num_funcalls) + "\tnum_clients: " +str(num_clients) +"\n")
    misses.write("gets\t#keys\n")

    setnormalmisses = open('set_normal_misses.txt', 'a')
    setnormalmisses.write("num_funcalls: " + str(num_funcalls) + "\tnum_clients: " +str(num_clients) +"\n")
    setnormalmisses.write("sets\t#keys\n")

    setmisses = open('set_lazy_misses.txt', 'a')
    setmisses.write("num_funcalls: " + str(num_funcalls) + "\tnum_clients: " +str(num_clients) +"\n")
    setmisses.write("sets\t#keys\n")

    setnonormalmisses = open('set_normal_nomisses.txt', 'a')
    setnonormalmisses.write("num_funcalls: " + str(num_funcalls) + "\tnum_clients: " +str(num_clients) +"\n")
    setnonormalmisses.write("sets\t#keys\n")

    setnomisses = open('set_lazy_nomisses.txt', 'a')
    setnomisses.write("num_funcalls: " + str(num_funcalls) + "\tnum_clients: " +str(num_clients) +"\n")
    setnomisses.write("sets\t#keys\n")

    #for i in range(11):
    if True:
        #  NORMAL GETS NO MISS
#        start_redis(redis_loc)
#        get = bench("normal_redis_get", do_get, num_clients,  num_funcalls, num_keys, None, None)
#        f.write(str(get) +"\t")
#        actualredis = redis.StrictRedis()
#        f.write(str(len(actualredis.keys("*"))) + "\n")
#        f.flush()
#        stop_redis()
#
#        # LAZY GETS NO MISS
#        start_redis(redis_loc)
#        start_redis(redis_loc)
#        get =bench("lazy_redis_get_nomiss", do_get, num_clients,  num_funcalls, num_keys, [("edgeattr", "v0")], None)
#        g.write(str(get) +"\t")
#        actualredis = redis.StrictRedis()
#        print actualredis.info()
#        g.write(str(len(actualredis.keys("*"))) + "\n")
#        g.flush()
#        stop_redis()

        # NORMAL GETS WITH MISSES
        start_redis(redis_loc)
        # only set 85% of the keys, then try to get 100% for a 15% miss rate
        actualredis = redis.StrictRedis()
        for i in range(reduced):
            actualredis.set("edgeattr:" + str(i), data)
        get =bench("normal_redis_get_misses", do_get, num_clients,  num_funcalls, num_keys, None, None)
        normalmisses.write(str(get) +"\t")
        actualredis = redis.StrictRedis()
        print actualredis.info()
        normalmisses.write(str(len(actualredis.keys("*"))) + "\n")
        normalmisses.flush()
        stop_redis()

        # LAZY GETS WITH MISSES
        start_redis(redis_loc)
        # only set 85% of the keys, then try to get 100% for a 15% miss rate
        actualredis = redis.StrictRedis()
        for i in range(reduced):
            actualredis.set("v0|edgeattr:" + str(i), data)
        get =bench("lazy_redis_get_misses", do_get, num_clients,  num_funcalls, num_keys, [("edgeattr", "v0")], None)
        misses.write(str(get) +"\t")
        actualredis = redis.StrictRedis()
        print actualredis.info()
        misses.write(str(len(actualredis.keys("*"))) + "\n")
        misses.flush()
        stop_redis()

#        # NORMAL SET WITH MISSES
#        start_redis(redis_loc)
#        actualredis = redis.StrictRedis()
#        #prepopulate - no version tag for normal
#        for i in range(num_keys):
#            actualredis.set("edgeattr:" + str(i), data)
#        set = bench("normal_redis_set_misses", do_set_wmisses, num_clients,  num_funcalls, num_keys, None, data)
#        setnormalmisses.write(str(set) + "\t" )
#        setnormalmisses.write(str(actualredis.info()))
#        setnormalmisses.write(str(len(actualredis.keys("*"))) + "\n")
#        setnormalmisses.flush()
#        stop_redis()
#
#        # LAZY SET WITH MISSES
#        start_redis(redis_loc)
#        actualredis = redis.StrictRedis()
#        #prepopulate
#        for i in range(num_keys):
#            actualredis.set("v0|edgeattr:" + str(i), data)
#        set =bench("lazy_redis_set_misses", do_set_wmisses, num_clients,  num_funcalls, num_keys, [("edgeattr", "v0")], data)
#        setmisses.write(str(set) + "\t")
#        setmisses.write(str(actualredis.info()))
#        setmisses.write(str(len(actualredis.keys("*"))) + "\n")
#        setmisses.flush()
#        stop_redis()
#
#        # NORMAL SET WITH NO MISSES
#        start_redis(redis_loc)
#        actualredis = redis.StrictRedis()
#        #prepopulate - no version tag for normal
#        for i in range(num_keys):
#            actualredis.set("edgeattr:" + str(i), data)
#        set = bench("normal_redis_set_nomisses", do_set, num_clients,  num_funcalls, num_keys, None, data)
#        setnonormalmisses.write(str(set) + "\n" )
#        setnonormalmisses.write(str(actualredis.info()))
#        setnonormalmisses.write(str(len(actualredis.keys("*"))) + "\n")
#        setnonormalmisses.flush()
#        stop_redis()
#
#        # LAZY SET WITH NO MISSES
#        start_redis(redis_loc)
#        actualredis = redis.StrictRedis()
#        #prepopulate
#        for i in range(num_keys):
#            actualredis.set("v0|edgeattr:" + str(i), data)
#        set =bench("lazy_redis_set_nomisses", do_set, num_clients,  num_funcalls, num_keys, [("edgeattr", "v0")], data)
#        setnomisses.write(str(set) + "\n")
#        setnomisses.write(str(actualredis.info()))
#        setnomisses.write(str(len(actualredis.keys("*"))) + "\n")
#        setnomisses.flush()
#        stop_redis()



    f.close()
    g.close()
    normalmisses.close()
    misses.close()
    setmisses.close()
    setnormalmisses.close()

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
