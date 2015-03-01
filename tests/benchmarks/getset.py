"""
The built-in redis benchmark (redis-bench) is designed to benchmark _redis_, 
not the redis client.  However, the basic idea in this benchmark is the same...
test a large number of gets/sets on a large number of clients.

This benchmark is meant to compare the standard install redis client (pyredis)
against the lazy update redis client (lazyupdredis).
"""
import json
import sys, os
import redis
from lazyupdredis import *
from threading import Thread



def bench_normal_getset():
    return None


def bench_lazy_getset():
    return None



def main():

    # Remove the previous run's generated files, for sanity's sake.
    os.system("rm /tmp/gen*")

    # non-hooked redis commands to work as orginally specified
    actualredis = redis.StrictRedis()


    actualredis.execute_command('QUIT')


if __name__ == '__main__':
    main()
