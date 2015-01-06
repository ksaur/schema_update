"""
Load some test data in the database, update, and test for expected results.

"""
import json
import redis
import sys
import shutil
sys.path.append("../jsondiffpatch_generator") #TODO separate directory?
import decode
import do_upd
import json_patch_creator

def reset(r):
    # clear out old data from redis
    r.flushall()
    # other stuff?


# test basic INIT, ADD, REN, UPD for fullpaths
def test1(r):
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  TEST1  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    reset(r)
    # create the update file
    json_patch_creator.process_dsl("../example_json/sadalage_init", "test1.py")
    shutil.move("test1.py", "../jsondiffpatch_generator/generated_test1.py")

    # add an entry
    s = "{ \"_id\": \"4bd8ae97c47016442af4a580\", \"customerid\": 99999, \"name\": \"Foo Sushi Inc\", \"since\": \"12/12/2001\", \"category\": \"A\", \"order\": { \"orderid\": \"UXWE-122012\", \"orderdate\": \"12/12/2001\", \"orderItems\": [ { \"product\": \"Fortune Cookies\",   \"price\": 19.99 },{ \"product\": \"Edamame\",   \"price\": 29.99 } ] } }"
    r.set("key1", s)
    # make sure data added
    e = r.get("key1")
    assert (e) is not None
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone["_id"] == "4bd8ae97c47016442af4a580")
    assert(((jsone["order"].get("orderItems"))[0]).get("price") == 19.99)
    assert(((jsone["order"].get("orderItems"))[1]).get("price") == 29.99)
    assert("fullprice" not in jsone)
    assert("category" in jsone)

    # perform the update and grab the updated value (Also test including the extension on filename)
    do_upd.do_upd(r, "generated_test1.py")
    e = r.get("key1")
    assert (e) is not None
    jsone = json.loads(e,object_hook=decode.decode_dict)
    # test for expected values
    # test UPD
    assert(jsone["_id"] == 23473328205018852615364322688) #hex to dec
    # test REN
    assert(((jsone["order"].get("orderItems"))[0]).get("fullprice") == 19.99)
    assert("price" not in jsone)
    # test INIT
    assert(((jsone["order"].get("orderItems"))[0]).get("discountedPrice") == 13.99)
    # (test arrays)
    assert(((jsone["order"].get("orderItems"))[1]).get("discountedPrice") == 20.99)
    # test DEL
    assert("category" not in jsone)


    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  (TEST1)  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"


# tests for keys  #TODO implement....
def test2(r):
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  TEST2  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    reset(r)

    # create the update file
#    json_patch_creator.process_dsl("../example_json/keys_init")
#    shutil.move("dsu.py", "../jsondiffpatch_generator/dsu.py")

    # add an entry (http://www.sitepoint.com/customer-form-json-file-example/)
    v = "{ \"firstName\": \"John\", \"lastName\": \"Smith\", \"age\": 25, \"address\": { \"streetAddress\": \"21 2nd Street\", \"city\": \"New York\", \"state\": \"NY\", \"postalCode\": \"10021\" }, \"phoneNumber\": [ { \"type\": \"home\", \"number\": \"212 555-1234\" }, { \"type\": \"fax\", \"number\": \"646 555-4567\" } ] }"
    r.set("key1", v)
    v= v.replace("5","7")
    r.set("key2", v)
    # make sure data added
    e = r.get("key1")
    assert (e) is not None
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone.get("phoneNumber")[0].get("number") == "212 555-1234")
    e = r.get("key2")
    assert (e) is not None
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone.get("phoneNumber")[0].get("number") == "212 777-1234")

#    # perform the update and grab the updated value
#    do_upd.do_upd(r)
#    e = r.get("key1")
#    assert (e) is not None
#    jsone = json.loads(e,object_hook=decode.decode_dict)
#    # test for expected values
#    # test UPD
#    assert(jsone["_id"] == 23473328205018852615364322688) #hex to dec
#    # test REN
#    assert(((jsone["order"].get("orderItems"))[0]).get("fullprice") == 19.99)
#    assert("price" not in jsone)
#    # test INIT
#    assert(((jsone["order"].get("orderItems"))[0]).get("discountedPrice") == 13.99)
#    # test DEL
#    assert("category" not in jsone)


    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  (TEST2)  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

# Demonstrate the usages of $in $out $root $base
def test3(r):
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  TEST3  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
    reset(r)

    # create the update file
    json_patch_creator.process_dsl("../example_json/in_out_upd", "test3.py")
    shutil.move("test3.py", "../jsondiffpatch_generator/generated_test3.py")

    v = "{ \"name\": \"Foo Bar Industries\", \"orderdate\": \"12/12/2014\", \"order\": { \"orderid\": \"UUUXBSI\", \"orderitems\": [ { \"product\": \"Foo Bar Ball\", \"percentfullprice\": 0.7, \"price\": 13.99 }, { \"product\": \"Foo Bar Stool\", \"percentfullprice\": 0.7, \"price\": 13.99 } ] } }"
    r.set("key1", v)
    # make sure data added
    e = r.get("key1")
    assert (e) is not None
    jsone = json.loads(e,object_hook=decode.decode_dict)
    print jsone.get("order").get("orderitems")[0]
    assert(jsone.get("order").get("orderitems")[0].get("percentfullprice") == 0.7)
    assert(jsone.get("order").get("orderitems")[0].get("price") == 13.99)
    assert(jsone.get("order").get("orderid") == "UUUXBSI")

    # perform the update and grab the updated value.  (Also test leaving off the extension from filename)
    do_upd.do_upd(r, "generated_test3")
    e = r.get("key1")
    assert (e) is not None
    jsone = json.loads(e,object_hook=decode.decode_dict)
    # test for expected values
    # test UPD
    print jsone
    assert(jsone.get("order").get("orderitems")[0].get("percentfullprice") == 1.0)
    assert(jsone.get("order").get("orderitems")[0].get("price") == 19.99)
    assert(jsone.get("order").get("orderid") == "UUUXBSI_12122014")


    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  (TEST3)  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

def main():
    # connect to Redis
    r = do_upd.connect()

    # test basic INIT, ADD, REN, UPD for fullpaths
    test1(r)
    # tests for keys
    test2(r)
    # tests for $out and $in
    test3(r)

    r.execute_command('QUIT')


if __name__ == '__main__':
    main()
