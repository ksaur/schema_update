import sys
import json
import decode


def update_menu(jsonobj):
    e = jsonobj.get('menu').get('popup').get('menuitem')
    assert(e is not None)
    for f in e:
        g = f.get('test')
        assert(g is not None)
        g['adds'] = None


def update_soup(jsonobj):
    ()


def main():

    file1 = open(sys.argv[1], 'r')
    str1 = file1.read()
    json1 = json.loads(str1, object_hook=decode.decode_dict)
    for k in json1.keys():
        # Create the function name and call it.
        funcname = "update_"+k
        # http://stackoverflow.com/questions/3061/calling-a-function-of-a-module-from-a-string-with-the-functions-name-in-python
        globals()[funcname](json1)
    print json1

if __name__ == '__main__':
    main()
