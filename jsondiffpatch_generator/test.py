import sys
import json

def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv

def _decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv

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
    json1 = json.loads(str1, object_hook=_decode_dict)
    for k in json1.keys():
       print k + "before:"
       # Create the function name and call it.
       funcname = "update_"+k
       # http://stackoverflow.com/questions/3061/calling-a-function-of-a-module-from-a-string-with-the-functions-name-in-python
       globals()[funcname](json1)
    print json1

if __name__ == '__main__':
    main()
