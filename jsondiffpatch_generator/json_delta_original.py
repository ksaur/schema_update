# -*- encoding: utf-8 -*- 
# json_delta.py: a library for computing deltas between
# JSON-serializable structures.
#
# Copyright 2012‒2014 Philip J. Roberts <himself@phil-roberts.name>.
# BSD License applies; see the LICENSE file, or
# http://opensource.org/licenses/BSD-2-Clause
'''
This is the main "library" for json_delta's functionality.  If it gets
any bigger, I'll probably split it out into at least four separate
modules.  As it is, the functionality divides into four main headings:
diff, patch, udiff and upatch, plus entry points for the above,
utility functions common to all four, and basic shell functionality as
documented below.

The library is kept as one module for ease of distribution: if you
want to use it from another program, this file is all you need.  The
full package includes three CLI scripts that offer more versatile
access to the functionality this module makes available.  The
json_diff and json_patch scripts have syntax and options that mimic
standard diff(1) and patch(1) where it is appropriate to do so.  Also,
there is json_cat, a script I wrote for testing purposes which may
prove useful.

Requires Python 2.7 or newer (including Python 3).
'''
from __future__ import print_function, unicode_literals

import bisect, copy, sys, re, itertools
import json
from json import decoder, scanner

try:
    import needle
except ImportError:
    needle = None

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

def diff(left_struc, right_struc, minimal=True, verbose=True, key=None):
    '''Compose a sequence of diff stanzas sufficient to convert the
    structure ``left_struc`` into the structure ``right_struc``.  (The
    goal is to add 'necessary and' to 'sufficient' above!).

    Flags: 
        ``verbose``: if this is set ``True`` (the default), a line of
        compression statistics will be printed to stderr.

        ``minimal``: if ``True``, the function will try harder to find
        the diff that encodes as the shortest possible JSON string, at
        the expense of a possible performance penalty (as alternatives
        are computed and compared).

    The parameter ``key`` is present because this function is mutually
    recursive with :py:func:`needle_diff` and :py:func:`keyset_diff`.
    If set to a list, it will be prefixed to every keypath in the
    output.
    '''
    if key is None:
        key = []
    if minimal: 
        dumbdiff = [[key[:], copy.copy(right_struc)]]
    common = commonality(left_struc, right_struc)
    if common < 0.5:
        my_diff = this_level_diff(left_struc, right_struc, key, common)
    elif minimal:
        if needle is not None:
            my_diff = needle_diff(left_struc, right_struc, key, minimal)
        else:
            my_diff = keyset_diff(left_struc, right_struc, key, minimal)
    else:
        my_diff = keyset_diff(left_struc, right_struc, key, minimal)

    if minimal:
        my_diff = min(dumbdiff, my_diff, 
                      key=lambda x: len(compact_json_dumps(x)))

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
                  file=sys.stderr)
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

def upatch(struc, udiff, reverse=False, in_place=True):
    '''Apply a patch of the form output by udiff() to the structure
    ``struc``.

    By default, this function modifies ``struc`` in place; set
    ``in_place`` to ``False`` to return a patched copy of ``struc``
    instead.
    '''
    if not in_place:
        struc = copy.deepcopy(struc)
    left_json, right_json = split_udiff_parts(udiff)
    if not (left_json or right_json):
        return struc
    dec = extended_json_decoder()
    left_part = dec.decode(left_json)
    right_part = dec.decode(right_json)
    if reverse:
        return fill_in_ellipses(struc, right_part, left_part)
    return fill_in_ellipses(struc, left_part, right_part)

def udiff(left, right, patch=None, indent=0, entry=True):
    '''Render the difference between the structures ``left`` and
    ``right`` as a string in a fashion inspired by :command:`diff -u`.

    Generating a udiff is strictly slower than generating a normal
    diff, since the udiff is computed on the basis of a normal diff
    between ``left`` and ``right``.  If such a diff has already been
    computed (e.g. by calling :py:func:`diff`), pass it as the
    ``patch`` parameter.
    '''
    if patch is None:
        patch = diff(left, right, verbose=False)
    elif entry:
        patch = copy.deepcopy(patch)

    if not patch and type(left) in TERMINALS:
        assert left == right, (left, right)
        if not entry:
            left_lines = [single_patch_band(indent, json.dumps(left))]
            right_lines = [single_patch_band(indent, json.dumps(left))]
        else:
            left_lines, right_lines = ([], [])
    elif patch and patch[0][0] == []:
        matter = json.dumps(left, indent=1).split('\n')
        left_lines = [patch_bands(indent, matter, '-')]
        if len(patch[0]) > 1:
            assert patch[0] == [[], right], (left, right, diff)
            matter = json.dumps(right, indent=1).split('\n')
            right_lines = [patch_bands(indent, matter, '+')]
    elif isinstance(left, dict):
        left_lines, right_lines = udiff_dict(left, right, patch, indent)
    elif isinstance(right, list):
        assert isinstance(right, list), (left, right)
        left_lines, right_lines = udiff_list(left, right, patch, indent)

    if entry:
        return generate_udiff_lines(left_lines, right_lines)
    else:
        return (left_lines, right_lines)

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

def all_paths(struc):
    '''Generate key-paths to every node in ``struc``.

    Both terminal and non-terminal nodes are visited, like so:

    >>> paths = [x for x in all_paths({'foo': None, 'bar': ['baz', 'quux']})]
    >>> [] in paths # ([] is the path to struc itself.)
    True
    >>> ['foo'] in paths
    True
    >>> ['bar'] in paths
    True
    >>> ['bar', 0] in paths
    True
    >>> ['bar', 1] in paths
    True
    >>> len(paths)
    5
    '''
    yield []
    if isinstance(struc, dict):
        keys = struc.keys()
    elif isinstance(struc, list):
        keys = range(len(struc))       
    else:
        return
    for key in keys:
        for subkey in all_paths(struc[key]):
            yield [key] + subkey    

def follow_path(struc, path):
    '''Return the value found at the key-path ``path`` within ``struc``.'''
    if not path:
        return struc
    else:
        return follow_path(struc[path[0]], path[1:])

def check_diff_structure(diff):
    '''Return ``diff`` (or ``True``) if it is structured as a sequence
    of ``diff`` stanzas.  Otherwise return ``False``.

    ``[]`` is a valid diff, so if it is passed to this function, the
    return value is ``True``, so that the return value is always true
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

def needle_penalty(left, right):
    '''Penalty function for Needleman-Wunsch alignment.'''
    if needle.Gap() in (left, right) or left != right:
        return 0.
    return 1.

def needle_diff(left_struc, right_struc, key, minimal=True):
    '''Returns a diff between ``left_struc`` and ``right_struc``.  

    If ``left_struc`` and ``right_struc`` are both serializable as
    arrays, this function will use Needleman-Wunsch sequence alignment
    to find a minimal diff between them.  Otherwise, returns the same
    result as :func:`keyset_diff`.

    This function probably shouldn't be called directly.  Instead, use
    :func:`udiff`, which will call :func:`keyset_diff` if appropriate
    anyway.
    '''
    if type(left_struc) not in (list, tuple):
        return keyset_diff(left_struc, right_struc, key, minimal)

    assert type(right_struc) in (list, tuple)

    a, aleft, aright = needle.needle(left_struc, right_struc, needle_penalty)
    alignments = needle.backtrack(left_struc, right_struc, a, needle_penalty)
    can_align = False

    for aleft, aright in alignments:
        if aleft[:len(left_struc)] == left_struc:
            can_align = True
            break

    if not can_align:
        return keyset_diff(left_struc, right_struc, key, minimal)

    out = []
    for k in range(len(aleft)):
        sub_key = key + [k]
        if isinstance(aleft[k], needle.Gap):
            out.append([sub_key, aright[k]])
        elif isinstance(aright[k], needle.Gap):
            out.append([sub_key])
        else:
            out.extend(diff(aleft[k], aright[k], key=sub_key, 
                            minimal=minimal, verbose=False))
    return out

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

def keyset_diff(left_struc, right_struc, key, minimal=True):
    '''Return a diff between ``left_struc`` and ``right_struc``.  

    It is assumed that ``left_struc`` and ``right_struc`` are both
    non-terminal types (serializable as arrays or objects).  Sequences
    are treated just like mappings by this function, so the diffs will
    be correct but not necessarily minimal.  For a minimal diff
    between two sequences, use :func:`needle_diff`.

    This function probably shouldn't be called directly.  Instead, use
    :func:`udiff`, which will call :func:`keyset_diff` if appropriate
    anyway.
    '''
    out = []
    (o, l, r) = compute_keysets(left_struc, right_struc)
    out.extend([[key + [k]] for k in l])
    out.extend([[key + [k], right_struc[k]] for k in r])
    for k in o:
        sub_key = key + [k]
        out.extend(diff(left_struc[k], right_struc[k],
                        minimal, False, sub_key))
    return out

def this_level_diff(left_struc, right_struc, key=None, common=None):
    '''Return a sequence of diff stanzas between the structures
    left_struc and right_struc, assuming that they are each at the
    key-path ``key`` within the overall structure.'''
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
        struc = diff[1]
        changeback = False
    elif len(key) == 1:
        if len(diff) == 1:
            del struc[key[0]]
        elif (type(struc) in (list, tuple)) and key[0] == len(struc):
            struc.append(diff[1])
        else:
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
# Functions for computing udiffs.

# The data structure representing a udiff that these functions all
# manipulate is a pair of lists of iterators ``(left_lines,
# right_lines)``.  These lists are expected (principally by
# generate_udiff_lines(), which processes them), to be of the same
# length.  A pair of iterators ``(left_lines[i], right_lines[i]`` may
# yield exactly the same sequence of output lines, each with ``' '``
# as the first character (representing parts of the structure the
# input and output have in common).  Alternatively, they may each
# yield zero or more lines (referring to parts of the structure that
# are unique to the inputs they represent).  In this case, all lines
# yielded by ``left_lines[i]`` should begin with ``'-'``, and all
# lines yielded by ``right_lines[i]`` should begin with ``'+'``.

def udiff_dict(left, right, diff, indent=0):
    '''Construct a pair of iterator sequences representing ``diff`` as
    a delta between dictionaries ``left`` and ``right``.

    This function probably shouldn't be called directly.  Instead, use
    :py:func:`udiff()` with the same arguments.  :py:func:`udiff()`
    and :py:func:`udiff_dict()` are mutually recursive, anyway.'''
    left_lines = []
    right_lines = []

    def add_common_matter(matter, ind=None):
        if ind is None: ind = indent
        return _add_common_matter(matter, left_lines, right_lines, ind)
    def add_differing_matter(left=None, right=None, ind=None):
        if ind is None: ind = indent
        return _add_differing_matter(left, right, left_lines, right_lines, ind)
    def commafy_last(left_comma=True, right_comma=None):
        return _commafy_last(left_lines, right_lines, left_comma, right_comma)

    def dump_verbatim(obj, side='left', comma=False):
        matter = json.dumps(obj, indent=1).split('\n')
        matter[0] = '"%s": %s' % (key, matter[0])
        gen = patch_bands(indent, matter, '-' if side == 'left' else '+')
        add_differing_matter(**{side: commafy(gen, comma)})

    keys_in_diff = set((stanza[0][0] for stanza in diff))
    if not (left or right):
        add_common_matter('{}')
        return (left_lines, right_lines)
    if not keys_in_diff:
        add_common_matter('{...}')
        return (left_lines, right_lines)

    add_common_matter('{')
    indent += 1

    common_keys = (set(left.keys()).union(set(right.keys()))
                   - keys_in_diff)
    if common_keys:
        key = next(iter(common_keys))
        value = next(udiff(left[key], right[key], [], 
                           indent+1, entry=False)[0][0])
        line_matter = '"%s": %s' % (key, value.lstrip())
        add_common_matter(line_matter)
    if len(common_keys) > 1:
        commafy_last()
        left_comma  = any(((key in left)  for key in keys_in_diff))
        right_comma = any(((key in right) for key in keys_in_diff))
        if left_comma and right_comma:
            add_common_matter('...,')
        elif left_comma:
            add_differing_matter(left='...,', right='...')
        elif right_comma:
            add_differing_matter(left='...', right='...,')
        else:
            add_common_matter('...')

    keys_in_diff = list(keys_in_diff)
    for i, key in enumerate(keys_in_diff):
        left_comma  = any(((key in left)  for key in keys_in_diff[i+1:]))
        right_comma = any(((key in right) for key in keys_in_diff[i+1:]))
        sub_diff = in_one_level(diff, key)
        if sub_diff == [[[]]]: # Handle deletions from left
            dump_verbatim(left[key], 'left', left_comma)
        elif key not in left: # Handle additions
            dump_verbatim(right[key], 'right', right_comma)
        else: # Handle modifications
            [left_side, right_side] = udiff(left[key], right[key], sub_diff, 
                                            indent+1, entry=False)
            add_common_matter('"%s":' % key)
            add_differing_matter(left_side, right_side)
            commafy_last(left_comma, right_comma)
        if i != (len(keys_in_diff) - 1): add_common_matter('')
                
    indent -= 1
    add_common_matter('}')
    return left_lines, right_lines

def udiff_list(left, right, diff, indent=0):
    '''Construct a pair of iterator sequences representing ``diff`` as
    a delta between the lists ``left`` and ``right``.

    This function probably shouldn't be called directly.  Instead, use
    :py:func:`udiff()` with the same arguments.  :py:func:`udiff()`
    and :py:func:`udiff_list()` are mutually recursive, anyway.'''
    keys_in_diff = sorted(set([stanza[0][0] for stanza in diff]))
    left_lines = []
    right_lines = []

    def add_common_matter(matter, ind=None):
        if ind is None: ind = indent
        return _add_common_matter(matter, left_lines, right_lines, ind)
    def add_differing_matter(left=None, right=None, ind=None):
        if ind is None: ind = indent
        return _add_differing_matter(left, right, left_lines, right_lines, ind)
    def commafy_last(left_comma=True, right_comma=None):
        return _commafy_last(left_lines, right_lines, left_comma, right_comma)

    def dump_verbatim(obj, side='left', comma=False):
        matter = json.dumps(obj, indent=1).split('\n')
        gen = patch_bands(indent+1, matter, '-' if side == 'left' else '+')
        add_differing_matter(**{side: commafy(gen, comma)})

    if not (left or right):
        add_common_matter('[]')
        return (left_lines, right_lines)
    if not keys_in_diff:
        assert left == right, (left, right)
        material = '[...(%d)]' % len(right)
        add_common_matter(material)
        return (left_lines, right_lines)

    add_common_matter('[')
    left_a, right_a = reconstruct_alignment(left, right, diff)

    def compute_commas(idx):
        out = []
        for seq in left_a, right_a:
            out.append(any(((not isinstance(elem, Gap)) 
                            for elem in seq[idx:])))
        return tuple(out)

    pos = 0
    keys = iter(keys_in_diff)
    while pos < len(left_a):
        key = next(keys, len(left_a) - 1)
        assert key >= pos, (key, pos)
        sub_diff = in_one_level(diff, key)
        pos_diff = key - pos

        if pos_diff >= 1:
            left_ext, right_ext = udiff(left_a[pos], right_a[pos], 
                                        in_one_level(diff, pos),
                                        indent+1, entry=False)
            add_differing_matter(left_ext, right_ext)
        if pos_diff > 2:
            commafy_last()
            matter = '...(%d)' % (pos_diff - 2)
            add_common_matter(matter, ind=indent+1)
        if pos_diff >= 2:
            commafy_last()
            left_ext, right_ext = udiff(left_a[key-1], right_a[key-1], [],
                                        indent+1, entry=False)
            add_differing_matter(left_ext, right_ext)

        left_comma, right_comma = compute_commas(key)

        if left_comma and right_comma and pos_diff >= 1:
            commafy_last()
        elif left_comma and pos_diff >= 1:
            add_differing_matter(left=',')
        elif right_comma and pos_diff >= 1:
            add_differing_matter(right=',')

        left_comma, right_comma = compute_commas(key+1)

        if isinstance(right_a[key], Gap):
            dump_verbatim(left_a[key], 'left', left_comma)
        elif isinstance(left_a[key], Gap):
            dump_verbatim(right_a[key], 'right', right_comma)
        else:
            left_ext, right_ext = udiff(left_a[key], right_a[key], sub_diff,
                                        indent+1, entry=False)
            for ext, comma in (left_ext, left_comma), (right_ext, right_comma):
                ext[-1] = commafy(ext[-1], comma)
            add_differing_matter(left_ext, right_ext)            
        pos = key + 1

    add_common_matter(']')
    return (left_lines, right_lines)

def patch_bands(indent, material, sigil=' '):
    '''Generate appropriately indented patch bands, with ``sigil`` as
    the first character.'''
    indent = ' ' * indent
    out = []
    for line in material:
        yield ('%(sigil)s%(indent)s%(line)s' % locals())        

def single_patch_band(indent, line, sigil=' '):
    '''Convenience function returning an iterable that generates a
    single patch band.'''
    return patch_bands(indent, (line,), sigil)

def commafy(gen, comma=True):
    '''Yields every result of ``gen``, with a comma concatenated onto
    the final result iff ``comma`` is ``True``.'''
    comma = ',' if comma == True else ''
    prev = next(gen)
    for line in gen:
        yield prev
        prev = line
    if not prev.endswith(','):
        yield '%s%s' % (prev, comma)
    else:
        yield prev

def add_matter(seq, matter, indent):
    '''Add material to ``seq``, treating it appropriately for its
    type.

    ``matter`` may be an iterator, in which case it is appended to
    ``seq``.  If it is a sequence, it is assumed to be a sequence of
    iterators, the sequence is concatenated onto ``seq``.  If
    ``matter`` is a string, it is turned into a patch band using
    :py:func:`single_patch_band`, which is appended.  Finally, if
    ``matter`` is None, an empty iterable is appended to ``seq``.

    This function is a udiff-forming primitive, called by more
    specific functions defined within :py:func:`udiff_dict` and
    :py:func:`udiff_list`.
    '''
    if isinstance(matter, _basestring):
        seq.append(single_patch_band(indent, matter))
    elif matter is None:
        seq.append(iter(()))
    elif isinstance(matter, list) or isinstance(matter, tuple):
        seq.extend(matter)
    else:
        seq.append(matter)

# The following functions represent functionality common to both
# udiff_dict() and udiff_list().  The forms without the leading _ are
# defined within the two functions, with the appropriate sequences for
# left_lines and right_lines curried in.

def _add_common_matter(matter, left_lines, right_lines, indent):
    for seq in left_lines, right_lines:
        add_matter(seq, matter, indent)

def _add_differing_matter(left, right, left_lines, right_lines, indent):
    for matter, seq, sigil in ((left, left_lines, '-'), 
                               (right, right_lines, '+')):
        if isinstance(matter, _basestring): 
            matter = single_patch_band(indent, matter, sigil)
        add_matter(seq, matter, indent)

def _commafy_last(left_lines, right_lines, left_comma, right_comma):
    if right_comma is None: 
        right_comma = left_comma
    left_lines[-1] = commafy(left_lines[-1], left_comma)
    right_lines[-1] = commafy(right_lines[-1], right_comma)

# ----------------------------------------------------------------------

class Gap(object):
    pass

def reconstruct_alignment(left, right, diff):
    '''Reconstruct the sequence alignment between the lists ``left``
    and ``right`` implied by ``diff``.'''
    keys = [stanza[0][0] for stanza in diff]
    align_length = max(len(left), len(right), max(keys) + 1)

    left_a = left[:] + ([Gap()] * (align_length - len(left)))
    right_a = [Gap()] * (align_length)
    rights = iter(right)
    for i in range(align_length):
        if [[i]] not in diff:
            right_a[i] = next(rights)
    return left_a, right_a

def generate_udiff_lines(left, right):
    '''Combine the diff lines from ``left`` and ``right``, and
    generate the lines of the resulting udiff.'''
    assert len(left) == len(right), (left, right)
    right_gens = iter(right)
    for left_g in left:
        right_g = next(right_gens)
        left_line = next(left_g, None)
        if (left_line is not None) and (left_line[0] == ' '):
            right_line = next(right_g)
            assert left_line == right_line, (left_line, right_line)
            yield left_line
            for line in left_g:
                right_line = next(right_g)
                assert line == right_line, (line, right_line)
                yield line
        else:
            if left_line is not None:
                assert left_line[0] == '-', left_line
                yield left_line
                for line in left_g:
                    assert line[0] == '-', line
                    yield line

            for line in right_g:
                assert line[0] == '+', line
                yield line

# ----------------------------------------------------------------------
# Functions for applying udiffs as patches.

def extended_json_decoder():
    '''Return a decoder for the superset of JSON understood by the
    upatch function.

    The exact nature of this superset is documented in the manpage for
    json_patch(1).  Briefly, the string ``...`` is accepted where
    standard JSON expects a ``{<property name>}: {<object>}``
    construction, and the string ``...``, optionally followed by a
    number in parentheses, is accepted where standard JSON expects an
    array element.

    The superset is implemented by parsing ``...`` in JSON objects as
    a key/value pair ``Ellipsis: True`` in the resulting dictionary,
    and ``...({num}){?}`` as a subsequence of ``{num}`` ``Ellipsis``
    objects, or one ellipsis object if ``({num})`` is not present.

    Examples:

    >>> dec = extended_json_decoder()
    >>> (dec.decode('{"foo": "bar",...,"baz": "quux"}') ==
    ...  {"foo": "bar", "baz": "quux", Ellipsis: True})
    True
    >>> dec.decode('[...]')
    [Ellipsis]
    >>> dec.decode('["foo",...(3),"bar"]')
    [u'foo', Ellipsis, Ellipsis, Ellipsis, u'bar']
    '''
    dec = decoder.JSONDecoder()
    dec.parse_object = _JSONObject
    dec.parse_array = _JSONArray
    dec.scan_once = scanner.py_make_scanner(dec)
    return dec

# The following functions are taken from the internals of the json
# module, and extended to cope with the udiff superset.

def _JSONObject(s_and_end, *args):
    # The function signature of json.scanner.JSONObject() changed
    # between python versions 2.7 and 3.  The following is an ugly
    # shim to compensate.
    _w = decoder.WHITESPACE.match
    _ws = decoder.WHITESPACE_STR
    if isinstance(args[0], bool):
        (strict, scan_once, object_hook, object_pairs_hook, memo) = args
    else:
        (encoding, strict, scan_once, object_hook, object_pairs_hook) = args

    def check_ellipsis(end):
        if s[end:end+3] == '...':
            pairs_append((Ellipsis, True))
            end += 3
            if s[end] == ',':
                end += 1
        return end
    def consume_whitespace(end):
        try:
            nextchar = s[end]
            if nextchar in _ws:
                end += 1
                nextchar = s[end]
                if nextchar in _ws:
                    end = _w(s, end + 1).end()
                    nextchar = s[end]
        except IndexError:
            nextchar = ''
        return nextchar, end

    s, end = s_and_end
    pairs = []
    pairs_append = pairs.append

    # Use a slice to prevent IndexError from being raised, the following
    # check will raise a more specific ValueError if the string is empty
    nextchar = s[end:end + 1]
    # Normally we expect nextchar == '"'
    if nextchar != '"':
        if nextchar in _ws:
            end = _w(s, end).end()
            nextchar = s[end:end + 1]
        end = check_ellipsis(end)
        nextchar = s[end:end + 1]
        # Trivial empty object
        if nextchar == '}':
            if object_pairs_hook is not None:
                result = object_pairs_hook(pairs)
                return result, end + 1
            pairs = dict(pairs)
            if object_hook is not None:
                pairs = object_hook(pairs)
            return pairs, end + 1
        elif nextchar != '"':
            raise ValueError(decoder.errmsg(
                "Expecting property name enclosed in double quotes", s, end))
    end += 1
    while True:
        key, end = decoder.py_scanstring(s, end, strict=strict)

        # To skip some function call overhead we optimize the fast paths where
        # the JSON key separator is ": " or just ":".
        if s[end:end + 1] != ':':
            end = _w(s, end).end()
            if s[end:end + 1] != ':':
                raise ValueError(decoder.errmsg("Expecting ':' delimiter", s, end))
        end += 1

        try:
            if s[end] in _ws:
                end += 1
                if s[end] in _ws:
                    end = _w(s, end + 1).end()
        except IndexError:
            pass

        try:
            value, end = scan_once(s, end)
        except StopIteration:
            raise ValueError(decoder.errmsg("Expecting object", s, end))
        pairs_append((key, value))

        try:
            nextchar = s[end]
            if nextchar in _ws:
                end = _w(s, end + 1).end()
                nextchar = s[end]
        except IndexError:
            nextchar = ''
        end += 1

        if nextchar == '}':
            break
        elif nextchar != ',':
            raise ValueError(decoder.errmsg("Expecting ',' delimiter", s, end - 1))
        nextchar, end = consume_whitespace(end)
        end = check_ellipsis(end)
        nextchar, end = consume_whitespace(end)

        end += 1
        if nextchar == '}':
            break

        if nextchar != '"':
            raise ValueError(decoder.errmsg(
                "Expecting property name enclosed in double quotes", s, end - 1))
    if object_pairs_hook is not None:
        result = object_pairs_hook(pairs)
        return result, end
    pairs = dict(pairs)
    if object_hook is not None:
        pairs = object_hook(pairs)
    return pairs, end

ELLIPSIS = re.compile(r'\.\.\.(?:\((\d+)\))?')

def _JSONArray(s_and_end, scan_once, _w=decoder.WHITESPACE.match, 
               _ws=decoder.WHITESPACE_STR):
    s, end = s_and_end
    values = []
    nextchar = s[end:end + 1]
    if nextchar in _ws:
        end = _w(s, end + 1).end()
        nextchar = s[end:end + 1]
    # Look-ahead for trivial empty array
    if nextchar == ']':
        return values, end + 1
    _append = values.append
    while True:
        m = ELLIPSIS.match(s[end:])
        if m is not None:
            count = 1 if m.group(1) is None else int(m.group(1))
            values.extend((Ellipsis,) * count)
            end += m.end()
        else:
            try:
                value, end = scan_once(s, end)
            except StopIteration:
                raise ValueError(decoder.errmsg("Expecting object", s, end))
            _append(value)
        nextchar = s[end:end + 1]
        if nextchar in _ws:
            end = _w(s, end + 1).end()
            nextchar = s[end:end + 1]
        end += 1
        if nextchar == ']':
            break
        elif nextchar != ',':
            raise ValueError(decoder.errmsg("Expecting ',' delimiter", s, end))
        try:
            if s[end] in _ws:
                end += 1
                if s[end] in _ws:
                    end = _w(s, end + 1).end()
        except IndexError:
            pass

    return values, end

# ----------------------------------------------------------------------

def fill_in_ellipses(struc, left_part, right_part):
    '''Replace Ellipsis objects parsed out of a udiff with elements
    from struc.'''
    diff = []
    for path in all_paths(right_part):
        try:
            left_sub_struc = follow_path(left_part, path)
        except:
            left_sub_struc = {}
        right_sub_struc = follow_path(right_part, path)
        if right_sub_struc is Ellipsis:
            diff.append([path, copy.deepcopy(follow_path(struc, path))])
        elif isinstance(right_sub_struc, dict) and Ellipsis in right_sub_struc:
            del right_sub_struc[Ellipsis]
            struc_dict = follow_path(struc, path)
            sd_keys = compute_keysets(struc_dict, right_sub_struc)[1]
            for key in sd_keys:
                if key not in left_sub_struc:
                    sub_path = path + [key]
                    diff.append([path + [key], 
                                 copy.deepcopy(follow_path(struc, sub_path))])
    return patch(right_part, diff)

def split_udiff_parts(udiff):
    '''Split ``udiff`` into parts representing subsets of the left and
    right structures that were used to create it.

    The return value is a 2-tuple ``(left_json, right_json)``.  If
    ``udiff`` is a string representing a valid udiff, then each member of
    the tuple will be a structure formatted in the superset of JSON that
    can be interpreted using :func:`extended_json_decoder()`.
    
    The function itself works by stripping off the first character of
    every line in the udiff, and composing ``left_json`` out of those
    lines which begin with ``' '`` or ``'-'``, and ``right_json`` out
    of those lines which begin with ``' '`` or ``'+'``.

    >>> udiff = """--- <stdin>[0]
    ... +++ <stdin>[1]
    ...  {
    ...   "foo": "bar"
    ...   ...
    ...   "baz": 
    ... -  "quux",
    ... +  "quordle",
    ...  
    ... - "bar": null
    ...  
    ... + "quux": false
    ...  }"""
    >>> left_json = """{
    ...  "foo": "bar"
    ...  ...
    ...  "baz": 
    ...   "quux",
    ...
    ...  "bar": null
    ...
    ... }"""
    >>> right_json = """{
    ...  "foo": "bar"
    ...  ...
    ...  "baz": 
    ...   "quordle",
    ...
    ...
    ...  "quux": false
    ... }"""
    >>> split_udiff_parts(udiff) == (left_json, right_json)
    True
    '''
    out_json_seq = udiff.split('\n')
    if out_json_seq[0][:3] == '---' and out_json_seq[1][:3] == '+++':
        out_json_seq = out_json_seq[2:]
    left_json = [line[1:] for line in out_json_seq if line and line[0] != '+']
    right_json = [line[1:] for line in out_json_seq if line and line[0] != '-']
    return '\n'.join(left_json), '\n'.join(right_json)

# ----------------------------------------------------------------------
# Basic script functionality

def main():
    assert len(sys.argv) in (2, 3), sys.argv
    assert sys.argv[1] in ('patch', 'diff')
    if len(sys.argv) == 3:
        assert sys.argv[2] == '-u'

    cmd = '%s%s' % ('u' if '-u' in sys.argv else '', sys.argv[1])
    cmd = eval(cmd) if cmd.lstrip('u') in ('patch', 'diff') else None
    
    args = json.load(sys.stdin)
    if cmd == udiff:
        for line in cmd(*args):
            print(line)
    elif cmd is not None:
        sys.stdout.write(json.dumps(cmd(*args)))

if __name__ == '__main__':
    main()
