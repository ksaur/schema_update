
all:
	gcc -shared -fPIC -g redisfs_v5v6_upd.c -o redisfs_v5v6.so -ldl -lz -I../../redis-2.8.17/src/ -lz
	gcc -shared -fPIC -g redisfs_v0v6_nonlazy.c -o redisfs_v0v6.so -ldl -lz -I../../redis-2.8.17/src/ -lz
clean:
	rm -f *so
	rm -f run_upd
