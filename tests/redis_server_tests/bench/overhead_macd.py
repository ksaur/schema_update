import redis
import subprocess
from subprocess import Popen
from time import sleep

redis_loc = "/fs/macdonald/ksaur/redis-2.8.17/src/"
kvolve_loc = "/fs/macdonald/ksaur/schema_update/redis-2.8.17/src/"
upd_loc = "update/fs/macdonald/ksaur/schema_update/tests/redis_server_tests/bench/prev_ns.so"
trials = 11 
num_clients = "50" # default
num_ops = "50000000"
keyspace = "1000000"
pipeline = "16"

def popen(args):
  print "$ %s" % args
  return Popen(args.split(" "))

def unmod(cmd, s, flag):
  print("______________"+cmd+"_____________")
  for i in range (trials):
    redis_server = popen(redis_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(s)
    r = redis.StrictRedis()
    r.client_setname("placebo")
    sleep(1)
    if flag:
      bench = subprocess.Popen([redis_loc +"redis-benchmark", "-n", num_ops, "-P", pipeline, "-r", keyspace, cmd, "__rand_int__", "val"])
    else:
      bench = subprocess.Popen([redis_loc +"redis-benchmark", "-n", num_ops, "-P", pipeline, "-r", keyspace, cmd, "__rand_int__"])
    bench.wait()
    redis_server.terminate() 
    sleep(1)

def kvolve_no_ns(cmd, s, flag):
  print("______________KV "+cmd +" NO NS_____________")
  for i in range (trials):
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(s)
    r = redis.StrictRedis()
    r.client_setname("placebo")
    sleep(1)
    if flag:
      bench = subprocess.Popen([kvolve_loc +"redis-benchmark", "-n", num_ops, "-P", pipeline, "-r", keyspace, cmd, "__rand_int__", "val"])
    else:
      bench = subprocess.Popen([kvolve_loc +"redis-benchmark", "-n", num_ops, "-P", pipeline, "-r", keyspace, cmd, "__rand_int__"])
    bench.wait()
    redis_server.terminate() 
    sleep(1)

def kvolve_with_ns(cmd, s, flag):
  print("______________KV "+cmd +" WITH NS_____________")
  for i in range (trials):
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(s)
    r = redis.StrictRedis()
    r.client_setname("key@2") # Redis uses "key" for prefix on the random keys
    sleep(1)
    if flag:
      bench = subprocess.Popen([kvolve_loc +"redis-benchmark",  "-n", num_ops, "-P", pipeline, "-r", keyspace, cmd, "__rand_int__", "val"])
    else:
      bench = subprocess.Popen([kvolve_loc +"redis-benchmark",  "-n", num_ops, "-P", pipeline, "-r", keyspace, cmd, "__rand_int__"])
    bench.wait()
    redis_server.terminate() 
    sleep(1)

def kvolve_with_ns_change(cmd, s, flag):
  print("______________KV "+cmd +" WITH NS CHANGE_____________")
  for i in range (trials):
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(s)
    r = redis.StrictRedis()
    r.client_setname("k@1")
    r.client_setname(upd_loc) # update from k@1->key@2 (namespace change)
    sleep(1)
    if flag:
      bench = subprocess.Popen([kvolve_loc +"redis-benchmark", "-n", num_ops, "-P", pipeline, "-r", keyspace, cmd, "__rand_int__", "val"])
    else:
      bench = subprocess.Popen([kvolve_loc +"redis-benchmark", "-n", num_ops, "-P", pipeline, "-r", keyspace, cmd, "__rand_int__"])
    bench.wait()
    redis_server.terminate() 
    sleep(1)

def main():
  subprocess.call(["rm", "dump.rdb"])
  s = 1

  unmod("get", s, False)
  unmod("set", s, True)
  kvolve_no_ns("get", s, False)
  kvolve_no_ns("set", s, True)
  kvolve_with_ns("get", s, False) 
  kvolve_with_ns("set", s, True) 
  kvolve_with_ns_change("get", s, False)
  kvolve_with_ns_change("set", s, True)

  unmod("spop", s, False)
  unmod("sadd", s, True)
  kvolve_no_ns("spop", s, False)
  kvolve_no_ns("sadd", s, True)
  kvolve_with_ns("spop", s, False) 
  kvolve_with_ns("sadd", s, True) 
  kvolve_with_ns_change("spop", s, False)
  kvolve_with_ns_change("sadd", s, True)

  unmod("lpop", s, False)
  unmod("lpush", s, True)
  kvolve_no_ns("lpop", s, False)
  kvolve_no_ns("lpush", s, True)
  kvolve_with_ns("lpop", s, False) 
  kvolve_with_ns("lpush", s, True) 
  kvolve_with_ns_change("lpop", s, False)
  kvolve_with_ns_change("lpush", s, True)


if __name__ == '__main__':
    main()
