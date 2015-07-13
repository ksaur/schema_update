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
amico_12_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/amico_12.rb"
amico_20_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/amico_20.rb"
upd_code = "/fs/macdonald/ksaur/schema_update/target_programs/amico_updcode/amico_v12v20.so"
trials = 11
runtime = 600 # 10 min
beforeupd = 300 # 5 min

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
    r.client_setname("amico:followers@12,amico:following@12,amico:blocked@12,amico:reciprocated@12,amico:pending@12")
    amico12 = subprocess.Popen(["ruby", amico_12_loc, "kvolve"])
    sleep(1)
    # This thread prints the "queries per second"
    stats = Thread(target=do_stats, args=(r,))
    stats.start()
    sleep(beforeupd)
    allkeys = r.keys('*')
    orig = len(allkeys)
    f2.write(str(orig) + ",")
    print "UPDATING, have " + str(orig) + " Keys to update" 
    r.client_setname("update/"+upd_code)
    amico12.terminate() # the connection will be automatically killed, this just kills the process
    amico20 = subprocess.Popen(["ruby", amico_20_loc, "kvolve"])
    sleep(runtime - beforeupd)
    amico20.terminate()
    stats.join()
    ke = r.keys('kvolve')
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
