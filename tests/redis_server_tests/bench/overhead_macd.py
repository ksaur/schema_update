import redis
import subprocess
from subprocess import Popen
from time import sleep

redis_loc = "/fs/macdonald/ksaur/redis-2.8.17/src/"
kvolve_loc = "/fs/macdonald/ksaur/schema_update/redis-2.8.17/src/"
upd_loc = "update/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/prev_ns.so"
trials = 21
num_clients = "50" # default
num_ops = "5000000"
keyspace = "1000000"

def popen(args):
  print "$ %s" % args
  return Popen(args.split(" "))

def unmod(cmd, s):
  print("______________"+cmd+"_____________")
  for i in range (trials):
    redis_server = popen(redis_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(s)
    r = redis.StrictRedis()
    r.client_setname("placebo")
    sleep(1)
    bench = subprocess.Popen([redis_loc +"redis-benchmark", "-t", cmd, "-n", num_ops, "-r", keyspace])
    bench.wait()
    redis_server.terminate() 
    sleep(1)

def kvolve_no_ns(cmd, s):
  print("______________KV "+cmd +" NO NS_____________")
  for i in range (trials):
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(s)
    r = redis.StrictRedis()
    r.client_setname("placebo")
    sleep(1)
    bench = subprocess.Popen([kvolve_loc +"redis-benchmark", "-t", cmd, "-n", num_ops, "-r", keyspace])
    bench.wait()
    redis_server.terminate() 
    sleep(1)

def kvolve_with_ns(cmd, s):
  print("______________KV "+cmd +" WITH NS_____________")
  for i in range (trials):
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(s)
    r = redis.StrictRedis()
    r.client_setname("key@2") # Redis uses "key" for prefix on the random keys
    sleep(1)
    bench = subprocess.Popen([kvolve_loc +"redis-benchmark", "-t", cmd, "-n", num_ops, "-r", keyspace])
    bench.wait()
    redis_server.terminate() 
    sleep(1)

def kvolve_with_ns_change(cmd, s):
  print("______________KV "+cmd +" WITH NS CHANGE_____________")
  for i in range (trials):
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(s)
    r = redis.StrictRedis()
    r.client_setname("k@1")
    r.client_setname(upd_loc) # update from k@1->key@2 (namespace change)
    sleep(1)
    bench = subprocess.Popen([kvolve_loc +"redis-benchmark", "-t", cmd, "-n", num_ops, "-r", keyspace])
    bench.wait()
    redis_server.terminate() 
    sleep(1)

def main():
  subprocess.call(["rm", "dump.rdb"])
  s = 1
  for i in range (2):
    if s is 3:
      subprocess.call(["cp", "1000000_orig.rdb", "dump.rdb"])
    unmod("get", s)
    unmod("set", s)
    if s is 3:
      subprocess.call(["cp", "1000000_kv.rdb", "dump.rdb"])
    kvolve_no_ns("get", s)
    kvolve_no_ns("set", s)
    kvolve_with_ns("get", s) 
    kvolve_with_ns("set", s) 
    kvolve_with_ns_change("get", s)
    kvolve_with_ns_change("set", s)
    s = 3


if __name__ == '__main__':
    main()
