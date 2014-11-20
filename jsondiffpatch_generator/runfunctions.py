"""

Call all of the generated functions for the input file.

Usage: python runfunctions.py filetoupdate

TODO: redis integration.....
 
With help from:
http://stackoverflow.com/questions/3061/
calling-a-function-of-a-module-from-a-string-with-the-functions-name-in-python

"""
import sys
import json
import decode

def main():

    file1 = open(sys.argv[1], 'r')
    str1 = file1.read()
    json1 = json.loads(str1, object_hook=decode.decode_dict)
    m = __import__ ('dsu')
    for k in json1.keys():
        # Create the function name and call it.
        funcname = "update_"+k
        func = getattr(m,funcname)
        func(json1)
    print json1

if __name__ == '__main__':
    main()
