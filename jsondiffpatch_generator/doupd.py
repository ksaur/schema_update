"""

Call all of the generated functions for the input file.

Usage: python runfunctions.py filetoupdate

TODO: redis integration.....
 
With help from:
http://stackoverflow.com/questions/3061/
calling-a-function-of-a-module-from-a-string-with-the-functions-name-in-python

"""
import sys
import json
import decode
import redis


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
    # load up the file to get all functions (like dlsym with Kitsune)
    m = __import__ ('dsu')
    # Get all the keys for redis
    keys = r.keys('*');
    print "Printing \'" + str(len(keys)) + "\' keys:"
    for currkey in keys:
        redisval = None
        print "key: " + currkey
        redisval = r.get(currkey)
        print "value: |" + redisval + "|"


        # Make sure everything is loaded
        assert redisval is not None, ("could not find value for" + currkey)
        jsonkey = json.loads(redisval, object_hook=decode.decode_dict)
        print "LOADED:",
        print jsonkey
        # Looping in case the user puts more than one JSON entry per key
        for o in jsonkey.keys():
            # Create the function name 
            funcname = "update_"+o
            func = getattr(m,funcname)
            assert func is not None, ("Could not find function for" + funcname)

            # Call the function for the current key (but feed it all keys for structure)
            func(jsonkey)

            # Now serialize it back, then write it back to redis.  
            # (Note that the key was modified in place.)
            modedkey = json.dumps(jsonkey)
            r.set(currkey, jsonkey)
            

if __name__ == '__main__':
    main()
