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
from redis.exceptions import ConnectionError


def do_get(args, unused, num_gets, key_range, args2, unused2):

    r = lazyupdredis.connect(args)
    curr_key_ns = args[0][0]
    for i in range(num_gets):
        rand = str(random.randint(0, key_range-1))
        try:
            r.get(curr_key_ns +":" + rand)
        except DeprecationWarning as e:
            curr_key_ns = args2[0][0]
            r = lazyupdredis.connect(args2)

def do_set(args, unused, num_gets, key_range, args2, data):

    r = lazyupdredis.connect(args)
    curr_data = data[0]
    curr_key_ns = args[0][0]
    for i in range(num_gets):
        rand = str(random.randint(0, key_range-1))
        try:
            r.set(curr_key_ns + ":" + rand, curr_data)
        except DeprecationWarning as e:
            curr_data = data[1]
            curr_key_ns = args2[0][0]
            r = lazyupdredis.connect(args2)

def do_stats():
    actualredis = redis.StrictRedis()
    f = open('stats.txt', 'w')
    #f.write("Time\t#Queries\t#V0Keys\t#V1Keys\n")
    f.write("Time\t#Queries\t#V0Keys\n")
    i = 0
    while True:
        try:
            queries = actualredis.info()["instantaneous_ops_per_sec"]
            f.write(str(i) + "\t" + str(queries) + "\t")
            f.write(str(len(actualredis.keys("v0*"))) + "\n")
            #f.write(str(len(actualredis.keys("v1*"))) + "\n")
            time.sleep(.25)
            i = i + .25
            #os.system("ps -ly `pidof redis-server` >> rss.txt")
        except ConnectionError:
            f.flush()
            f.close()
            break
        

def bench(tname, fun_name, num_clients, num_funcalls, keyrange, args, args2, data):
    """ 
    @param args: first set of args for lazyredis.
    @type args: list of tuples [("ns", "vers"), ...]
    @param args2: new set of args for lazyredis
    
    """

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

    start = time.time()
    thread_arr = list()
    for t_num in range(num_clients):
        thread = (Thread(target = fun_name, args = (args, t_num, num_funcalls, keyrange, args2, data)))
        thread_arr.append(thread)
        thread.start()

    # This thread prints the "queries per second"
    thread = (Thread(target=do_stats))
    thread.start()

    sleep(10)

    updater = lazyupdredis.connect(args)
    #updater.do_upd("data/example_json/bench_qps_lazy_gets_init")
    updater.do_upd("data/example_json/upd_keys_init")
    print "UPDATE!!!!!!!"

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



def lazy_cmd(redis_loc, cmd):

    num_keys = 5000    # the possible range of keys to iterate
    num_funcalls = 10000 # #gets in this case done over random keys (1 - num_keys)
    num_clients = 50

    start_redis(redis_loc)
    # non-hooked redis commands to work as orginally specified
    actualredis = redis.StrictRedis()

    g = open('lazy.txt', 'w')
    if cmd == "get":
        # prepopulate the DB for this "get" test.  Right now, assumimg no misses.
        json_val = json.dumps({"outport": 777, "inport": 999})
        r = lazyupdredis.connect([("edgeattr", "v0")])
        for i in range(num_keys):
            r.set("edgeattr:" + str(i), json_val)
        g.write(str( bench("lazy_redis_get_qps", do_get, num_clients,  num_funcalls, num_keys, [("edgeattr", "v0")], [("edgeattr:graph1", "v1")], None))+"\n")

    elif cmd == "set":
        json_val = json.dumps({"outport": 777, "inport": 999})
        json_val2 = json.dumps({"outport": 777, "inport": 999})
        #json_val2 = json.dumps({"outport": 777, "inport": 999, "counter": 0})
        g.write(str( bench("lazy_redis_set_qps", do_set, num_clients,  num_funcalls, num_keys, [("edgeattr", "v0")], [("edgeattr:graph1", "v1")], [json_val, json_val2]))+"\n")

    print str(len(actualredis.keys("v0*"))) + " keys not updated, ",
    print str(len(actualredis.keys("v1*"))) + " keys updated."
    print actualredis.info()
    print "There are " + str(len(actualredis.keys("*"))) + " total keys in redis "
    stop_redis()


def main():

#    logging.basicConfig(level=logging.DEBUG)

    # Remove the previous run's generated files, for sanity's sake.
    os.system("rm /tmp/gen*")
    redis_loc = "/fs/macdonald/ksaur/redis-2.8.19/src/"

    # test lazy_gets()
    #for i in range(3):  #TODO more trials, then take mean, lalal, etc
    #lazy_cmd(redis_loc, "get")

    # test lazy_sets()
    #for i in range(3):  #TODO more trials, then take mean, lalal, etc
    lazy_cmd(redis_loc, "set")


if __name__ == '__main__':
    main()
