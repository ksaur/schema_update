# -*- encoding: utf-8 -*-
# json_delta.py: a library for computing deltas between
# JSON-serializable structures.
#
# Copyright 2012‒2014 Philip J. Roberts <himself@phil-roberts.name>.
# BSD License applies; see the LICENSE file, or
# http://opensource.org/licenses/BSD-2-Clause
#
# ###################################################
'''
Requires Python 2.7 or newer (including Python 3).
'''
import bisect, copy, sys, re
import json
import decode
import argparse


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


# ----------------------------------------------------------------------
# Main entry points


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
        if (len(key) != 0):
            ## mark the last item in "[]" to signal that it is a list
            key[len(key)-1] = [key[len(key)-1]]

        #print("Truncating Array....")
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
        if type(left_struc) in NONTERMINALS:
            my_diff = keyset_diff(left_struc, right_struc, key)
        else:
            print "RETURNING"
            my_diff = [] # no objects here...

    if key == []:
        if len(my_diff) > 1:
            my_diff = sort_stanzas(my_diff)
    return my_diff


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
    # The INIT gets pulled later. This is a placeholder for the next step.
    out.extend([[key + [k], "INIT"] for k in r])
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

