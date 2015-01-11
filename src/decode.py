"""
This file contains some helper functions.

These 2 de-unicoding hook functions from:
http://stackoverflow.com/questions/956867/how-to-get-string-objects-instead-of-unicode-ones-from-json-in-python
(stackoverflow post by Mike Brennan)
"""

def decode_list(data):
    """
    Remove unicode from lists.

    """
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = decode_list(item)
        elif isinstance(item, dict):
            item = decode_dict(item)
        rv.append(item)
    return rv

def decode_dict(data):
    """
    Remove unicode from dict.

    Example:

    >>> s = "{ \"name\": \"Foo Bar Industries\"}"
    >>> json.loads(s)  # without decode hook, you'll get unicode
    {u'name': u'Foo Bar Industries'}
    >>> json.loads(s, object_hook=decode.decode_dict) # remove unicode
    {'name': 'Foo Bar Industries'}

    """
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = decode_list(value)
        elif isinstance(value, dict):
            value = decode_dict(value)
        rv[key] = value
    return rv
