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
impres_loc = "/fs/macdonald/ksaur/impressions-v1/impressions"
impres_spec_loc = "/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/inputfile"
redisfs_5_loc = "/fs/macdonald/ksaur/schema_update/target_programs/redisfs.5/src/redisfs"
redisfs_7_loc = "/fs/macdonald/ksaur/schema_update/target_programs/redisfs.7/src/redisfs"
upd_code = "/fs/macdonald/ksaur/schema_update/target_programs/redisfs_updcode/redisfs_v0v6.so"
trials = 11
migrating = False
runtime = 230
beforeupd = 100

def popen(args):
  print "$ %s" % args
  return Popen(args.split(" "))

def do_crawl():
  t = time.time()
  while True:
    for path,dirs,files in os.walk("/mnt/redis"):
      for f in files:
        os.system("cat " + path +"/" +f +"> /dev/null")
        sleep(.1)
        if (time.time() - t)  > runtime:
          return
        while migrating == True:
          sleep(1)

def do_stats(r):
  f = open('redisfs_upd_stats.txt', 'a')
  f.write("Time\t#Queries\n")
  i = 0
  while i<runtime:
    if migrating == False:
      queries = r.info()["instantaneous_ops_per_sec"]
    else:
      queries = 1
    f.write(str(i) + "\t" + str(queries-1) + "\n")
    time.sleep(.5)
    i = i + .5
    if (i%20 == 0):
      f.flush()

def kv():
  global migrating
  print("______________KV_____________")
  for i in range (trials):
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    redisfs5 = popen(redisfs_5_loc)
    sleep(2)
    stats = Thread(target=do_stats, args=(r,))
    stats.start()
    crawl = Thread(target=do_crawl)
    crawl.start()
    bench = subprocess.Popen([impres_loc, impres_spec_loc])
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
    crawl.join()
    print r.info()
    redis_server.terminate() 
    sleep(1)


def main():
  subprocess.call(["rm", "dump.rdb"])
  kv()


if __name__ == '__main__':
    main()
