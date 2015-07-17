
all:
	gcc -shared -fPIC -g loadup_prevns.c -o prev_ns.so -ldl -I../../../redis-2.8.17/src/
	gcc -g redisfs_v0v6_nonlazy.c -o compress -lhiredis -lz
clean:
	rm -f *so
