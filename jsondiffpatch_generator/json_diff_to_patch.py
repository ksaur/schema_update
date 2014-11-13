# -*- encoding: utf-8 -*- 
# json_delta.py: a library for computing deltas between
# JSON-serializable structures.
#
# Copyright 2012‒2014 Philip J. Roberts <himself@phil-roberts.name>.
# BSD License applies; see the LICENSE file, or
# http://opensource.org/licenses/BSD-2-Clause
#
# ###################################################
#
# Modified/Repurposed 2014 by KSaur (ksaur@umd.edu)
#
'''
Requires Python 2.7 or newer (including Python 3).
'''
import bisect, copy, sys, re
import json


__VERSION__ = '0.1'

try:
    _basestring = basestring
except NameError:
    _basestring = str

try:
    extra_terminals = (unicode, long)
except NameError:
    extra_terminals = ()

TERMINALS = (str, int, float, bool, type(None)) + extra_terminals
NONTERMINALS = (list, dict)
SERIALIZABLE_TYPES = ((str, int, float, bool, type(None), 
                       list, tuple, dict) + extra_terminals)

# ----------------------------------------------------------------------
# Main entry points

def diff(left_struc, right_struc, verbose=True, key=None):
    '''Compose a sequence of diff stanzas sufficient to convert the
    structure ``left_struc`` into the structure ``right_struc``.  (The
    goal is to add 'necessary and' to 'sufficient' above!).

    Flags: 
        ``verbose``: if this is set ``True`` (the default), a line of
        compression statistics will be printed to stderr.

    The parameter ``key`` is present because this function is mutually
    recursive with :py:func:`needle_diff` and :py:func:`keyset_diff`.
    If set to a list, it will be prefixed to every keypath in the
    output.
    '''
    print ("in diff with key")
    print (key)
    if key is None:
        key = []
    common = commonality(left_struc, right_struc)
    # We only need to worry about the first element in the array.
    # We are assuming for now that all elements have the same type,
    # and that they will be patched symmetrically.
    if ((type(left_struc) is list) and (type(right_struc) is list) and
        (len(left_struc) >1) and (len(right_struc) >1) ):
        print("Truncating Array....")
        left_struc=left_struc[0]
        right_struc=right_struc[0]
    if common < 0.5:
        print ("a") 
        print type(left_struc)
        # We don't care about values changing, just keys.
        # This will ignore the values and just continue processing if
        # the type has changed, or if it's a container (list/dict)
        if((type(left_struc) is not type(right_struc)) or
            (type(left_struc) is list) or (type(left_struc) is dict)):
            my_diff = this_level_diff(left_struc, right_struc, key, common)
        else:
            my_diff = []
        print ("GOT THIS:")
        print my_diff
    else:
        print ("c")
        my_diff = keyset_diff(left_struc, right_struc, key)

    if key == []:
        if len(my_diff) > 1:
            my_diff = sort_stanzas(my_diff)
        if verbose:
            size = len(compact_json_dumps(right_struc))
            csize = float(len(compact_json_dumps(my_diff)))
            msg = ('Size of delta %.3f%% size of original '
                   '(original: %d chars, delta: %d chars)')
            print(msg % (((csize / size) * 100), 
                         size,
                         int(csize)), 
                  0)
    return my_diff

def patch(struc, diff, in_place=True):
    '''Apply the sequence of diff stanzas ``diff`` to the structure
    ``struc``.

    By default, this function modifies ``struc`` in place; set
    ``in_place`` to ``False`` to return a patched copy of struc
    instead.
    '''
    if not in_place:
        struc = copy.deepcopy(struc)
    for stanza in diff:
        struc = patch_stanza(struc, stanza)
    return struc


# ----------------------------------------------------------------------
# Utility functions

def in_one_level(diff, key):
    '''Return the subset of ``diff`` whose key-paths begin with
    ``key``, expressed relative to the structure at ``[key]``
    (i.e. with the first element of each key-path stripped off).

    >>> diff = [ [['bar'], None],
    ...          [['baz', 3], 'cheese'],
    ...          [['baz', 4, 'quux'], 'foo'] ]
    >>> in_one_level(diff, 'baz')
    [[[3], 'cheese'], [[4, 'quux'], 'foo']]

    '''
    oper_stanzas = [stanza[:] for stanza in diff if stanza[0][0] == key]
    for stanza in oper_stanzas:
        stanza[0] = stanza[0][1:]
    return oper_stanzas

def compact_json_dumps(obj):
    '''Compute the most compact possible JSON representation of the
    serializable object ``obj``.

    >>> test = {
    ...             'foo': 'bar',
    ...             'baz': 
    ...                ['quux', 'spam', 
    ...       'eggs']
    ... }
    >>> compact_json_dumps(test)
    '{"foo":"bar","baz":["quux","spam","eggs"]}'
    >>>
    '''
    return json.dumps(obj, indent=None, separators=(',', ':'))


def check_diff_structure(diff):
    '''Return ``diff`` (or ``True``) if it is structured as a sequence
    of ``diff`` stanzas.  Otherwise return ``False``.

    ``[]`` is a valid diff, so if it is passed to this function, the
    return value is ``True``, so that the return value is always True
    in a Boolean context if ``diff`` is valid.

    >>> check_diff_structure([])
    True
    >>> check_diff_structure([None])
    False
    >>> check_diff_structure([[["foo", 6, 12815316313, "bar"], None]])
    [[['foo', 6, 12815316313, 'bar'], None]]
    >>> check_diff_structure([[["foo", 6, 12815316313, "bar"], None],
    ...                       [["foo", False], True]])
    False
    '''
    if diff == []:
        return True
    if not isinstance(diff, list):
        return False
    for stanza in diff:
        if not isinstance(stanza, list):
            return False
        if len(stanza) not in (1, 2):
            return False
        keypath = stanza[0]
        if not isinstance(keypath, list):
            return False
        for key in keypath:
            if not (type(key) is int or isinstance(key, _basestring)): 
                    # So, it turns out isinstance(False, int)
                    # evaluates to True!
                return False
    return diff

# ----------------------------------------------------------------------
# Functions for computing normal diffs.

def compute_keysets(left_seq, right_seq):
    '''Compare the keys of ``left_seq`` vs. ``right_seq``.

    Determines which keys ``left_seq`` and ``right_seq`` have in
    common, and which are unique to each of the structures.  Arguments
    should be instances of the same basic type, which must be a
    non-terminal: i.e. list or dict.  If they are lists, the keys
    compared will be integer indices.

    Returns:
        Return value is a 3-tuple of sets ``({overlap}, {left_only},
        {right_only})``.  As their names suggest, ``overlap`` is a set
        of keys ``left_seq`` have in common, ``left_only`` represents
        keys only found in ``left_seq``, and ``right_only`` holds keys
        only found in ``right_seq``.

    Raises:
        AssertionError if ``left_seq`` is not an instance of
        ``type(right_seq)``, or if they are not of a non-terminal
        type.

    >>> compute_keysets({'foo': None}, {'bar': None})
    (set([]), set(['foo']), set(['bar']))
    >>> compute_keysets({'foo': None, 'baz': None}, {'bar': None, 'baz': None})
    (set(['baz']), set(['foo']), set(['bar']))
    >>> compute_keysets(['foo', 'baz'], ['bar', 'baz'])
    (set([0, 1]), set([]), set([]))
    >>> compute_keysets(['foo'], ['bar', 'baz'])
    (set([0]), set([]), set([1]))
    >>> compute_keysets([], ['bar', 'baz'])
    (set([]), set([]), set([0, 1]))
    '''
    assert isinstance(left_seq, type(right_seq))
    assert type(left_seq) in NONTERMINALS

    if type(left_seq) is dict:
        left_keyset = set(left_seq.keys())
        right_keyset = set(right_seq.keys())
    else:
        left_keyset = set(range(len(left_seq)))
        right_keyset = set(range(len(right_seq)))

    overlap = left_keyset.intersection(right_keyset)
    left_only = left_keyset - right_keyset
    right_only = right_keyset - left_keyset

    return (overlap, left_only, right_only)

def keyset_diff(left_struc, right_struc, key):
    '''Return a diff between ``left_struc`` and ``right_struc``.  

    It is assumed that ``left_struc`` and ``right_struc`` are both
    non-terminal types (serializable as arrays or objects).  Sequences
    are treated just like mappings by this function, so the diffs will
    be correct but not necessarily minimal.  

    This function probably shouldn't be called directly.  Instead, use
    :func:`udiff`, which will call :func:`keyset_diff` if appropriate
    anyway.
    '''
    out = []
    (o, l, r) = compute_keysets(left_struc, right_struc)
    out.extend([[key + [k]] for k in l])
    out.extend([[key + [k], right_struc[k]] for k in r])
    for k in o:
        print ("Processing: " + k)
        sub_key = key + [k]
        out.extend(diff(left_struc[k], right_struc[k],
                        False, sub_key))
    return out

def this_level_diff(left_struc, right_struc, key=None, common=None):
    '''Return a sequence of diff stanzas between the structures
    left_struc and right_struc, assuming that they are each at the
    key-path ``key`` within the overall structure.'''

    print("LEFT AND RIGHT:")
    print(left_struc)
    print(right_struc)
    out = []

    if key is None:
        key = []

    if common is None:
        common = commonality(left_struc, right_struc)

    if common:
        (o, l, r) = compute_keysets(left_struc, right_struc)
        for okey in o:
            if left_struc[okey] != right_struc[okey]:
                out.append([key[:] + [okey], right_struc[okey]])
        for okey in l:
            out.append([key[:] + [okey]])
        for okey in r:
            out.append([key[:] + [okey], right_struc[okey]])
        return out
    elif left_struc != right_struc:
        return [[key[:], right_struc]]
    else:
        return []

def commonality(left_struc, right_struc):
    '''Return a float between 0.0 and 1.0 representing the amount
    that the structures left_struc and right_struc have in common.  

    If left_struc and right_struc are of the same type, this is
    computed as the fraction (elements in common) / (total elements).
    Otherwise, commonality is 0.0.
    '''
    if type(left_struc) is not type(right_struc):
        return 0.0
    if type(left_struc) in TERMINALS:
        return 0.0
    if type(left_struc) is dict:
        (o, l, r) = compute_keysets(left_struc, right_struc)
        com = float(len(o))
        tot = len(o.union(l, r))
    else:
        assert type(left_struc) in (list, tuple), left_struc
        com = 0.0
        for elem in left_struc:
            if elem in right_struc: com += 1
        tot = max(len(left_struc), len(right_struc))

    if not tot: return 0.0
    return com / tot

def split_deletions(diff):
    '''Return a tuple of length 3, of which the first element is a
    list of stanzas from ``diff`` that modify objects (dicts when
    deserialized), the second is a list of stanzas that add or change
    elements in sequences, and the second is a list of stanzas which
    delete elements from sequences.'''
    objs = [x for x in diff if isinstance(x[0][-1], _basestring)]
    seqs = [x for x in diff if isinstance(x[0][-1], int)]
    assert len(objs) + len(seqs) == len(diff), diff
    seqs.sort(key=len)
    lengths = [len(x) for x in seqs]
    point = bisect.bisect_left(lengths, 2)
    return (objs, seqs[point:], seqs[:point])

def sort_stanzas(diff):
    '''Sort the stanzas in ``diff``: node changes can occur in any
    order, but deletions from sequences have to happen last node
    first: ['foo', 'bar', 'baz'] -> ['foo', 'bar'] -> ['foo'] ->
    [] and additions to sequences have to happen
    leftmost-node-first: [] -> ['foo'] -> ['foo', 'bar'] ->
    ['foo', 'bar', 'baz'].
    
    Note that this will also sort changes to objects (dicts) so that
    they occur first of all, then modifications/additions on
    sequences, followed by deletions from sequences.
    '''
    # First we divide the stanzas using split_deletions():
    (objs, mods, dels) = split_deletions(diff)
    # Then we sort modifications of lists in ascending order of last key:
    mods.sort(key=lambda x: x[0][-1])
    # And deletions from lists in descending order of last key:
    dels.sort(key=lambda x: x[0][-1], reverse=True)
    # And recombine:
    return objs + mods + dels

# ----------------------------------------------------------------------
# Functions for applying normal patches

def patch_stanza(struc, diff):
    '''Applies the diff stanza ``diff`` to the structure ``struc`` as
    a patch.

    Note that this function modifies ``struc`` in-place into the
    target of ``diff``.'''
    changeback = False
    if type(struc) is tuple:
        changeback = True
        struc = list(struc)[:]
    key = diff[0]
    if not key:
        print ("0")
        print (diff[1])
        struc = diff[1]
        changeback = False
    elif len(key) == 1:
        if len(diff) == 1:
            print ("1")
            del struc[key[0]]
        elif (type(struc) in (list, tuple)) and key[0] == len(struc):
            print ("2")
            struc.append(diff[1])
        else:
            print ("3")
            struc[key[0]] = diff[1]
    else:
        print ("4")
        pass_key = key[:]
        pass_struc_key = pass_key.pop(0)
        pass_struc = struc[pass_struc_key]
        pass_diff = [pass_key] + diff[1:]
        struc[pass_struc_key] = patch_stanza(pass_struc, pass_diff)
    if changeback:
        struc = tuple(struc)
    return struc

# ----------------------------------------------------------------------

# Basic script functionality

dbg1 = {
    "menu": {
        "id": 1,
        "live": True,
        "deleteme": True,
        "pointer": None,
        "value": "File",
        "popup": {
            "menuitem": [
                {
                    "value": "New",
                    "onclick": "CreateNewDoc()"
                },
                {
                    "value": "Open",
                    "onclick": "OpenDoc()"
                },
                {
                    "value": "Close",
                    "onclick": "CloseDoc()"
                }
            ]
        }
    }
}
dbg2 = {
    "menu": {
        "id": 1,
        "delta": 9,
        "live": False,
        "pointer": None,
        "value": "File",
        "popup": {
            "menuitem": [
                {
                    "value": "New",
                    "onclick": "CreateNewDoc()"
                },
                {
                    "value": "Open",
                    "onclick": "OpenDoc()"
                },
                {
                    "value": "Close",
                    "onclick": "CloseDoc()"
                }
            ]
        }
    }
}

# These 2 de-unicoding hook functions from:
# http://stackoverflow.com/questions/956867/
#   how-to-get-string-objects-instead-of-unicode-ones-from-json-in-python
#   Mike Brennan
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


def main():
    assert len(sys.argv) is 3

    #print ("\nDiff'ing files:" + sys.argv[1] +  " and " +sys.argv[2])
    file1 = open(sys.argv[1], 'r')
    file2 = open(sys.argv[2], 'r')
    str1 = file1.read()
    str2 = file2.read()
    print (type(str1))
    json1 = json.loads(str1, object_hook=_decode_dict)
    json2 = json.loads(str2, object_hook=_decode_dict)

    ###print ("\n\nTHE DELTA IS:")
    thediffto = diff(json1, json2)
    thedifffrom = diff(json2, json1)
    print (thediffto)
    print (thedifffrom)


    #print (compute_keysets(json1, json2))
    #print (compute_keysets(json2, json1))
   
    #thepatch = patch(dbg1, thediff)
    #thepatch = patch(json1, thediff)
    #print thepatch


if __name__ == '__main__':
     main()
