"""
Load some test data in the database, update, and test for expected results.

"""
import json
import sys
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


    # create the update file
    json_patch_creator.process_dsl("data/example_json/lazy_1_init", tname +".py")
    shutil.move(tname +".py", "../generated/generated_"+tname+".py")

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
    r.do_upd("generated_" + tname)
    assert(actualredis.lrange("UPDATE_VERSIONS_edgeattr", 0, -1)==["v0", "v1"] )
    # adding new entries is done on demand, so should have new values 
    assert(r.curr_version("edgeattr") == "v1")
    assert(r.versions("edgeattr") == ["v0", "v1"]) 
    assert(actualredis.hget("UPDATE_FILES", "v1|edgeattr") == ("generated_" + tname))

    # make sure the other updates also got loaded
    assert(r.curr_version("key") == "ver1")
    print r.upd_dict

    # test setting...should blow away old versions
    r.set("edgeattr:n9@n2", "{\"outport\": 2, \"inport\": 9}")
    assert(actualredis.get("v0|edgeattr:n9@n2") is None)
    assert(actualredis.get("v1|edgeattr:n9@n2") is not None)

    # make sure that the new module loads on a new connection
    r2 = lazyupdredis.connect([("key", "ver1"), ("edgeattr", "v1")])
    assert(r2.versions("edgeattr") == ["v0", "v1"]) 
    assert(r2.curr_version("edgeattr") == "v1") 
    assert(r2.hget("UPDATE_FILES", "v1|edgeattr") == ("generated_" + tname))

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

    # create the update file
    json_patch_creator.process_dsl("data/example_json/lazy_2_init", tname +".py")
    shutil.move(tname +".py", "../generated/generated_"+tname+".py")

    #The globs:
    #  edgeattr:n*@n5
    #  edgeattr:n4@n*
    r.do_upd("generated_" + tname)
    print "update dict is:"
    print r.upd_dict

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

# TODO don't allow connect to v0
def test3(actualredis):
    tname = "test3_z"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    reset(actualredis)
    # connect to Redis
    json_val = json.dumps({"outport": None, "inport": None})
    r = lazyupdredis.connect([("edgeattr", "v0")])
    for (i,j) in [("9","5"), ("2","3"), ("4","2")]:
        r.set("edgeattr:n" + i + "@n" + j, json_val)

    # create the update file v0->v1
    json_patch_creator.process_dsl("data/example_json/lazy_3_init", tname +".py")
    shutil.move(tname +".py", "../generated/generated_"+tname+".py")

    r.do_upd("generated_" + tname)

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
    json_patch_creator.process_dsl("data/example_json/lazy_3b_init", tname +"2.py")
    shutil.move(tname +"2.py", "../generated/generated_"+tname+"2.py")

    r.do_upd("generated_" + tname + "2")

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


def main():
    # non-hooked redis commands to work as orginally specified
    actualredis = redis.StrictRedis()

    # test basic lazy updates
    #test1(actualredis)
    # test exists/not exists cominations
    #test2(actualredis)
    # test multi update cmds; test multi updates.
    test3(actualredis)

    actualredis.execute_command('QUIT')


if __name__ == '__main__':
    main()
