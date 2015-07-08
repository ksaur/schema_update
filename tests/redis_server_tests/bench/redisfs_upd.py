import redis
import signal
import time
import os
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
redisfs_5_loc = "/fs/macdonald/ksaur/schema_update/target_programs/redisfs.5/src/redisfs.so"
redisfs_7_loc = "/fs/macdonald/ksaur/schema_update/target_programs/redisfs.7/src/redisfs.so"
kitsune_bin = "/fs/macdonald/ksaur/kitsune-core/bin/bin/"
trials = 11
runtime = 150
beforeupd = 50

def popen(args):
  print "$ %s" % args
  return Popen(args.split(" "))

def do_stats(r):
  f = open('redisfs_upd_stats.txt', 'a')
  f.write("\n")
  i = 0
  while i<runtime:
    queries = r.info()["instantaneous_ops_per_sec"]
    f.write(str(queries-1) + ",")
    time.sleep(.5)
    i = i + .5
    if (i%20 == 0):
      f.flush()

def kv():
  print("______________KITSUNE_____________")
  f2 = open('redisfs_upd_count.txt', 'a')
  for i in range (trials):
    print "KITS " + str(i)
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    r.client_setname("skx@5,skx:INODE@5,skx:PATH@5,skx:GLOBAL@5")
    driver = subprocess.Popen([kitsune_bin+"driver", redisfs_5_loc])
    sleep(2)
    # This thread prints the "queries per second"
    stats = Thread(target=do_stats, args=(r,))
    stats.start()
    bench = subprocess.Popen([ps_loc, ps_spec_loc])
    sleep(beforeupd)
    orig = r.dbsize()
    print "UPDATING, have " + str(orig) + " Keys to update" 
    f2.write(str(orig) + ",")
    print time.time()
    os.system(kitsune_bin+"doupd" +" `pidof driver` "+ redisfs_7_loc)
    driver.send_signal(signal.SIGTERM)
    print time.time()
    sleep(runtime - beforeupd)
    bench.terminate()
    driver.terminate()
    stats.join()
    ke = r.keys('*')
    notupd = 0
    for k in ke:
      t = r.object("idletime", k)
      if t > beforeupd:
         notupd = notupd + 1
    print "UPDATED: " + str(orig -notupd)
    f2.write(str(orig -notupd) + "\n")
    print r.info()
    redis_server.terminate() 
    sleep(1)
    f2.flush()
  f2.close()


def main():
  subprocess.call(["rm", "dump.rdb"])
  kv()


if __name__ == '__main__':
  main()
