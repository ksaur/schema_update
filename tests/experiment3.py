import json
import sys, os
import redis
import random, time, logging
####from redis import *
import threading
from threading import Thread
from time import sleep
from random import randint
sys.path.append("data/example_jsonbulk/")
import sample_generate
from redis.exceptions import ConnectionError

#global
signal = False

def do_get(args, t_num, num_gets, key_range, e, r):

    for i in range(num_gets):
        rand = str(random.randint(0, key_range-1))
        try:
            r.get("key:" + rand)
        except Exception:
            print "DISCONNECTED: count: " + str(i) + " thread:" + str(t_num)
            e.wait()
            r = redis.StrictRedis()
            print str(t_num) + " reconnected."

def do_stats():
    actualredis = redis.StrictRedis()
    f = open('stats.txt', 'a')
    #f.write("Time\t#Queries\t#V0Keys\t#V1Keys\n")
    f.write("Time\t#Queries\t#V0Keys\n")
    i = 0
    while True:
        try:
            queries = actualredis.info()["instantaneous_ops_per_sec"]
            f.write(str(i) + "\t" + str(queries) + "\n")
            #f.write(str(len(actualredis.keys("ver0*"))) + "\n")
            #f.write(str(len(actualredis.keys("ver1*"))) + "\n")
            time.sleep(.5)
            i = i + .5
            #os.system("ps -ly `pidof redis-server` >> rss.txt")
        except ConnectionError:
            f.write("______________________________________________\n")
            f.flush()
            f.close()
            break
        

def bench(tname, fun_name, num_clients, num_funcalls, keyrange, args, args2, data, preload):
    """ 
    @param args: first set of args for lazyredis.
    @type args: list of tuples [("ns", "vers"), ...]
    @param args2: new set of args for lazyredis
    
    """

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"


    client_handles = list()
    for tnum in range(num_clients): # must do ahead of time to not mess up timer
        r = redis.StrictRedis(args)
        client_handles.append(r)

    # This thread prints the "queries per second"
    thread = (Thread(target=do_stats))
    thread.start()

    start = time.time()
    thread_arr = list()
    threading_event = threading.Event()
    for t_num in range(num_clients):
        thread = (Thread(target = fun_name, args = (args, t_num, num_funcalls, keyrange, threading_event, client_handles[t_num])))
        thread_arr.append(thread)
        thread.start()


    sleep(20)
    updater = redis.StrictRedis(args)
    print "UPDATE!!!!!!!"
    [ r.connection_pool.disconnect() for r in client_handles ]
    arr = r.scan(0)
    while True:
        for rediskey in arr[1]:
            jsonobj = json.loads(r.get(rediskey))
            group_0_update_order(rediskey, jsonobj)
            r.set(rediskey, json.dumps(jsonobj))
        if arr[0] == 0:
            break
        arr = r.scan(arr[0])

    print "SIGNAL"
    threading_event.set()

    # now the threads can finish...
    for t in thread_arr:
        print "joining: " + str(t)
        t.join()

    end = time.time()
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    return end - start

def start_redis(redis_loc):
    # also wipe out state persisted to disk
    #cmd = "rm dump.rdb"
    #os.system(cmd)
    #print "DB wiped from disk"
    logging.info("Starting redis ...\n")
    print (redis_loc +"redis-server " + redis_loc + "redis.conf 2>&1 &")
    os.system(redis_loc +"redis-server " + redis_loc + "redis.conf 2>&1 &")
    sleep(5)

def stop_redis():
    logging.info("Killing redis ...\n")
    cmd = "killall redis-server"
    os.system(cmd)
    sleep(5)

def group_0_update_order(rediskey, jsonobj):
    e = jsonobj.get('order').get('orderItems')
    assert(e is not None)
    for f in e:
        assert(f is not None)
        f['discountedPrice'] = round(f['price']*.7,2)
        f['fullprice'] = f.pop('price')
    return (rediskey, jsonobj)


def lazy_cmd(redis_loc):

    num_keys = 200000    # the possible range of keys to iterate
    num_funcalls = 20000 # #gets in this case done over random keys (1 - num_keys)
    num_clients = 50

    start_redis(redis_loc)

    bench("lazy_redis_get_qps", do_get, num_clients,  num_funcalls, num_keys, None, None, None, None)

    stop_redis()


def main():

#    logging.basicConfig(level=logging.DEBUG)
    redis_loc = "/fs/macdonald/ksaur/redis-2.8.19/src/"
    lazy_cmd(redis_loc)

if __name__ == '__main__':
    main()
