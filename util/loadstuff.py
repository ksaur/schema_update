"""
This file is used in generating test data.

Load up some test data from a file into the database for testing.

Usage: python runfunctions.py filetoupdate

Assumes you have a file with some JSON for now... TODO....

"""
import sys
import redis


#TODO: link with other libraries, or make stand-alone?
def connect(host=None, port=None):
    """ Connect to redis. Default is localhost, port 6379.
        (Redis must be running.)
    """
    if host is None:
        host = 'localhost'
    if port is None:
        port = 6379
    r = redis.StrictRedis(host, port, db=0)
    try:
        r.ping()
    except r.ConnectionError as e:
        print(e)
        sys.exit(-1)
    return r

# TODO...redis objects
        ## For later, when it's not just strings...
        #redisval = None
        #typ = r.type(currkey)
        #print "key (" + typ + "): " + currkey
        #if typ == 'string':
        #    redisval = r.get(currkey)
        #### For later, when it's not just strings...
        #elif typ == 'hash':
        #    print r.hgetall(key)
        #elif typ == 'zset':
        #    print r.zrange(key, 0, -1)
        #elif typ == 'set':
        #    print r.smembers(key)
        #elif typ == 'list':
        #    print r.lrange(key, 0, -1)
        #print "---"

def main():

    r = connect()
    r.flushall()
    assert (len(sys.argv) == 2), '\n\nUsage is: \"python loadstuff.py <filetoload>\"'

    f = open(sys.argv[1], 'r')
    name = 1  # for fake key name generation
    for l in f:
        #print "|" + l.rstrip('\n') + "|"
        r.set(str(name), l.rstrip('\n'))
        name+=1 # increment the variable key's 'name'


if __name__ == '__main__':
    main()
