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
amico_12_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/am12.rb"
amico_20_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/am20.rb"
trials = 11
migrating = False
runtime = 150
beforeupd = 50

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
    orig = r.dbsize()
    print "UPDATING, have " + str(orig) + " Keys to update" 
    f2.write(str(orig) + "\n")
    allkeys = r.keys('*')
    for k in allkeys:
      typ = r.type(k)
      if(typ == 'string'):
        r.get(k)
      elif(typ == 'set'):
        r.smembers(k)
    print "RESUMING at v7"
    # added if(strncmp(vers_str,"clear",5)==0) {vers_list = NULL; return;} kvolve_internal.c:115
    # which will return kvolve to normal redis mode
    r.client_setname("clear")
    print time.time()
    migrating = False
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
