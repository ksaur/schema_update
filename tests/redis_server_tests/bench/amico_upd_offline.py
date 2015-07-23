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



redis_loc = "/fs/macdonald/ksaur/redis-2.8.17/src/"
amico_12_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/amico_12.rb"
amico_12b_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/amico_12_b.rb"
amico_20_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/amico_20.rb"
amico_20b_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/amico_20_b.rb"
upd_code = "/fs/macdonald/ksaur/schema_update/target_programs/amico_updcode/amico_v12v20.so"
trials = 11
migrating = False
runtime = 1800 # 30 min
beforeupd = 900 # 15 min

def popen(args):
  print "$ %s" % args
  return Popen(args.split(" "))


def do_stats(r, run):
  name = "amico_upd_stats"+str(run)+"_offline.txt"
  f = open(name, 'a')
  f.write("\n")
  i = 0
  while i<runtime:
    if migrating == False:
      queries = r.info()["instantaneous_ops_per_sec"]
    else:
      queries = 1
    f.write(str(queries-1) + "\n")
    time.sleep(1)
    i = i + 1 
    if (i%20 == 0):
      f.flush()

def kvoff():
  global migrating
  print("______________OFFLINE_____________")
  f2 = open('amico_upd_count_offline.txt', 'a')
  for i in range (trials):
    print "OFFLINE " + str(i)
    redis_server = popen(redis_loc +"redis-server " + redis_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    amico12 = subprocess.Popen(["ruby", amico_12_loc])
    amico12b = subprocess.Popen(["ruby", amico_12b_loc])
    sleep(1)
    stats = Thread(target=do_stats, args=(r,i))
    stats.start()
    sleep(beforeupd)
    print "KILLING v5"
    amico12.terminate()
    amico12b.terminate()
    print "Migrating schema offline starting"
    print time.time()
    migrating = True
    allkeys = r.keys('*')
    print "UPDATING, have " + str(len(allkeys)) + " Keys to update" 
    f2.write(str(len(allkeys)) + "\n")
    for s in allkeys:
      r.rename(s, s[0:s.rfind(':')] +":default"+s[s.rfind(':'):])
    migrating = False
    print time.time()
    print "RESUMING at v7"
    amico20 = subprocess.Popen(["ruby", amico_20_loc])
    amico20b = subprocess.Popen(["ruby", amico_20b_loc])
    sleep(runtime - beforeupd)
    amico20.terminate()
    amico20b.terminate()
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
