import sys
import redis, json
import argparse
import random, string
import datetime
from datetime import timedelta
from random import randint


def random_date(start, end):
    return start + timedelta(
        seconds=randint(0, int((end - start).total_seconds())))


def gen_1_sadalage(r, num_entries):

    for i in range(num_entries):
        s = dict()
        s["_id"]= random.randint(100000000,sys.maxint)
        s["customerid"]= i
        s["name"] = ''.join(random.choice(string.ascii_uppercase) for j in range(16)) 
        since = random_date(datetime.date(2000,3,12), datetime.date(2008,1,1))
        s["since"] = str(since)
        o = dict()
        o["orderid"] = random.randint(1000,10000000) 
        o["orderdate"] = str(random_date(since, datetime.date(2015,1,1)))
        l = list()
        for it in range(random.randint(1,4)):
            price = "{:.2f}".format(random.randint(2000,5000)/100.00)
            prod = ''.join(random.choice(string.ascii_uppercase) for j in range(9))
            items = {"product" : prod, "price": price}
            l.append(items)
        o["orderItems"] = l
        s["order"] = o
        r.set("customer:"+str(i), json.dumps(s))

    r.save()


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--e', nargs=1, help='number of entries ')
    args = parser.parse_args()

    if (args.e) is not None:
        num_entries = int(args.e[0])
    else:
        print "using default number of entries (1000)" 
        num_entries = 1000

    r = redis.StrictRedis()
    try:
        r.ping()
    except r.ConnectionError as e:
        print(e)
        sys.exit(-1)
    r.flushall()

    gen_1_sadalage(r, num_entries)


    


if __name__ == '__main__':
    main()
