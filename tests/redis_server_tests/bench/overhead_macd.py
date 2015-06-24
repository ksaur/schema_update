import redis
import subprocess
from subprocess import Popen
from time import sleep

#redis_loc = "/home/ksaur/redis-2.8.17/src/"
redis_loc = "/fs/macdonald/ksaur/redis-2.8.17/src/"
#kvolve_loc = "/home/ksaur/AY1415/schema_update/redis-2.8.17/src/"
kvolve_loc = "/fs/macdonald/ksaur/schema_update/redis-2.8.17/src/"
#upd_loc = "update/home/ksaur/AY1415/schema_update/tests/redis_server_tests/bench/prev_ns.so"
upd_loc = "update/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/prev_ns.so"
trials = 11
num_clients = "50" # default
num_ops = "2000000"
keyspace = "100000000"

def popen(args):
  print "$ %s" % args
  return Popen(args.split(" "))

def unmod(cmd):
  print("______________"+cmd+"_____________")
  for i in range (trials):
    redis_server = popen(redis_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    r.client_setname("placebo")
    sleep(1)
    bench = subprocess.Popen([redis_loc +"redis-benchmark", "-t", cmd, "-n", num_ops, "-r", keyspace])
    bench.wait()
    redis_server.terminate() 
    sleep(1)

def kvolve_no_ns(cmd):
  print("______________KV "+cmd +" NO NS_____________")
  for i in range (trials):
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    r.client_setname("placebo")
    sleep(1)
    bench = subprocess.Popen([kvolve_loc +"redis-benchmark", "-t", cmd, "-n", num_ops, "-r", keyspace])
    bench.wait()
    redis_server.terminate() 
    sleep(1)

def kvolve_with_ns(cmd):
  print("______________KV "+cmd +" WITH NS_____________")
  for i in range (trials):
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    r.client_setname("key@2") # Redis uses "key" for prefix on the random keys
    sleep(1)
    bench = subprocess.Popen([kvolve_loc +"redis-benchmark", "-t", cmd, "-n", num_ops, "-r", keyspace])
    bench.wait()
    redis_server.terminate() 
    sleep(1)

def kvolve_with_ns_change(cmd):
  print("______________KV "+cmd +" WITH NS CHANGE_____________")
  for i in range (trials):
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    r.client_setname("k@1")
    r.client_setname(upd_loc)
    sleep(1)
    bench = subprocess.Popen([kvolve_loc +"redis-benchmark", "-t", cmd, "-n", num_ops, "-r", keyspace])
    bench.wait()
    redis_server.terminate() 
    sleep(1)

def main():
  unmod("get")
  unmod("set")
  kvolve_no_ns("get")
  kvolve_no_ns("set")
  kvolve_with_ns("get") 
  kvolve_with_ns("set") 
  kvolve_with_ns_change("get")
  kvolve_with_ns_change("set")


if __name__ == '__main__':
    main()
