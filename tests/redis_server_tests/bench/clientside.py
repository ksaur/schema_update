####  To be run on a remote host
import subprocess
from subprocess import Popen
from time import sleep
import time

num_ops = "5000000"
keyspace = "1000000"
host = "macdonald"
trial_len =170 

def main():
  for i in range(4):
    for j in range(11):
      start = time.time()
      sleep(5)
      bench = subprocess.Popen(["./redis-benchmark", "-h", host, "-t", "get", "-n", num_ops, "-r", keyspace])
      bench.wait()
      while (time.time()- start) < trial_len:
        sleep(1)


    for j in range(11):
      start = time.time()
      sleep(5)
      bench = subprocess.Popen(["./redis-benchmark", "-h", host, "-t", "set", "-n", num_ops, "-r", keyspace])
      bench.wait()
      while (time.time()- start) < trial_len:
        sleep(1)



if __name__ == '__main__':
    main()
