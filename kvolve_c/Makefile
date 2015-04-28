
all: kvolve.a
	gcc -g -o proxy  proxy.c kvolve.a -lpthread 

kvolve.a: kvolve.o
	ar rcs kvolve.a kvolve.o

kvolve.o: 
	gcc -c kvolve.c

clean:
	rm -f *.o proxy kvolve.a


