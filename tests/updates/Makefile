
all:
	gcc -shared -fPIC -g test1.c -o test1.so -ldl -I../../redis-2.8.17/src/
	gcc -shared -fPIC -g test2.c -o test2.so -ldl -I../../redis-2.8.17/src/
	gcc -g run_test1_test2.c -o run_test1_test2 -lhiredis 
clean:
	rm *so
	rm run_test1_test2
