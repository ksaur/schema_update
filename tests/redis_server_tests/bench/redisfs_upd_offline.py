import redis
import signal
import time
import os
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
upd_code = "/fs/macdonald/ksaur/schema_update/target_programs/redisfs_updcode/redisfs_v5v6.so"
trials = 11
migrating = 0

def popen(args):
  print "$ %s" % args
  return Popen(args.split(" "))

def do_stats(r):
  f = open('redisfs_upd_stats.txt', 'a')
  f.write("Time\t#Queries\n")
  i = 0
  while True:
    if migrating == 0:
      queries = r.info()["instantaneous_ops_per_sec"]
    else:
      queries = 1
    f.write(str(i) + "\t" + str(queries-1) + "\n")
    time.sleep(.5)
    i = i + .5
    if (i%20 == 0):
      f.flush()

def kv():
  print("______________KV_____________")
  for i in range (trials):
    global migrating
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    r.client_setname("skx@5,skx:INODE@5,skx:PATH@5,skx:GLOBAL@5")
    redisfs5 = popen(redisfs_5_loc)
    sleep(2)
    # This thread prints the "queries per second"
    stats = Process(target=do_stats, args=(r,))
    stats.start()
    bench = subprocess.Popen([impres_loc, impres_spec_loc])
    sleep(100)
    print "KILLING v5"
    os.kill(bench.pid, signal.SIGSTOP)
    redisfs5.send_signal(signal.SIGINT)
    redisfs5.wait()
    r.client_setname("update/"+upd_code)
    print "Migrating schema offline"
    migrating = 1
    allkeys = r.keys('*')
    for k in allkeys:
      typ = r.type(k)
      if(typ == 'string'):
        r.get(k)
      elif(typ == 'set'):
        r.smembers(k)
    print "RESUMING at v7"
    migrating = 0
    redisfs7 = popen(redisfs_7_loc)
    os.kill(bench.pid, signal.SIGCONT)
    bench.wait()
    redisfs7.terminate()
    stats.terminate()
    print r.info()
    redis_server.terminate() 
    sleep(1)


def main():
  subprocess.call(["rm", "dump.rdb"])
  kv()


if __name__ == '__main__':
    main()
