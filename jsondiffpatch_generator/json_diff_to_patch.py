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

initdict = dict()

def diff(left_struc, right_struc, key=None):
    '''Compose a sequence of diff stanzas sufficient to convert the
    structure ``left_struc`` into the structure ``right_struc``.  (The
    goal is to add 'necessary and' to 'sufficient' above!).

    The parameter ``key`` is present because this function is mutually
    recursive with :py:func:`keyset_diff`.
    If set to a list, it will be prefixed to every keypath in the
    output.
    '''
    if key is None:
        key = []
    common = commonality(left_struc, right_struc)
    # We only need to worry about the first element in the array.
    # We are assuming for now that all elements have the same type,
    # and that they will be patched symmetrically.
    if ((type(left_struc) is list) and (type(right_struc) is list) and
        (len(left_struc) >0) and (len(right_struc) >0) ):
        d = [key[len(key)-1]]
        print d
        key[len(key)-1] = d

        print("Truncating Array....")
        left_struc=left_struc[0]
        right_struc=right_struc[0]
    if common is True:
        # We don't care about values changing, just keys.
        # This will ignore the values and just continue processing if
        # the type has changed, or if it's a container (list/dict)
        if((type(left_struc) is not type(right_struc)) or
            (type(left_struc) is list) or (type(left_struc) is dict)):
            my_diff = this_level_diff(left_struc, right_struc, key, common)
        else:
            my_diff = []
    else:
        my_diff = keyset_diff(left_struc, right_struc, key)

    if key == []:
        if len(my_diff) > 1:
            my_diff = sort_stanzas(my_diff)
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

    #print ("======= overlap / left / right ==========")
    #print (overlap)
    #print (left_only)
    #print (right_only)
    #print ("=========================================")
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
    out.extend([[key + [k], "INIT"] for k in r])
    # TODO, pull INIT from db
    #out.extend([[key + [k], right_struc[k]] for k in r])
    for k in o:
        sub_key = key + [k]
        out.extend(diff(left_struc[k], right_struc[k],
                        sub_key))
    return out

def this_level_diff(left_struc, right_struc, key=None, common=None):
    '''Return a sequence of diff stanzas between the structures
    left_struc and right_struc, assuming that they are each at the
    key-path ``key`` within the overall structure.'''
    out = []
    # Always compute the keysets, return the diff.
    (o, l, r) = compute_keysets(left_struc, right_struc)
    for okey in o:
        if left_struc[okey] != right_struc[okey]:
            out.append([key[:] + [okey], right_struc[okey]])
    for okey in l:
        out.append("DEL"+[key[:] + [okey]])
    for okey in r:
        out.append("ADD"+[key[:] + [okey], right_struc[okey]])
    return out

def commonality(left_struc, right_struc):
    '''Return True if structs are the same type or terminals. Else False.
    '''
    if type(left_struc) is not type(right_struc):
        return True
    if type(left_struc) in TERMINALS:
        return True
    else:
        return False

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
        struc = diff[1]
        changeback = False
    elif len(key) == 1:
        if len(diff) == 1:
            # From array truncation
            if type(struc) is list:
                for e in struc:
                    # check for init here in arrays
                    del e[key[0]]
            else: 
                del struc[key[0]]
        elif (type(struc) in (list, tuple)) and key[0] == len(struc):
            struc.append(diff[1])
        else:
            # From array truncation
            if type(struc) is list:
                for e in struc:
                    # check for init here in arrays
                    e[key[0]] = diff[1]
            else:
                # check for init here in non-arrays
                struc[key[0]] = diff[1]
    else:
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

def generate_upd(thediff):
    print len(thediff)
    function = ""
    getter = ""
    for l in thediff:
        # l[0] is the key to where to modify the data
        # l[1] is 'INIT' if adding, otherwise there is no l[1]
        assert(len(l) in (1,2))
        keys = l[0]
        assert(len(keys)>0)
        if (keys[0] != function):
           print "\ndef update_" + keys[0] + "(jsonobj):"
           function = keys[0]
        # get the item to modify
        pos = 'e'  # for code generation. 
                   # This is the first variable name and we'll increment it
        tabstop = "    "
        codeline = tabstop + pos + " = jsonobj"
        for s in keys[0:(len(keys)-1)]: 
            if (type(s) is str):
                codeline += ".get(\'" + s + "\')"
            else: # arrays
                # if array isn't the leaf 
                nextpos = chr(ord(pos) + 1) # increment the variable name
                codeline += ".get(\'" + s[0] + "\')\n"
                codeline += tabstop + "assert(" + pos + " is not None)\n"
                codeline += tabstop + "for " + nextpos +" in " + pos + ":"
                tabstop = tabstop + "    "
                pos = nextpos
                if (s != keys[(len(keys)-2)]):
                   nextpos = chr(ord(pos) + 1)
                   codeline += "\n" + tabstop + nextpos + " = " + pos
                   pos = nextpos
                # TODO There are probably several scenarios this leaves out?
        if (getter != codeline):
            print codeline
            print tabstop + "assert(" + pos + " is not None)"
            getter = codeline

        # adding
        if (len(l) == 2):
           print tabstop + pos+"[\'" + keys[len(keys)-1] + "\'] = 'INIT..'"
        # deleting. 
        else:
           print tabstop + "del "+pos+"[\'" + (keys[len(keys)-1]) + "\']"
        

def regextime(dslf):
    # Load up the init file
    dslfile = open(dslf, 'r')
    for line in dslfile:
        print line,
        initdict 

    patterns =  ['(INIT\\s+)(\[.*\])\\s?=\\s?([a-zA-Z0-9]+)\\s?,\\s?if\\s?\'([a-zA-Z0-9]+)\'\\s?=\\s?\'(.*)\'',    #INIT [...] = val, if someclause
                 '(INIT\\s+)(\[.*\])\\s?=\\s?([a-zA-Z0-9]+)']     #INIT [...] = val

    def extract_from_re(estr):
        for p in patterns:
            if re.match(p,estr) is not None:
                cmd_re = re.compile(p)
                cmd = cmd_re.search(estr)
                print type(cmd_re) 
                print type(cmd) 
                print cmd_re.groups
                for i in range(1,cmd_re.groups+1): 
                    print "Group " +str(i) + " = " +  cmd.group(i)
                return cmd
            else:
                print "FAIL"

    for line in dslfile:
        print "=========================================\n\nline = " + line
        curr = extract_from_re(line)
        print "found " + str(len(curr.groups())) + " groups"
        print curr.group(1)

def main():
    assert (len(sys.argv) in (3, 4)), '\n\nUsage is: \"python json_diff_to_patch.py \
    <json1> <json2> (optional <initfile>)\".\n Ex: \"python json_diff_to_patch.py \
    ../example_json/sample1.json ../example_json/sample2.json\"'

    file1 = open(sys.argv[1], 'r')
    file2 = open(sys.argv[2], 'r')
    str1 = file1.read()
    str2 = file2.read()
    json1 = json.loads(str1, object_hook=_decode_dict)
    json2 = json.loads(str2, object_hook=_decode_dict)

    dslfile = None 
    if len(sys.argv) is 4:
        dslfile = regextime(sys.argv[3])

    print ("\nTHE KEYS ARE: (len " + str(len(json1.keys())) + ")") 
    print json1.keys() 

    thediff = diff(json1, json2)
    print ("\nTHE DIFF IS: (len " + str(len(thediff)) + ")")
    print (thediff)
    
    generate_upd(thediff)

    #print ("\nPATCHED FILE1 IS:")
    #print patch(json1, thediff)


if __name__ == '__main__':
    main()
