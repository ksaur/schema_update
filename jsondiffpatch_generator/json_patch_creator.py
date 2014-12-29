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
import decode
import argparse
import json_delta_diff


__VERSION__ = '0.1'


def generate_upd(dslfile, outfile):
    # parse DSL file
    dsldict = parsedslfile(dslfile)
    function = ""
    getter = ""
    for entry in dsldict:
        list_of_groups = dsldict.get(entry)
        for l in list_of_groups:
            # All commands will have group 1 (command) and group 2 (path)
            cmd =  l.group(1)
            keys = json.loads(l.group(2),object_hook=decode.decode_dict)
            usercode = ""
            newpath = ""
            # load usercode for INIT
            if (cmd == "INIT"):
                usercode = l.group(3)
            # load newpath if REN
            if (cmd == "REN"):
                newpath = json.loads(l.group(3),object_hook=decode.decode_dict) 
            assert(len(keys)>0)
            if (entry != function):
                outfile.write("\ndef update_" + entry + "(rediskey, jsonobj):\n")
                function = entry

            # This next block prints the function sig/decls
            pos = 'e'  # for code generation.
                       # This is the first variable name and we'll increment it
            tabstop = "    "
            codeline = tabstop + pos + " = jsonobj"
            print keys
            for s in keys[0:(len(keys)-1)]:
                print type(s)
                if (type(s) is not list):
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
                outfile.write(codeline+"\n")
                outfile.write(tabstop + "assert(" + pos + " is not None)\n")
                getter = codeline

            # Replace $out's with the variable to assign to
            vartoassign = pos+"[\'" + keys[len(keys)-1] + "\']"
            # whoa. where has this function been my whole life?
            if (cmd == "INIT"):
                usercode = usercode.replace("$out", vartoassign)
                usercode = usercode.replace("$base", pos)
                usercode = usercode.replace("$dbkey", "rediskey")
                usercode = usercode.replace("|", "\n"+tabstop)
                outfile.write(tabstop + usercode+"\n")
            elif (cmd == "DEL"):
                outfile.write(tabstop + "del "+pos+"[\'" + (keys[len(keys)-1]) + "\']\n")
            elif (cmd == "REN"):
                outfile.write(tabstop + pos+"[\'" + (newpath[len(newpath)-1]) + "\'] = "\
                + pos + ".pop("+ "\'" + (keys[len(keys)-1]) + "\'"     + ")\n")
             


def generate_dsltemplate(thediff, outfile):
    print len(thediff)
    for l in thediff:
        assert(len(l) in (1,2))
        keys = l[0]
        assert(len(keys)>0)
        # adding
        if (len(l) == 2):
            outfile.write("INIT " +  (str(keys).replace("\'","\"")) + "\n")
        # deleting.
        else:
            # This writes local path only
            # outfile.write("DEL "+"[\'" + (keys[len(keys)-1]) + "\']\n")
            outfile.write("DEL "+ (str(keys).replace("\'","\"")) + "\n")


# TODO, library call for this?
def startingtoken(l):
    tokens = ['INIT', 'DEL', 'REN', 'UPD']
    for t in tokens:
        if t in l:
            return True
    return False


def parsedslfile(dslfile):

    patterns =  ['(INIT)\\s+(\[.*\])\\s?:\\s?\{(.*)\}',     #INIT [...] : {...}
                 '(REN)\\s+(\[.*\])\\s?->\\s?(\[.*\])',     #REN [...]->[...]
                 '(DEL)\\s+(\[.*\])']

    dsldict = dict()
    def extract_from_re(estr):
        for p in patterns:
            if re.match(p,estr) is not None:
                cmd_re = re.compile(p)
                cmd = cmd_re.search(estr)
                print cmd_re.groups
                for i in range(1,cmd_re.groups+1):
                    print "Group " +str(i) + " = " +  cmd.group(i)
                return cmd
            else:
                print "FAIL"

    for line in dslfile:
        line = line.rstrip('\n')
        # parse multiline cmds
        while startingtoken(line) is False:
            tmp = next(dslfile, None)
            if tmp is not None:
                line += '|' + tmp.rstrip('\n')
            else: # EOF
                break
        print "=========================================\n\nline = " + line
        curr = extract_from_re(line)
        if curr is not None:
            print "found " + str(len(curr.groups())) + " groups"
            print curr.group(2)
            keys = json.loads(curr.group(2),object_hook=decode.decode_dict)
            print keys[0]
            if(keys[0] not in dsldict.keys()):
                dsldict[keys[0]] = [curr]
            else:
                print dsldict[keys[0]]
                print type(dsldict[keys[0]])
                dsldict[keys[0]].append(curr)
    print dsldict
    return dsldict


def bulkload(f, jsonarr):
    for line in f:
        # A file may contain mulitple JSON objects with unknown size.
        # This code will load up all the JSON objects by reading from file
        # until one is successfully parsed.  Continuges until EOF.
        # http://stackoverflow.com/questions/20400818/
        while line is not None:
            try:
                jfile = json.loads(line,object_hook=decode.decode_dict)
                break
            except ValueError:
                # Not yet a complete JSON value
                tmp = next(f, None)
                if tmp is not None:
                    line +=tmp
                else: # EOF
                    break
        print "loaded:"
        print jfile
        jsonarr.append(jfile)



def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--t', nargs=2, help='generate the template dsl file from 2 json template files')
    parser.add_argument('--d', nargs=1, help='process the dsl file and generate the update file')
    args = parser.parse_args()

    # Template option
    if (args.t) is not None:
        file1 = open(args.t[0], 'r')
        file2 = open(args.t[1], 'r')
        outfile = open("generated_dsl_init", 'w')
        jsonarray1 = []
        jsonarray2 = []

        bulkload(file1, jsonarray1)
        bulkload(file2, jsonarray2)
        print "ARRRAY IS:"
        print jsonarray1

        assert len(jsonarray1) == len(jsonarray2), \
         "Files should contain the same number of json templates..."

        for json1, json2 in zip(jsonarray1, jsonarray2):
            thediff = json_delta_diff.diff(json1, json2)
            print ("\nTHE DIFF IS: (len " + str(len(thediff)) + ")")
            print (thediff)

        # generate the template file here
        generate_dsltemplate(thediff, outfile)

    # Process DSL file option
    if (args.d) is not None:

        # Load up the init file
        dslfile = open(args.d[0], 'r')

        # Open the output file
        outfile = open("dsu.py", 'w')

        # Generate the functions based on the DSL file contents
        generate_upd(dslfile, outfile)



if __name__ == '__main__':
    main()
