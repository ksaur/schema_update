import json
import sys, os
import redis
from lazyupdredis import *
sys.path.append("data/example_jsonbulk/")
import sample_generate



def test_1_sadalage_upd():
    tname = "test1_bulk"
    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  STARTING  " + tname + "  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"

    # TODO, load the data in from file? would be faster than regenerating...
    sample_generate.gen_1_sadalage(1000)

    # Connect at the correct version and namespace
    r = lazyupdredis.connect([("customer", "v0")])
    print "Updating....."

    # Update all the keys now.
    print "UPDATED: " + str(r.do_upd_all_now("data/example_jsonbulk/gen_1_sadalage_init"))

    print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>  SUCCESS  ("+tname+")  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"


def main():
    test_1_sadalage_upd()


if __name__ == '__main__':
    main()
