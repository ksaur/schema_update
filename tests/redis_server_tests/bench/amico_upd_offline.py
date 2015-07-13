import redis
import signal
import time
import os, sys
import threading
from threading import Thread
import multiprocessing
from multiprocessing import Process
import subprocess
from subprocess import Popen
from time import sleep



kvolve_loc = "/fs/macdonald/ksaur/schema_update/redis-2.8.17/src/"
amico_12_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/amico_12.rb"
amico_20_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/amico_20.rb"
upd_code = "/fs/macdonald/ksaur/schema_update/target_programs/amico_updcode/amico_v12v20.so"
trials = 1
migrating = False
runtime = 200
beforeupd = 150

def popen(args):
  print "$ %s" % args
  return Popen(args.split(" "))


def do_stats(r):
  f = open('amico_upd_stats_offline.txt', 'a')
  f.write("\n")
  i = 0
  while i<runtime:
    if migrating == False:
      queries = r.info()["instantaneous_ops_per_sec"]
    else:
      queries = 1
    f.write(str(queries-1) + ",")
    time.sleep(.5)
    i = i + .5
    if (i%20 == 0):
      f.flush()

def kvoff():
  global migrating
  print("______________OFFLINE_____________")
  f2 = open('amico_upd_count_offline.txt', 'a')
  for i in range (trials):
    print "OFFLINE " + str(i)
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    amico12 = subprocess.Popen(["ruby", amico_12_loc])
    sleep(1)
    stats = Thread(target=do_stats, args=(r,))
    stats.start()
    sleep(beforeupd)
    print "KILLING v5"
    amico12.terminate()
    r.client_setname("amico:followers@12,amico:following@12,amico:blocked@12,amico:reciprocated@12,amico:pending@12")
    r.client_setname("update/"+upd_code)
    print "Migrating schema offline starting"
    print time.time()
    migrating = True
    allkeys = r.keys('*')
    print "UPDATING, have " + str(len(allkeys)) + " Keys to update" 
    f2.write(str(len(allkeys)) + "\n")
    for k in allkeys:
      r.zcard(k)
    r.client_setname("clear")
    # added if(strncmp(vers_str,"clear",5)==0) {vers_list = NULL; return;} kvolve_internal.c:115
    # which will return kvolve to normal redis mode
    migrating = False
    print time.time()
    print "RESUMING at v7"
    amico20 = subprocess.Popen(["ruby", amico_20_loc])
    sleep(runtime - beforeupd)
    amico20.terminate()
    stats.join()
    print r.info()
    redis_server.terminate() 
    sleep(1)
    f2.flush()
  f2.close()


def main():
  subprocess.call(["rm", "dump.rdb"])
  kvoff()


if __name__ == '__main__':
    main()
