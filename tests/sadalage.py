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


def test1():
    # create the update file
    json_patch_creator.process_dsl("../example_json/sadalage_init")
    shutil.move("dsu.py", "../jsondiffpatch_generator/dsu.py") #TODO params...but how to call __import__ ('dsu')?

    r = do_upd.connect()
    # clear out old data
    r.flushall()
    # add an entry
    s = "{ \"_id\": \"4bd8ae97c47016442af4a580\", \"customerid\": 99999, \"name\": \"Foo Sushi Inc\", \"since\": \"12/12/2001\", \"order\": { \"orderid\": \"UXWE-122012\", \"orderdate\": \"12/12/2001\", \"orderItems\": [   {   \"product\": \"Fortune Cookies\",   \"price\": 19.99   } ] } }"
    r.set("test1", s)
    # make sure data added
    e = r.get("test1")
    assert (e) is not None
    jsone = json.loads(e,object_hook=decode.decode_dict)
    assert(jsone["_id"] == "4bd8ae97c47016442af4a580")
    assert(((jsone["order"].get("orderItems"))[0]).get("price") == 19.99)
    assert("fullprice" not in jsone)

    # perform the update and grab the updated value 
    do_upd.do_upd(r)
    e = r.get("test1")
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

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"


def main():
    test1()
            

if __name__ == '__main__':
    main()
