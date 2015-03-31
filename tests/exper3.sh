#!/bin/bash
# since python seems to be doing weird when not restarted from scratch
for i in {1..11}
do
     #pypy experiment3.py do_get_or_set
     #pypy experiment3.py do_get
     pypy experiment3.py do_set
done
