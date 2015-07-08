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
ps_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/postmark"
ps_spec_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/config.pmrc"
redisfs_5_loc = "/fs/macdonald/ksaur/schema_update/target_programs/redisfs.5/src/redisfs"
redisfs_7_loc = "/fs/macdonald/ksaur/schema_update/target_programs/redisfs.7/src/redisfs"
upd_code = "/fs/macdonald/ksaur/schema_update/target_programs/redisfs_updcode/redisfs_v0v6.so"
trials = 11
migrating = False
runtime = 150
beforeupd = 50

def popen(args):
  print "$ %s" % args
  return Popen(args.split(" "))


def do_stats(r):
  f = open('redisfs_upd_stats_offline.txt', 'a')
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
  f2 = open('redisfs_upd_count_offline.txt', 'a')
  for i in range (trials):
    print "OFFLINE " + str(i)
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    redisfs5 = popen(redisfs_5_loc)
    sleep(2)
    stats = Thread(target=do_stats, args=(r,))
    stats.start()
    bench = subprocess.Popen([ps_loc, ps_spec_loc])
    sleep(beforeupd)
    print "KILLING v5"
    os.kill(bench.pid, signal.SIGSTOP)
    redisfs5.send_signal(signal.SIGINT)
    redisfs5.wait()
    r.client_setname("skx@0,skx:INODE@0,skx:PATH@0,skx:GLOBAL@0")
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
    migrating = False
    print time.time()
    redisfs7 = popen(redisfs_7_loc)
    os.kill(bench.pid, signal.SIGCONT)
    sleep(runtime - beforeupd)
    bench.terminate()
    redisfs7.terminate()
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
