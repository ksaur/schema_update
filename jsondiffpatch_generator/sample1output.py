import sys
import json
import decode


def update_menu(jsonobj):
    e = jsonobj.get('menu')
    print "\n1:"
    print e
    assert(e is not None)
    del e['deleteme']
    e['delta'] = 9
    print "\n2:"
    print e
    e = jsonobj.get('menu').get('popup').get('menuitem')
    print "\n3:"
    print e
    assert(e is not None)
    for f in e:
        assert(f is not None)
        f['active'] = False

def update_soup(jsonobj):
    e = jsonobj.get('soup')
    assert(e is not None)
    del e['delme']
    e['addmes'] = 0


def main():

    file1 = open(sys.argv[1], 'r')
    str1 = file1.read()
    json1 = json.loads(str1, object_hook=decode.decode_dict)
    for k in json1.keys():
       print k + "before:"
       # Create the function name and call it.
       funcname = "update_"+k
       # http://stackoverflow.com/questions/3061/calling-a-function-of-a-module-from-a-string-with-the-functions-name-in-python
       globals()[funcname](json1)
    print json1

if __name__ == '__main__':
    main()
