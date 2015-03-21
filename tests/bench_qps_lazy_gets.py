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




def do_get(r, unused, num_gets, key_range, args2):

    for i in range(num_gets):
        rand = str(random.randint(1, key_range))
        try:
            r.get("node:" + rand)
        except DeprecationWarning as e:
            r = lazyupdredis.connect(args2)

def do_stats():
    actualredis = redis.StrictRedis()
    f = open('stats.txt', 'w')
    i = 0
    prevq = 0 #total quries, to be subtracted
    while True:
        try:
            queries = actualredis.info()["total_commands_processed"]
            f.write(str(i) + "\t" + str(queries-prevq) + "\n")
            prevq = queries
            time.sleep(1)
            i = i + 1 
        except ConnectionError:
            f.close()
            break
        

def bench(tname, fun_name, num_clients, num_funcalls, keyrange, args, args2):
    """ 
    @param args: used lazyredis.  If no args given, uses unmodified StrictRedis
    @type args: list of tuples [("ns", "vers"), ...]
    
    """

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

    start = time.time()
    thread_arr = list()
    for t_num in range(num_clients):
        r = lazyupdredis.connect(args)
        thread = (Thread(target = fun_name, args = (r, t_num, num_funcalls, keyrange, args2)))
        thread_arr.append(thread)
        thread.start()

    # This thread prints the "queries per second"
    thread = (Thread(target=do_stats))
    thread.start()

    sleep(10)

    updater = lazyupdredis.connect(args)
    updater.do_upd("data/example_json/bench_qps_lazy_gets_init")

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


def main():

#    logging.basicConfig(level=logging.DEBUG)

    # Remove the previous run's generated files, for sanity's sake.
    os.system("rm /tmp/gen*")

    redis_loc = "/fs/macdonald/ksaur/redis-2.8.19/src/"

    num_keys = 5000    # the possible range of keys to iterate
    num_funcalls = 10000 # #gets in this case done over random keys (1 - num_keys)
    num_clients = 50

    start_redis(redis_loc)
    # non-hooked redis commands to work as orginally specified
    actualredis = redis.StrictRedis()

    # prepopulate the DB for this "get" test.  Right now, assumimg no misses.
    json_val = json.dumps({"outport": 777, "inport": 999})
    r = lazyupdredis.connect([("node", "v0")])
    for i in range(num_keys):
        r.set("node:" + str(i), json_val)
     
    g = open('lazy.txt', 'w')
    #for i in range(3):  #TODO more trials, then take mean, lalal, etc
    g.write(str( bench("lazy_redis_get_qps", do_get, num_clients,  num_funcalls, num_keys, [("node", "v0")], [("node", "v1")]))+"\t ")
    print str(len(actualredis.keys("v0*"))) + " keys not updated, ",
    print str(len(actualredis.keys("v1*"))) + " keys updated."
    stop_redis()


if __name__ == '__main__':
    main()
