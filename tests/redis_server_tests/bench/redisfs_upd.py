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
redisfs_5_loc = "/fs/macdonald/ksaur/schema_update/target_programs/redisfs.5/src/redisfs.so"
kitsune_bin = "/fs/macdonald/ksaur/kitsune-core/bin/bin/"
trials = 11

def popen(args):
  print "$ %s" % args
  return Popen(args.split(" "))

def do_stats(r):
  f = open('redisfs_upd_stats.txt', 'a')
  f.write("Time\t#Queries\n")
  i = 0
  while True:
    queries = r.info()["instantaneous_ops_per_sec"]
    f.write(str(i) + "\t" + str(queries-1) + "\n")
    time.sleep(.5)
    i = i + .5
    if (i%20 == 0):
      f.flush()

def kv():
  print("______________KV_____________")
  for i in range (trials):
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    r.client_setname("skx@5,skx:INODE@5,skx:PATH@5,skx:GLOBAL@5")
    redisfs5 = subprocess.Popen([kitsune_bin+"driver", redisfs_5_loc])
    sleep(2)
    # This thread prints the "queries per second"
    stats = Process(target=do_stats, args=(r,))
    stats.start()
    bench = subprocess.Popen([impres_loc, impres_spec_loc])
    sleep(100)
    print "UPDATING"
    os.system("echo UPDATING PROCESS AT")
    os.system("echo `pidof driver`")
    os.system(kitsune_bin+"doupd" +" `pidof driver` /fs/macdonald/ksaur/schema_update/target_programs/redisfs.6/src/redisfs.so")
    redisfs5.send_signal(signal.SIGTERM)
    bench.wait()
    redisfs6.terminate()
    stats.terminate()
    print r.info()
    redis_server.terminate() 
    sleep(1)


def main():
  subprocess.call(["rm", "dump.rdb"])
  kv()


if __name__ == '__main__':
  main()
