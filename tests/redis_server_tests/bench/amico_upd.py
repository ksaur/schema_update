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
amico_12_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/am12.rb"
amico_20_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/am20.rb"
trials = 11
runtime = 15
beforeupd = 5

def popen(args):
  print "$ %s" % args
  return Popen(args.split(" "))

def do_stats(r):
  f = open('amico_upd_stats.txt', 'a')
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
  print("______________KVOLVE_____________")
  f2 = open('amico_upd_count.txt', 'a')
  for i in range (trials):
    print "KVOLVE " + str(i)
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    amico12 = subprocess.Popen(["ruby", amico_12_loc])
    sleep(1)
    # This thread prints the "queries per second"
    stats = Thread(target=do_stats, args=(r,))
    stats.start()
    sleep(beforeupd)
    orig = r.dbsize()
    f2.write(str(orig) + ",")
    print "UPDATING, have " + str(orig) + " Keys to update" 
    amico12.terminate()

    amico20 = subprocess.Popen(["ruby", amico_20_loc])
    sleep(runtime - beforeupd)
    amico20.terminate()
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
