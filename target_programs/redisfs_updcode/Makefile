
all:
	gcc -shared -fPIC -g redisfs_v5v6_upd.c -o redisfs_v5v6.so -ldl -I../../redis-2.8.17/src/
	gcc -g run_upd.c -o run_upd -lhiredis 
clean:
	rm -f *so
	rm -f run_upd
