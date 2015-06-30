import redis
import subprocess
from subprocess import Popen
from time import sleep

redis_loc = "/fs/macdonald/ksaur/redis-2.8.17/src/"
kvolve_loc = "/fs/macdonald/ksaur/schema_update/redis-2.8.17/src/"
impres_loc = "/fs/macdonald/ksaur/impressions-v1/impressions"
impres_spec_loc = "/fs/macdonald/ksaur/impressions-v1/inputfile"
redisfs_5_loc = "/fs/macdonald/ksaur/schema_update/target_programs/redisfs.5/src/redisfs"
trials = 2

def popen(args):
  print "$ %s" % args
  return Popen(args.split(" "))


def kv():
  print("______________KV_____________")
  for i in range (trials):
    print kvolve_loc + " " + str(i)
    redis_server = popen(kvolve_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    r.client_setname("skx@5,skx:INODE@5,skx:PATH@5,skx:GLOBAL@5")
    redisfs = popen(redisfs_5_loc)
    sleep(1)
    bench = subprocess.Popen([impres_loc, impres_spec_loc])
    bench.wait()
    redisfs.terminate()
    print r.info()
    redis_server.terminate() 
    sleep(1)

def native():
  print("______________native_____________")
  for i in range (trials):
    print redis_loc + " " + str(i)
    redis_server = popen(redis_loc +"redis-server " + kvolve_loc +"../redis.conf")
    sleep(1)
    r = redis.StrictRedis()
    redisfs = popen(redisfs_5_loc)
    sleep(1)
    bench = subprocess.Popen([impres_loc, impres_spec_loc])
    bench.wait()
    redisfs.terminate()
    print r.info()
    redis_server.terminate() 
    sleep(1)

def main():
  subprocess.call(["rm", "dump.rdb"])
  kv()
  native()


if __name__ == '__main__':
    main()
