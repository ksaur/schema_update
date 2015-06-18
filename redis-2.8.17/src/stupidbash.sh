#!/bin/bash

for i in `seq 1 12`;
do
	rm dump.rdb
	./redis-server &
	#/home/ksaur/redis-2.8.17/src/redis-server &
	sleep 2
	./redis-benchmark  -t get -n 1000000 -r 100000000
	killall redis-server
	sleep 2
done
