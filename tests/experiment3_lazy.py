import json
import sys, os
import redis
import random, time, logging
####from redis import *
from lazyupdredis import *
import threading
from threading import Thread
from time import sleep
from random import randint
sys.path.append("data/example_jsonbulk/")
import sample_generate
from redis.exceptions import ConnectionError


fname = "foo" #set later, placeholder.
xformed = [0] * 200000



def do_get_or_set(cmds, t_num, num_gets, key_range, unused2, r, data, args2, times):

    curr_data = data[0]
    updated = False
    global xformed
    times.append(0)
    timestmp = time.time()
    currtotal = 0
    for i in range(num_gets):
        rand = str(random.randint(0, key_range-1))
        cmd = cmds[i]
        try:
            if cmd == 1:
                #print "GETTTT"
                r.get("key:" + rand)
            else:
                #print "SSSSSETTTT"
                r.set("key:" + rand, curr_data)
            if updated is True:
                xformed[int(rand)] = 1           
            if timestmp +.25 < time.time():
                times.append(currtotal)
                currtotal = 0
                timestmp = time.time()
            currtotal = currtotal + 1
        except Exception: # we may lose up to .25s of data
            print "DISCONNECTED: count: " + str(i) + " thread:" + str(t_num)
            kill = time.time()
            curr_data = data[1]
            r = lazyupdredis.connect(args2)
            print str(t_num) + " reconnected."
            timestmp = time.time()
            pause = timestmp - kill            
            while pause > 0:
                times.append(0)
                pause = pause - .25
            updated = True

def do_stats():
    actualredis = redis.StrictRedis()
    f = open(fname+'stats.txt', 'a')
    #f.write("Time\t#Queries\t#V0Keys\t#V1Keys\n")
    f.write("Time\t#Queries\t#V0Keys\n")
    i = 0
    while True:
        try:
            queries = actualredis.info()["instantaneous_ops_per_sec"]
            f.write(str(i) + "\t" + str(queries) + "\t")
            f.write(str(xformed.count(1)) + "\n")
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


    global fname
    fname = tname
    client_handles = list()
    for tnum in range(num_clients): # must do ahead of time to not mess up timer
        r = lazyupdredis.connect(args)
        client_handles.append(r)
    cmds = list()
    if fun_name == "do_get_or_set":
        print "GETS AND SETS"
        for i in range(num_funcalls):
            cmds.append(random.randint(0, 1))
    elif fun_name == "do_get":
        print "GETS"
        for i in range(num_funcalls):
            cmds.append(1)
        # This thread prints the "queries per second"
        thread = (Thread(target=do_stats))
        thread.start()
    elif fun_name == "do_set":
        print "SETS"
        for i in range(num_funcalls):
            cmds.append(0)


    start = time.time()
    thread_arr = list()
    results = list()
    threading_event = threading.Event()
    for t_num in range(num_clients):
        l = list()
        results.append(l)
        thread = (Thread(target = do_get_or_set, args = (cmds, t_num, num_funcalls, keyrange, threading_event, client_handles[t_num], data, args2, results[t_num] )))
        thread_arr.append(thread)
        thread.start()


    sleep(20)

    updater = lazyupdredis.connect(args)
    # Version with a preload of module
    updater.do_upd("data/example_json/paper_dsl", "/tmp/mymodule.py")
    print "UPDATE!!!!!!!"

    for t in thread_arr:
        print "joining: " + str(t)
        t.join()
    totals = [0] * 10000
    for i in range(num_clients):
        tdata = results[i]
        for idx, j in enumerate(tdata):
            totals[idx] = totals[idx] + j
    f = open(tname+'.txt', 'a')
    f.write(str(totals))
    f.write("\n____________________________\n")
    f.close()

    end = time.time()
    print updater.info() 
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


def lazy_cmd(redis_loc, cmd):

    num_keys = 200000    # the possible range of keys to iterate
    num_funcalls = 25000 # #gets in this case done over random keys (1 - num_keys)
    num_clients = 50

    start_redis(redis_loc)

    val1 = {
    "_id": "4BD8AE97C47016442AF4A580",
    "customerid": 99999,
    "name": "Foo Sushi Inc",
    "since": "12/12/2012",
    "order": {
        "orderid": "UXWE-122012",
        "orderdate": "12/12/2001",
        "orderItems": [
            {
                "product": "Fortune Cookies",
                "price": 19.99
            }
        ]
    }}
    val2 = {
    "_id": "4BD8AE97C47016442AF4A580",
    "customerid": 99999,
    "name": "Foo Sushi Inc",
    "since": "12/12/2012",
    "order": {
        "orderid": "UXWE-122012",
        "orderdate": "12/12/2001",
        "orderItems": [
            {
                "product": "Fortune Cookies",
                "fullprice": 19.99,
                "discountedPrice": 13.99
            }
        ]
    }}
    json_val1 = json.dumps(val1)
    json_val2 = json.dumps(val2)

    bench("lazy_redis_"+cmd, cmd, num_clients,  num_funcalls, num_keys, [("key", "ver0")], [("key", "ver1")], [json_val1, json_val2], None)
    actualredis = redis.StrictRedis()
    print str(len(actualredis.keys("ver0*"))) + " keys not updated, "

    stop_redis()


def main(cmd):

#    logging.basicConfig(level=logging.DEBUG)
    redis_loc = "/fs/macdonald/ksaur/redis-2.8.19/src/"
    lazy_cmd(redis_loc, cmd)

if __name__ == '__main__':
    main(str(sys.argv[1]))
