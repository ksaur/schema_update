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
    r = lazyupdredis.connect([("key", "INITIAL_V0"), ("edgeattr", "INITIAL_V0")])
    assert(actualredis.lrange("UPDATE_VERSIONS_key", 0, -1) == ["INITIAL_V0"])
    assert(actualredis.lrange("UPDATE_VERSIONS_edgeattr", 0, -1) == ["INITIAL_V0"])


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

    # Make sure the versioning works for the udpate 
    print "Performing update for " + tname
    r.do_upd("generated_" + tname)
#    print actualredis.lrange("UPDATE_VERSIONS", 0, -1)
#    assert(actualredis.lrange("UPDATE_VERSIONS", 0, -1) == ["INITIAL_V0", "V1"])
#    assert(r.versions() == ["INITIAL_V0", "V1"]) 
#    assert(r.curr_version() == "V1") 
#    assert(r.hget("UPDATE_FILES", "V1") == ("generated_" + tname))
#    print r.upd_dict["V1"]
##    correctd = [('key*', ['group_1_update_category', 'group_1_update__id', 'group_1_update_order']), ('edgeattr_n*@n5', ['group_2_update_outport'])]
##    assert(r.upd_dict["V1"][1] == correctd)
#
#    # make sure that the new module loads on a new connection
#    r2 = lazyupdredis.connect([])
#    assert(r2.versions() == ["INITIAL_V0", "V1"]) 
#    assert(r2.curr_version() == "V1") 
#    assert(r2.hget("UPDATE_FILES", "V1") == ("generated_" + tname))
#    print (r2.upd_dict["V1"][1])
##    assert(r2.upd_dict["V1"][1] == correctd)
#
#    # test that the expected keys are added
#    assert(r.get("edgeattr:n1@n2") is not None)
#    # should have skipped n4
#    assert(r.get("edgeattr:n1@n4") is None)
#    
#    # test that the update worked
#    # make sure that it hasn't happened on-demand by checking in non-hooked redis
#    e = actualredis.get("INITIAL_V0|edgeattr:n2@n5") # must include tag in actual redis
#    assert(e is not None)
#    jsone = json.loads(e,object_hook=decode.decode_dict)
#    assert(jsone.get("outport") is None)
#    # now, when we grab it in lazy redis, the update should happen on-demand
#    e = r.get("edgeattr:n2@n5")
#    jsone = json.loads(e,object_hook=decode.decode_dict)
#    assert(jsone.get("outport") == 777)
#
#    # At this point, keys "edgeattr_n1@n2" and "edgeattr_n2@n5" are the only two "touched"
#    # Make sure of this using actualredis
#    # These keys at V1:  n1@n2, n2@n5
#    assert(len(actualredis.keys("V1*")) == 2) 
#    # These keys at key1, key2, n1@n1, n1@3, n1@n5, n2@n1, n2@n2, n2@n3
#    assert(len(actualredis.keys("INITIAL_V0*")) == 8) 
   

    print r.upd_dict


    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"



def main():
    # non-hooked redis commands to work as orginally specified
    actualredis = redis.StrictRedis()

    # test basic lazy updates
    test1(actualredis)

    actualredis.execute_command('QUIT')


if __name__ == '__main__':
    main()
