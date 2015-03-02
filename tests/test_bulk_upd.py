import json
import sys, os
import redis
from lazyupdredis import *
sys.path.append("data/example_jsonbulk/")
import sample_generate



def test_1_sadalage_upd():
    tname = "test1_bulk"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

    # non-hooked redis commands to work as orginally specified
    actualredis = redis.StrictRedis()

    # TODO, load the data in from file? would be faster than regenerating...
    num_kv = 1000
    sample_generate.gen_1_sadalage(num_kv)

    # Connect at the correct version and namespace
    r = lazyupdredis.connect([("customer", "v0")])
    print "Updating....."

    # Update all the keys now.
    print "UPDATED: " + str(r.do_upd_all_now("data/example_jsonbulk/sample_1_sadalage_init"))

    # Assert that stuff updated
    
    assert(len(actualredis.keys("v0*")) == 0) #keys not updated
    assert(len(actualredis.keys("v1*")) == num_kv) # keys updated.


    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"


def main():
    test_1_sadalage_upd()


if __name__ == '__main__':
    main()
