
all:
	gcc -shared -fPIC -g test_user_call.c -o user_call.so -ldl -I../../../redis-2.8.17/src/
	gcc -g run_tests.c -o run_tests -lhiredis 
clean:
	rm -f *so
	rm -f run_tests
