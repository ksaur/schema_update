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
def test1(r, actualredis):
    tname = "test1_z"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    reset(r)
    # create the update file
    json_patch_creator.process_dsl("data/example_json/lazy_1_init", tname +".py")
    shutil.move(tname +".py", "../generated/generated_"+tname+".py")

    # add an entry
    cat_a = "{ \"_id\": \"4bd8ae97c47016442af4a580\", \"customerid\": 99999, \"name\": \"Foo Sushi Inc\", \"since\": \"12/12/2001\", \"category\": \"A\", \"order\": { \"orderid\": \"UXWE-122012\", \"orderdate\": \"12/12/2001\", \"orderItems\": [ { \"product\": \"Fortune Cookies\",   \"price\": 19.99 },{ \"product\": \"Edamame\",   \"price\": 29.99 } ] } }"
    cat_b = "{ \"_id\": \"4bd8ae97c47016442af4a580\", \"customerid\": 99999, \"name\": \"Foo Sushi Inc\", \"since\": \"12/12/2001\", \"category\": \"B\", \"order\": { \"orderid\": \"UXWE-122012\", \"orderdate\": \"12/12/2001\", \"orderItems\": [ { \"product\": \"Fortune Cookies\",   \"price\": 19.99 },{ \"product\": \"Edamame\",   \"price\": 29.99 } ] } }"
    r.set("key1", cat_a)
    r.set("key2", cat_b)
    # make sure data added
    e = r.get("key1")
    assert (e) is not None
    assert(r.get("key2") is not None)
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone["_id"] == "4bd8ae97c47016442af4a580")
    assert(((jsone["order"].get("orderItems"))[0]).get("price") == 19.99)
    assert(((jsone["order"].get("orderItems"))[1]).get("price") == 29.99)
    assert("fullprice" not in jsone)
    assert("category" in jsone)

    # make sure the version string got loaded in actualredis
    assert(len(r.keys("*")) == 2)
    assert(len(actualredis.keys("*")) == 3)
    assert(actualredis.lrange("UPDATE_VERSIONS", 0, -1) == ["INITIAL_V0"])

    # Make sure the versioning works for the udpate 
    print "Performing update for " + tname
    r.do_upd("generated_" + tname,)
    print actualredis.lrange("UPDATE_VERSIONS", 0, -1)
    assert(actualredis.lrange("UPDATE_VERSIONS", 0, -1) == ["INITIAL_V0", "V1"])
    assert(r.versions() == ["INITIAL_V0", "V1"]) 
    assert(r.curr_version() == "V1") 
    assert(r.hget("UPDATE_FILES", "V1") == ("generated_" + tname))
    print r.upd_dict["V1"]
    correctd = [('key*', ['group_1_update_category', 'group_1_update__id', 'group_1_update_order']), ('edgeattr_n*@n5', ['group_2_update_outport'])]
    assert(r.upd_dict["V1"][1] == correctd)

    # make sure that the new module loads on a new connection
    r2 = lazyupdredis.connect()
    assert(r2.versions() == ["INITIAL_V0", "V1"]) 
    assert(r2.curr_version() == "V1") 
    assert(r2.hget("UPDATE_FILES", "V1") == ("generated_" + tname))
    print (r2.upd_dict["V1"][1])
    assert(r2.upd_dict["V1"][1] == correctd)

    # test that the expected keys are added
    assert(r.get("edgeattr_n2@n1") is not None)
    # should have skipped n4
    assert(r.get("edgeattr_n1@n4") is None)
    e = r.get("edgeattr_n1@n5")
    assert(e is not None)
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone.get("inport") is None)
    assert(jsone.get("outport") is None)
    
    print "here is the giant mess you have to work with:"
    print r.upd_dict
    
    # test that the update worked
    # make sure that it hasn't happened on-demand by checking in non-hooked redis
    e = actualredis.get("INITIAL_V0|edgeattr_n2@n5") # must include tag in actual redis
    assert(e is not None)
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone.get("outport") is None)
    # now, when we grab it in lazy redis, the update should happen on-demand
    #e = r.get("edgeattr_n2@n5")
    #jsone = json.loads(e,object_hook=decode.decode_dict)
    #assert(jsone.get("outport") == 777)
    # and i

    #numupd = do_upd.do_upd(r, "generated_" + tname)
    #e = r.get("key1")
    #assert (e) is not None
    #jsone = json.loads(e,object_hook=decode.decode_dict)
    ## test for expected values
    ## test UPD
    #assert(jsone["_id"] == 23473328205018852615364322688) #hex to dec
    ## test REN
    #assert(((jsone["order"].get("orderItems"))[0]).get("fullprice") == 19.99)
    #assert("price" not in jsone)
    ## test INIT
    #assert(((jsone["order"].get("orderItems"))[0]).get("discountedPrice") == 13.99)
    ## (test arrays)
    #assert(((jsone["order"].get("orderItems"))[1]).get("discountedPrice") == 20.99)
    ## test DEL
    #assert("category" not in jsone)

    #e = r.get("key2")
    #assert (e) is not None
    #jsone = json.loads(e,object_hook=decode.decode_dict)
    #assert("category" in jsone)

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"



def main():
    # non-hooked redis commands to work as orginally specified
    actualredis = redis.StrictRedis()
    actualredis.flushall() # wipes out all version string after tests are done

    # connect to Redis
    r = lazyupdredis.connect()

    # test basic INIT, ADD, REN, UPD for fullpaths
    test1(r, actualredis)

    r.execute_command('QUIT')


if __name__ == '__main__':
    main()
