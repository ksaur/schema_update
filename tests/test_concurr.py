import sys, os, re, fnmatch, json
import redis
from redis.exceptions import WatchError

sys.path.append("../src")
import lazyupdredis


def test_set(r, name, value, evilredis, evilval,  withpipe=False):
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
        print "watching " + new_name
        pipe.watch(new_name)
        pipe.multi()
        for v in reversed(prev[:-1]):
            oldname = v + "|" + name
            old = pipe.execute_command('GET', oldname)
            if old is not None:
                pipe.execute_command('DEL', oldname)
            else:
                break
        if(evilredis and withpipe):
                try:
                    benign_pipe = evilredis.pipeline()
                    print "watching " + pieces[0]
                    benign_pipe.watch(pieces[0])
                    benign_pipe.multi()
                    evillist= [pieces[0], evilval]
                    benign_pipe.execute_command('SET', *evillist)
                except WatchError:
                    print "(expected) EVIL REDIS WATCH ERROR, Value not set"
                    return False
        elif evilredis:
            evillist= [pieces[0], evilval]
            print "setting " + pieces[0]
            evilredis.execute_command('SET', *evillist)
        pipe.execute_command('SET', *pieces)
        print "CALLING EXEC"
        rets = pipe.execute()
        if (evilredis and withpipe):
            try:
                print "CALLING EVIL EXEC"
                print benign_pipe.execute()
            except WatchError:
                print "(expected) EVIL REDIS WATCH ERROR, Value not set. RETURNING TRUE"
                return True # expected.
        print rets
        return rets[-1]
    except WatchError:
            print "(expected) WATCH ERROR, Value not set"
            return False


def test_get(r, name, evilredis, evilval, withpipe=False):
    """
    This code should match the code in lazyupdredis "get".  The issue is getting the
    evilredis to modify the key in the split microsecond inbetween the adds, so this
    forces that to happen.
    """

    ns = r.namespace(name)
    global_ns_ver = r.global_curr_version(ns)
    client_ns_ver = r.client_ns_versions[ns]

    # Make sure the client has been updated to this version
    if global_ns_ver != client_ns_ver:
        err= "Could not update key:" + name + ".\nTo continue, " +\
            "you must update namespace \'" + ns + "\' to version " + global_ns_ver +\
            ".  Currently at namespace version " + client_ns_ver +\
            " for \'" + ns + "\'"
        raise DeprecationWarning(err)
    
    # Check to see if we're already current
    orig_name = global_ns_ver + "|" + name
    val = r.execute_command('GET', orig_name)
    # Return immediately if no update is necsesary
    if(val):
        print "\tNo update necessary for key: " + name + " (version = " + global_ns_ver + ")"
        return val

    # No key found at the current version.
    # Try to get a matching key. Ex: if key="foo", try "v0|key", "v1|key", etc
    vers_list = r.global_versions(ns)
    curr_key_version = None
    for v in reversed(vers_list[:-1]): # this will test the most current first
        orig_name = v + "|" + name
        val = r.execute_command('GET', orig_name)
        # Found a key!  Figure out which version and see if it needs updating
        if val is not None:
            curr_key_version = orig_name.split("|", 1)[0]
            ### print "key ns version: " + curr_key_version
            print "GOT KEY " + name + " at VERSION: " + v
            break
    # no key at 'name' for any eversion.
    if curr_key_version == None:
        return None

    ######### LAZY UPDATES HERE!!!! :)  ########

    # Version isn't current.  Now check for updates
    curr_idx = vers_list.index(curr_key_version)
    new_name = vers_list[-1] + "|" + name
    print "\tCurrent key is at position " + str(curr_idx) +\
        " in the udp list, which means that there is/are " + \
        str(len(vers_list)-curr_idx-1) + " more update(s) to apply"

    try:
        pipe = r.pipeline()
        pipe.watch(orig_name)
        # must call "watch" on all before calling multi.
        for upd_v in vers_list[curr_idx+1:]:
            pipe.watch(upd_v + "|" + name)
        pipe.multi()

        # Apply 1 or multiple updates, from oldest to newest, if necessary
        for upd_v in vers_list[curr_idx+1:]:

            # Make sure we have the update in the dictionary
            upd_name = (curr_key_version, upd_v, ns)
            if upd_name not in r.upd_dict:
                err= "Could not update key:" + name + ".  Could not find " +\
                    "update \'" + str(upd_name) +"\' in update dictionary."
                raise KeyError(err)

            # Grab all the information from the update dictionary...
            print "Updating to version " + upd_v + " using update \'" + str(upd_name) +"\'"
            # Combine all of the update functions into a list "upd_funcs_combined"
            #
            # There may be more than one command per update
            #   Ex: for edgeattr:n*@n5 v0->v1
            #       for edgeattr:n4@n* v0->v1
            upd_funcs_combined = list()
            for (module, glob, upd_funcs, new_ver) in r.upd_dict[upd_name]:

                print "Found a rule."
                print "new_ver = " + new_ver + " upd_v = " + upd_v
                # Make sure we have the expected version
                if (new_ver != upd_v):
                    print "ERROR!!! Version mismatch at : " + name + "ver=" + upd_v 
                    return val
                # Check if the keyglob matches this particular key
                # Ex: if the glob wanted key:[1-3] and we are key:4, no update,
                #     eventhough the namespace matches.
                print "Searching for a match with glob = " + glob 
                print "and name = " + name 
                if re.match(fnmatch.translate(glob), name):
                    print "\tUpdating key " + name + " to version: " + upd_v
                    print "\tusing the following functions:" + str(upd_funcs)
                    print "\twith value:" + val
                    upd_funcs_combined.extend(upd_funcs)

            # if we found some functions to call, then call them (all at once) so the
            # version string only gets written once.
            if upd_funcs_combined:  
                print "Applying some updates:" + str(upd_funcs_combined)
                mod = r.update(name, val, upd_funcs_combined, module)
                if mod:
                    mod[0] = upd_v + "|" + mod[0]
                    print "was watching" +orig_name
                    print "now fucking with" + mod[0]
                    if(evilredis):
                        mod[1] = evilval
                        if(withpipe):
                            benignpipe = evilredis.pipeline()
                            print "watching " + mod[0] + " " + orig_name
                            benignpipe.watch(mod[0])
                            benignpipe.watch(orig_name)
                            benignpipe.multi()
                            pipe.execute_command('SET', *mod)
                            benignpipe.execute_command('SET', *mod)
                            pipe.execute_command('DEL', curr_key_version+ "|" + name)
                            benignpipe.execute_command('GET', mod[0])
                            print benignpipe.execute()
                        else:
                            evilredis.execute_command('SET', *mod)
                            evilredis.execute_command('GET', mod[0])
                    else:
                        pipe.execute_command('SET', *mod)
                        pipe.execute_command('DEL', curr_key_version+ "|" + name)
                    curr_key_version = new_ver
                else:
                    raise ValueError( "ERROR!!! Could not update key: " + name )
            # no functions matched, update version string only.                   
            else:
                print "\tNo functions matched.  Updating version str only"
                print "orig_name "+orig_name + " -> new_name " +new_name
                pipe.rename(orig_name, new_name)
        # now get and return the updated value
        pipe.execute_command('GET', new_name)
        rets = pipe.execute()
        if rets:
            return rets[-1]
        return None
    except WatchError:
        print "WATCH ERROR, Value not set"
        return False #TODO what to return here?!?!


def test1_set_concurr(actualredis):
    tname = "test1_concurr"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    actualredis.flushall()

    r = lazyupdredis.connect([("mykey", "v0")])
    evilredis = lazyupdredis.connect([("mykey", "v0")])

    # test basic setting
    assert(test_set(r, "mykey:1", "lalala", evilredis, "evil1") == False)
    assert(actualredis.get("v0|mykey:1") == "evil1")
    assert(test_set(r, "mykey:1", "lalala", None, None) == True)
    assert(actualredis.get("v0|mykey:1") == "lalala")

    r.do_upd("data/example_json/concurr_1")
    evilredis = lazyupdredis.connect([("mykey", "v1")])

    # test setting and deleting the old
    assert(test_set(r, "mykey:2", "fafafa", None, None) == True)
    assert(actualredis.get("v1|mykey:2") == "fafafa")
    assert(actualredis.get("v0|mykey:2") == None)

    # evil redis isn't using concurrency control, so it wins.
    assert(test_set(r, "mykey:2", "fafafa", evilredis, "evil2") == False)
    assert(actualredis.get("v1|mykey:2") == "evil2")

    # test when both have pipes (actual scenario)
    actualredis.flushall()
    r = lazyupdredis.connect([("mykey", "v0")])
    evilredis = lazyupdredis.connect([("mykey", "v0")])

    assert(test_set(r, "mykey:2", "fafafa", evilredis, "evil2", True) == True)
    assert(actualredis.get("v0|mykey:2") == "fafafa")

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

def test2_get_concurr(actualredis):
    tname = "test2_concurr"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    actualredis.flushall()

    r = lazyupdredis.connect([("edgeattr", "v0")])
    evilredis = lazyupdredis.connect([("edgeattr", "v0")])
    val = json.dumps({"outport" : None, "inport" : None})
    evilval = json.dumps({"outport" : 667, "inport" : 668})
    r.set("edgeattr:2", val)
    r.set("edgeattr:3", val)

    # test basic get
    assert(test_get(r, "edgeattr:2", None, None) is not None)
   
    # test out lazy!
    r.do_upd("data/example_json/lazy_3_init")
    evilredis = lazyupdredis.connect([("edgeattr", "v1")])

    # test getting and deleting the old for key 2
    assert(test_get(r, "edgeattr:2", None, None) == "{\"outport\": 777, \"inport\": 999}")
    assert(actualredis.get("v1|edgeattr:2") != None)
    assert(actualredis.get("v0|edgeattr:2") == None)

    # now test out with evil redis for key 3
    print "Expecting a watch error: "
    assert(test_get(r, "edgeattr:3", evilredis, evilval) == False)
    assert(actualredis.get("v0|edgeattr:3") == val) 
    
    # test when both have pipes (actual scenario)
    actualredis.flushall()
    r = lazyupdredis.connect([("edgeattr", "v0")])
    r.set("edgeattr:2", val)

    r.do_upd("data/example_json/lazy_3_init")
    evilredis = lazyupdredis.connect([("edgeattr", "v1")])

    assert(test_get(r, "edgeattr:2", evilredis, evilval, True) == False)
#    assert(actualredis.get("v0|mykey:1") == "evil1")
#    assert(test_get(r, None, None, "mykey:2", "fafafa") == False)
#    assert(actualredis.get("v0|mykey:2") == None)

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"


if __name__ == "__main__":

    # Remove the previous run's generated files, for sanity's sake.
    os.system("rm gen*")

    # non-hooked redis commands to work as orginally specified
    actualredis = redis.StrictRedis()

    # test setting
    test1_set_concurr(actualredis)

    # test getting
    test2_get_concurr(actualredis)


