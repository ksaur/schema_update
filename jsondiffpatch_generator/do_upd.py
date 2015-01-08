"""

Call all of the generated functions for the redis database.

Usage: python doupd.py

This assumes the update functions are in a file called dsu.py (todo)

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


def do_upd(r, updfile="dsu"):
    #strip off extention, if provided
    updfile = updfile.replace(".py", "")
    # load up the file to get all functions (like dlsym with Kitsune)
    m = __import__ (updfile)

    update_pairs = getattr(m, "update_pairs")

    # Loop over the "for key __  " glob stanzas
    for glob in update_pairs:
        print glob
        print update_pairs[glob]
        keys = r.keys(glob)
        print "Printing \'" + str(len(keys)) + "\' keys:"
        # Loop over the keys matching the current glob
        for currkey in keys:
            redisval = None
            print "key: " + currkey
            redisval = r.get(currkey)
            print "value: |" + redisval + "|"

            # Make sure everything is loaded
            assert redisval is not None, ("could not find value for" + currkey)
            print type(redisval)
            jsonkey = json.loads(redisval, object_hook=decode.decode_dict)
            
            # Loop over the set of functions that apply to the keys
            for funcname in update_pairs[glob]:
                try:
                    func = getattr(m,funcname)
                except AttributeError as e:
                    print "(Could not find function: " + funcname + ")"
                    continue
                # Call the function for the current key and current jsonsubkey
                func(currkey, jsonkey)

                # Now serialize it back, then write it back to redis.  
                # (Note that the key was modified in place.)
                modedkey = json.dumps(jsonkey)
                r.set(currkey, modedkey)


def main():
    r = connect()
    do_upd(r)
            

if __name__ == '__main__':
    main()
