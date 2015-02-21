import sys, os
import redis
from redis.exceptions import WatchError

sys.path.append("../src")
import lazyupdredis


def test_set(r, evilredis, evilval, name, value):
    """
    This code should match the code in lazyupdredis "get".  The issue is getting the
    evilredis to modify the key in the split microsecond inbetween the adds, so this
    forces that to happen.
    """

    ns = r.namespace(name)
    curr_ver = r.global_curr_version(ns)
    if curr_ver is None:
        raise ValueError("ERROR, Bad for current version (None) for key \'" + name +\
              "\'. Global versions are: " + str(r.global_versions(ns)))
    new_name = curr_ver + "|" + name
    pieces = [new_name, value]

    prev = r.global_versions(ns)
    try:
        pipe = r.pipeline()
        pipe.watch(new_name)
        pipe.multi()
        for v in reversed(prev[:-1]):
            oldname = v + "|" + name
            old = pipe.execute_command('GET', oldname)
            if old is not None:
                pipe.execute_command('DEL', oldname)
            else:
                break
        if(evilredis):
            pieces[1] = evilval
            evilredis.execute_command('SET', *pieces)
        pipe.execute_command('SET', *pieces)
        rets = pipe.execute()
        return rets[-1]
    except WatchError:
        print "(expected) WATCH ERROR, Value not set"
        return False

def test_set2(r, evilredis, evilval, name, value):
    """
    Same as above, but this time evil redis has a pipe, so it's 
    less evil (not a lead pipe).
    """

    ns = r.namespace(name)
    curr_ver = r.global_curr_version(ns)
    if curr_ver is None:
        raise ValueError("ERROR, Bad for current version (None) for key \'" + name +\
              "\'. Global versions are: " + str(r.global_versions(ns)))
    new_name = curr_ver + "|" + name
    pieces = [new_name, value]

    prev = r.global_versions(ns)
    try:
        pipe = r.pipeline()
        pipe.watch(new_name)
        pipe.multi()
        for v in reversed(prev[:-1]):
            oldname = v + "|" + name
            old = pipe.execute_command('GET', oldname)
            if old is not None:
                pipe.execute_command('DEL', oldname)
            else:
                break
        if(evilredis):
            benign_pipe = evilredis.pipeline()
            pieces[1] = evilval
            benign_pipe.execute_command('SET', *pieces)
            pipe.execute_command('SET', *pieces)
            benign_pipe.execute()
        rets = pipe.execute()
        if rets:
            return rets[-1]
        return False
    except WatchError:
        print "(expected) WATCH ERROR, Value not set"
        return False


def test1_set_concurr(actualredis):
    tname = "test1_concurr"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    actualredis.flushall()

    r = lazyupdredis.connect([("mykey", "v0")])
    evilredis = lazyupdredis.connect([("mykey", "v0")])

    # test basic setting
    assert(test_set(r, evilredis, "evil1", "mykey:1", "lalala") == False)
    assert(actualredis.get("v0|mykey:1") == "evil1")
    assert(test_set(r, None, None, "mykey:1", "lalala") == True)
    assert(actualredis.get("v0|mykey:1") == "lalala")

    r.do_upd("data/example_json/concurr_1")
    evilredis = lazyupdredis.connect([("mykey", "v1")])

    # test setting and deleting the old
    assert(test_set(r, None, None, "mykey:2", "fafafa") == True)
    assert(actualredis.get("v1|mykey:2") == "fafafa")
    assert(actualredis.get("v0|mykey:2") == None)

    assert(test_set(r, evilredis, "evil2", "mykey:2", "fafafa") == False)
    assert(actualredis.get("v1|mykey:2") == "evil2")

    # test when both have pipes (actual scenario)
    actualredis.flushall()
    r = lazyupdredis.connect([("mykey", "v0")])
    evilredis = lazyupdredis.connect([("mykey", "v0")])

    assert(test_set2(r, evilredis, "evil1", "mykey:1", "lalala") == False)
    assert(actualredis.get("v0|mykey:1") == "evil1")
    assert(test_set2(r, None, None, "mykey:2", "fafafa") == False)
    assert(actualredis.get("v0|mykey:2") == None)

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"


if __name__ == "__main__":

    # Remove the previous run's generated files, for sanity's sake.
    os.system("rm gen*")

    # non-hooked redis commands to work as orginally specified
    actualredis = redis.StrictRedis()

    # test setting
    test1_set_concurr(actualredis)



