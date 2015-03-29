#!/bin/bash
# since python seems to be doing weird when not restarted from scratch
for i in {1..11}
do
     pypy experiment2.py
done
