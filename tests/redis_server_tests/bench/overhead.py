import redis
import subprocess
from subprocess import Popen
from time import sleep

#def redis_loc = "/fs/macdonald/ksaur/redis-2.8.19/src/"
redis_loc = "/home/ksaur/redis-2.8.17/src/"

def popen(args):
  print "$ %s" % args
  return Popen(args.split(" "))

def unmod(cmd):
  for i in range (11):
    redis_server = popen(redis_loc +"redis-server " + redis_loc +"../redis.conf")
    sleep(1)
    bench = subprocess.Popen([redis_loc +"redis-benchmark", "-t", cmd, "-n", "1000000", "-r", "100000000"])
    bench.wait()
    redis_server.terminate() 
    sleep(1)


def main():
    unmod("get")
    unmod("set")


if __name__ == '__main__':
    main()
