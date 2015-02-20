"""
Load some test data in the database, update, and test for expected results.

"""
import json
import sys, os
import shutil
sys.path.append("../src")
sys.path.append("../generated")
import decode
import json_patch_creator
import redis
import lazyupdredis

# Note: don't call flushall on actualredis.  This functionality isn't available
# to the user and will blow away the version information
def reset(r):
    # clear out old data from redis
    r.flushall()
    # other stuff?


# test version string in lazy redis.  
# test basic lazy update functionality 
def test1(actualredis):

    tname = "test1_z"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    reset(actualredis)

    # connect to Redis
    r = lazyupdredis.connect([("key", "ver0"), ("edgeattr", "v0")])
    assert(actualredis.lrange("UPDATE_VERSIONS_key", 0, -1) == ["ver0"])
    assert(actualredis.lrange("UPDATE_VERSIONS_edgeattr", 0, -1) == ["v0"])

    # add an entry
    cat_a = "{ \"_id\": \"4bd8ae97c47016442af4a580\", \"customerid\": 99999, \"name\": \"Foo Sushi Inc\", \"since\": \"12/12/2001\", \"category\": \"A\", \"order\": { \"orderid\": \"UXWE-122012\", \"orderdate\": \"12/12/2001\", \"orderItems\": [ { \"product\": \"Fortune Cookies\",   \"price\": 19.99 },{ \"product\": \"Edamame\",   \"price\": 29.99 } ] } }"
    cat_b = "{ \"_id\": \"4bd8ae97c47016442af4a580\", \"customerid\": 99999, \"name\": \"Foo Sushi Inc\", \"since\": \"12/12/2001\", \"category\": \"B\", \"order\": { \"orderid\": \"UXWE-122012\", \"orderdate\": \"12/12/2001\", \"orderItems\": [ { \"product\": \"Fortune Cookies\",   \"price\": 19.99 },{ \"product\": \"Edamame\",   \"price\": 29.99 } ] } }"
    r.set("key:1", cat_a)
    r.set("key:2", cat_b)
    r.set("edgeattr:n9@n2", "{\"outport\": None, \"inport\": None}")
    # make sure data added
    e = r.get("key:1")
    assert (e) is not None
    assert(r.get("key:2") is not None)
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone["_id"] == "4bd8ae97c47016442af4a580")
    assert(((jsone["order"].get("orderItems"))[0]).get("price") == 19.99)
    assert(((jsone["order"].get("orderItems"))[1]).get("price") == 29.99)
    assert("fullprice" not in jsone)
    assert("category" in jsone)

    # make sure the version string got loaded in actualredis
    assert(len(r.keys("*")) == 3)
    assert(len(actualredis.keys("*")) == 5) # key:1 key:2 edgettr92 UPDV:key UPDV:edge
 
    #TODO test "nones" with no namespaces

    # Make sure the versioning works for the udpate 
    print "Performing update for " + tname
    r.do_upd("data/example_json/lazy_1_init")

    assert(actualredis.lrange("UPDATE_VERSIONS_edgeattr", 0, -1)==["v0", "v1"] )
    # adding new entries is done on demand, so should have new values 
    assert(r.global_curr_version("edgeattr") == "v1")
    assert(r.global_versions("edgeattr") == ["v0", "v1"]) 

    # make sure the other updates also got loaded
    assert(r.global_curr_version("key") == "ver1")
    print r.upd_dict

    # test setting...should blow away old versions
    r.set("edgeattr:n9@n2", "{\"outport\": 2, \"inport\": 9}")
    assert(actualredis.get("v0|edgeattr:n9@n2") is None)
    assert(actualredis.get("v1|edgeattr:n9@n2") is not None)

    # make sure that the new module loads on a new connection
    r2 = lazyupdredis.connect([("key", "ver1"), ("edgeattr", "v1")])
    assert(r2.global_versions("edgeattr") == ["v0", "v1"]) 
    assert(r2.global_curr_version("edgeattr") == "v1") 

    # test that the expected keys are added
    assert(r.get("edgeattr:n1@n2") is not None)
    # should have skipped n4
    assert(r.get("edgeattr:n1@n4") is None)
    
    # test that the update worked
    # make sure that it hasn't happened on-demand by checking in non-hooked redis
    e = actualredis.get("ver0|key:1") # must include tag in actual redis
    assert(e is not None)
    # now, when we grab it in lazy redis, the update should happen on-demand
    e = r.get("key:1")
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(((jsone["order"].get("orderItems"))[0]).get("fullprice") == 19.99)
    # make sure the old is gone
    assert(actualredis.get("ver0|key:1") is None)
    assert(actualredis.get("ver1|key:1") is not None)

    # These keys at v0: key2, 
    assert(len(actualredis.keys("v*0*")) == 1) 
    # Rest of keys at v1/ver1
    assert(len(actualredis.keys("v*1*")) == 10)

    # test deletions
    r.delete("edgeattr:n2@n2", "edgeattr:n1@n1")
    assert(r.get("edgeattr:n2@n2") is None)
    assert(actualredis.get("v0|edgeattr:n2@n2") is None)
    assert(len(actualredis.keys("v*1*")) == 8)

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"


# Test combintations of key existing/update existing
def test2(actualredis):

    tname = "test2_z"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    reset(actualredis)

    # connect to Redis
    json_val = json.dumps({"outport": None, "inport": None})
    r = lazyupdredis.connect([("edgeattr", "v0")])
    for (i,j) in [("1","2"), ("2","3"), ("4","2"), ("4","6"), ("5","2"), ("9","5")]:
        r.set("edgeattr:n" + i + "@n" + j, json_val)

    #The globs:
    #  edgeattr:n*@n5
    #  edgeattr:n4@n*
    r.do_upd("data/example_json/lazy_2_init")

    # key exists, update exists
    assert(actualredis.get("v0|edgeattr:n9@n5") is not None)
    e = r.get("edgeattr:n9@n5")
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone["outport"] == 777 )
    assert(actualredis.get("v1|edgeattr:n9@n5") is not None)
    assert(actualredis.get("v0|edgeattr:n9@n5") is None)

    # key does not exist, update exists
    assert(r.get("edgeattr:n4@n7") is None)

    ## key exists, update does not exist
    assert(actualredis.get("v0|edgeattr:n5@n2") is not None)
    e = r.get("edgeattr:n5@n2")
    print e
    jsone = json.loads(e,object_hook=decode.decode_dict)
    print jsone
    assert(jsone["outport"] == None )
    assert(actualredis.get("v1|edgeattr:n5@n2") is not None)
    assert(actualredis.get("v0|edgeattr:n5@n2") is None)

    ## key does not exist, update does not exist
    assert(r.get("edgeattr:n1@n9") is None)


    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

# test multi update cmds; test multi updates.
def test3(actualredis):
    tname = "test3_z"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    reset(actualredis)
    # connect to Redis
    json_val = json.dumps({"outport": None, "inport": None})
    r = lazyupdredis.connect([("edgeattr", "v0")])
    for (i,j) in [("9","5"), ("2","3"), ("4","2")]:
        r.set("edgeattr:n" + i + "@n" + j, json_val)

    # load the update file v0->v1
    r.do_upd("data/example_json/lazy_3_init")

    # test combining "for" statements for the same update...
    assert(actualredis.get("v0|edgeattr:n9@n5") is not None)
    e = r.get("edgeattr:n9@n5")
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone["outport"] == 777 )
    assert(jsone["inport"] == 999 )
    assert(actualredis.get("v1|edgeattr:n9@n5") is not None)
    assert(actualredis.get("v0|edgeattr:n9@n5") is None)


    # test multi-version updates

    # create the update file v1->v2
    r.do_upd("data/example_json/lazy_3b_init")

    # test going from v1->v2 for (n9@n5)
    print "\n**************** Testing going v1->v2 for n9@n5 *********************"
    assert(actualredis.get("v1|edgeattr:n9@n5") is not None)
    e = r.get("edgeattr:n9@n5")
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone["outport"] == 555 )
    assert(jsone["inport"] == 333 )
    assert(actualredis.get("v2|edgeattr:n9@n5") is not None)
    assert(actualredis.get("v1|edgeattr:n9@n5") is None)
    assert(actualredis.get("v0|edgeattr:n9@n5") is None)
    assert(len(actualredis.keys("*edgeattr:n9@n5")) == 1)

    # test going from v0->v1->v2 for (n2@n3)
    print "\n**************** Testing going v0->v1->v2 for n2@n3 *********************"
    # make sure it's still untouched
    e = actualredis.get("v0|edgeattr:n2@n3")
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone["outport"] == None )
    assert(jsone["inport"] == None )
    # Now grab the key to trigger both updates
    e = r.get("edgeattr:n2@n3")
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone["outport"] == 555 )
    assert(jsone["inport"] == 333 )
    assert(actualredis.get("v2|edgeattr:n2@n3") is not None)
    assert(actualredis.get("v1|edgeattr:n2@n3") is None)
    assert(actualredis.get("v0|edgeattr:n2@n3") is None)
    assert(len(actualredis.keys("*edgeattr:n2@n3")) == 1)

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"


# Make sure to connect to the correct versions
def test4(actualredis):
    tname = "test4_z"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    reset(actualredis)
    # connect to Redis
    json_val = json.dumps({"outport": None, "inport": None})
    r = lazyupdredis.connect([("edgeattr", "v0")])
    for (i,j) in [("9","5"), ("2","3"), ("4","2")]:
        r.set("edgeattr:n" + i + "@n" + j, json_val)

    # load the update file v0->v1
    r.do_upd("data/example_json/lazy_3_init")

    # make sure update applied
    assert(actualredis.get("v0|edgeattr:n9@n5") is not None)
    e = r.get("edgeattr:n9@n5")
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone["outport"] == 777 )


    # now try to connect to the current (correct) version, should succeed
    r2 = lazyupdredis.connect([("edgeattr", "v1")])
    print r2.upd_dict
    e = r.get("edgeattr:n9@n5")
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone["outport"] == 777 )
    # make sure the new client can also do updates
    e = r.get("edgeattr:n4@n2")
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone["outport"] == 777 )


    # now try to connect to and old version.  we should only be able to connect
    # to the new version, should fail
    print "This should print \"Fatal - old version\":"
    print "\t",
    try:
       r3 = lazyupdredis.connect([("edgeattr", "v0")])
       assert False, "Should have thrown an exception on previous line"
    except ValueError as e:
       print e

    # now try to connect to some madeup version....should fail, since the namespace exists
    print "This should print \"Fatal - bogus version\":"
    print "\t",
    try:
       r4 = lazyupdredis.connect([("edgeattr", "v9")])
       assert False, "Should have thrown an exception on previous line"
    except ValueError as e:
       print e


    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

# Have two clients (r1 and r2) connected at v0. Have r1 ask for an update to v1. Have r2 see the update.
def test5(actualredis):
    tname = "test5_z"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    reset(actualredis)

    # Two clients connect to Redis
    r1 = lazyupdredis.connect([("edgeattr", "v0")])
    r2 = lazyupdredis.connect([("edgeattr", "v0")])

    json_val = json.dumps({"outport": None, "inport": None})
    for (i,j) in [("9","5"), ("2","3"), ("4","2")]:
        r1.set("edgeattr:n" + i + "@n" + j, json_val)

    # load the update file v0->v1
    r1.do_upd("data/example_json/lazy_3_init")

    # make sure update applied


    # New Client (r1 at v1|edgeattr), Old Data (v0|egdeattr)
    assert(actualredis.get("v0|edgeattr:n9@n5") is not None)
    val = r1.get("edgeattr:n9@n5")
    jsone = json.loads(val,object_hook=decode.decode_dict)
    assert(jsone["outport"] == 777 )


    # Old Client (r2 at v0|edgeattr), Old Data (v0|egdeattr)
    # TODO: this is technically OK.   What to do here?
    # This client is asking for an old key at an old version
    # But redis knows that there should be an update...
    print "This should print a DeprecationWarning\":"
    print "\t",
    try:
        r2.get("edgeattr:n4@n2")
        assert False, "Should have thrown DeprecationWarning on previous line"
    except DeprecationWarning as e:
        print e

    # Old Client (r2 at v0|edgeattr), New Data (v1|egdeattr)
    assert(actualredis.get("v0|edgeattr:n9@n5") is None)
    assert(actualredis.get("v1|edgeattr:n9@n5") is not None)
    print "This should print a DeprecationWarning\":"
    print "\t",
    try:
        r2.get("edgeattr:n9@n5")
        assert False, "Should have thrown Deprecation on previous line"
    except DeprecationWarning as e:
        print e



    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

# Test default (no) namepsaces for backward compatibility
def test6(actualredis):
    tname = "test6_z"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    reset(actualredis)
    #  connect to Redis using a default namespace
    r = lazyupdredis.connect([("*", "fw_v0")])

    x = [ { "trusted_ip": "A", "trusted_port": "B", "untrusted_ip": "D", "untrusted_port": "C" },
     { "trusted_ip": "A", "trusted_port": "B", "untrusted_ip": "D", "untrusted_port": "C" }]
    r.set("fw_allowed", json.dumps(x))

    # update with crazy_init, which uses no namespace
    r.do_upd("data/example_json/crazy_init")

    e = r.get("fw_allowed")
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone[0].get("returned") == 0)

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

# Test that user provides the correct name for updating
def test7(actualredis):
    tname = "test7_z"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    reset(actualredis)

    #  connect to Redis using a default namespace
    r = lazyupdredis.connect([("*", "nonsense")])

    x = [ { "trusted_ip": "A", "trusted_port": "B", "untrusted_ip": "D", "untrusted_port": "C" },
     { "trusted_ip": "A", "trusted_port": "B", "untrusted_ip": "D", "untrusted_port": "C" }]
    r.set("fw_allowed", json.dumps(x))

    # This udpate specifies fw_v0->fw_v1, but we are are "nonsense" version
    print "This should print a KeyError\":"
    print "\t",
    try:
        r.do_upd("data/example_json/crazy_init")
        assert False, "Should have thrown KeyError on previous line"
    except KeyError as e:
        print e
    assert(actualredis.lrange("UPDATE_VERSIONS_*", 0 ,-1) == ["nonsense"])

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"


def main():

    # Remove the previous run's generated files, for sanity's sake.
    os.system("rm gen*")

    # non-hooked redis commands to work as orginally specified
    actualredis = redis.StrictRedis()

    # test basic lazy updates
    test1(actualredis)
    # test exists/not exists cominations
    test2(actualredis)
    # test multi update cmds; test multi updates.
    test3(actualredis)
    # don't allow connect to previous version
    test4(actualredis)
    # Have two clients (r1 and r2) connected at v0. Have r1 ask for an update to v1. 
    # Then have r2 try to do a get, and realize it's behind..
    test5(actualredis)
    # Test default (no) namepsaces for backward compatibility
    test6(actualredis)
    # Test that user provides the correct name for updating
    test7(actualredis)

    actualredis.execute_command('QUIT')


if __name__ == '__main__':
    main()
