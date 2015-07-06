#!/bin/bash
~/kitsune-core/bin/bin/ktcc --doglobalreg --dostackvars  --keepunused -ggdb3 -Wall -lz -ldl -fPIC -I~/kitsune-core/bin/bin/ -c redisfs.c -D_FILE_OFFSET_BITS=64 -zdefs -ldl -lrt -lfuse  -lz -I. -DVERSION=0.6 
~/kitsune-core/bin/bin/xfgen dsu.c redisfs.ktt redisfs.ktt none.xf
cc -pthread -lrt  -lz -lkitsune -g -shared -u kitsune_is_updating  pathutil.o redisfs.o hiredis.o sds.o net.o dsu.c -o redisfs.so -lfuse -u fuse_get_context -zdefs  -lrt -fPIC   -ldl -lz
cp redisfs.so redisfsv0v0.so 
