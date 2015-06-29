
#
#  Flags and stuffs.
#
CFLAGS=-ggdb -g -fPIC -Wall -Werror ../../fuse-2.9.3/lib/.libs/libfuse.so -D_FILE_OFFSET_BITS=64 -I. -DVERSION=$(VERSION)
LDFLAGS=-pthread -lrt -ldl -lz -lkitsune -shared -u kitsune_is_updating 
LDFUSE_FLAGS=../../fuse-2.9.3/lib/.libs/libfuse.so -u fuse_get_context -zdefs -ldl -lrt


#final:
#	cc  redisfs.o pathutil.o hiredis.o sds.o net.o   -o redisfs -L../../fuse-2.9.3/lib/.libs/ -lfuse -pthread -lrt -ldl -lz -lkitsune


#
#  By default make our filesystem.
#
all: link redisfs redisfs-snapshot 


#
#  Clean.
#
clean:
	rm redisfs redisfs-snapshot *.o || true
	rm -f fmacros.h || true
	rm -f hiredis.c || true
	rm -f hiredis.h || true
	rm -f sds.c || true
	rm -f sds.h  || true
	rm -f net.c || true
	rm -f net.h  || true
	rm -f util.h  || true

#
#  Install the binary
#
install:
	mkdir -p $(prefix)/sbin
	cp ./redisfs $(prefix)/sbin/

#
#  Indent & tidy.
#
tidy:
	indent --no-space-after-function-call-names --no-space-after-casts --braces-after-if-line --no-tabs --indent-level 4 -bli0 -cdb -sc redisfs.c
	indent --no-space-after-function-call-names --no-space-after-casts --braces-after-if-line --no-tabs --indent-level 4 -bli0 -cdb -sc redisfs-snapshot.c


#
#  The filesystem
#
redisfs: pathutil.o redisfs.o hiredis.o sds.o net.o
	$(CC) $(LDFLAGS) $^  -o redisfs.so $(LDFUSE_FLAGS)



#
#  The filesystem snapshot utility
#
redisfs-snapshot: pathutil.o redisfs-snapshot.o hiredis.o sds.o net.o


#
#  Link our C-client library into place
#
link:
	ln -sf ../hiredis/fmacros.h .
	ln -sf ../hiredis/hiredis.c .
	ln -sf ../hiredis/hiredis.h .
	ln -sf ../hiredis/sds.c .
	ln -sf ../hiredis/sds.h .
	ln -sf ../hiredis/net.c .
	ln -sf ../hiredis/net.h .
	ln -sf ../hiredis/util.h .



#@echo "TODO READ THIS *********************************************"
#@echo "TODOFIXME, Makefile bug (not mine, from redisfs repo):\nchange flag order to to fix the\nundefined reference to \`fuse_get_context' bug that you're about to see.\n\n'cc  redisfs.o pathutil.o hiredis.o sds.o net.o   -o redisfs ../../fuse-2.9.3/lib/.libs/libfuse.a -pthread -lrt -ldl -lz -lkitsune'  \n\nFor now just 'cd src', copy/paste/execute the line above after the error, and it will work.\n"
#@echo "*********************************************"

