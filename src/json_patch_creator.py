'''

This is the main file for generating the update code.

Two modes: 
  1. generate a template to fill out from two (old and new) json test data files
  2. generate the python code to perform the update using the template file

Requires Python 2.7.
'''
import bisect, copy, sys, re
import json
import decode
import argparse
import json_delta_diff


__VERSION__ = '0.2'
<<<<<<< HEAD


def generate_add_key(keyglob, usercode, outfile, prefix):
    """
    Generate code to add databasekeys

    @param keyglob: the limited keyglob of keys to add. (ranges but no wildcards)
    @param usercode: the code to initialize the new key 
    @type usercode: string
    @param outfile: the file to write the generated function to
    @param prefix: a string to ensure function name uniqueness
    @return: a dictionary of ( key blob command -> functions to call)
    """
    # write the function signature to file
    #print "USERCODE"
    #print str(type(usercode)) + usercode
    funname = re.sub(r'\W+', '', str(prefix +"_update_" + keyglob))
    outfile.write("\ndef "+ funname + "(rediskey, jsonobj):\n")
    tabstop = "    "
    usercode = usercode.replace("$out", 'rediskey') #We'll assume the user meant this..
    usercode = usercode.replace("$dbkey", "rediskey")
    usercode = usercode.replace("|", "\n"+tabstop)
    outfile.write(tabstop + usercode+"\n")
    return [funname]
=======
>>>>>>> master


def generate_upd(cmddict, outfile, prefix):
    """
    Generate the update functions for each keyset.
    @param cmddict: a dictionary of commands mapped to regex (INIT, UPD, etc) 
    @param outfile: the file to write the generated function to
    @param prefix: a string to ensure function name uniqueness
    @return: a dictionary of ( key blob command -> functions to call)
    """
    function = ""
    getter = ""
    funname_list = list()
    for entry in cmddict:
        list_of_groups = cmddict.get(entry)
        for l in list_of_groups:
            # All commands will have group 1 (command) and group 2 (path)
            cmd =  l.group(1)
            keys = json.loads(l.group(2),object_hook=decode.decode_dict)
            usercode = ""
            newpath = ""
            # load usercode for INIT and UPD
            if (cmd == "INIT" or cmd == "UPD"):
                usercode = l.group(3)
            # load newpath if REN
            if (cmd == "REN"):
                newpath = json.loads(l.group(3),object_hook=decode.decode_dict) 
            assert(len(keys)>0)
            if (entry != function):
                # write the function signature to file
                name = re.sub(r'\W+', '', str(prefix +"_update_" + entry))
                outfile.write("\ndef "+ name + "(rediskey, jsonobj):\n")
                # store the name of the function to call
                funname_list.append(name)
                function = entry
                getter = ""

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
            if (cmd == "UPD"):
                outfile.write(tabstop + "tmp = " + vartoassign +"\n")
                usercode = usercode.replace("$in", "tmp") 
            if (cmd == "INIT" or cmd == "UPD"):
                usercode = usercode.replace("$out", vartoassign)
                usercode = usercode.replace("$base", pos)
                usercode = usercode.replace("$root", "jsonobj")
                usercode = usercode.replace("$dbkey", "rediskey")
                usercode = usercode.replace("|", "\n"+tabstop)
                outfile.write(tabstop + usercode+"\n")
            elif (cmd == "DEL"):
                outfile.write(tabstop + "del "+pos+"[\'" + (keys[len(keys)-1]) + "\']\n")
            elif (cmd == "REN"):
                outfile.write(tabstop + pos+"[\'" + (newpath[len(newpath)-1]) + "\'] = "\
                + pos + ".pop("+ "\'" + (keys[len(keys)-1]) + "\'"     + ")\n")
    return funname_list
             

def generate_dsltemplate(thediff, outfile):
    """
    Compute a diff and generate some stubs of INIT/DEL for the user to get started with
    """
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


def parse_dslfile_inner(dslfile):
    """
    parses the inner portion of dsl funtions:
    {  .....(Rules beginning with INIT, UPD, REN, DEL).....}
    
    @return: a dictionary of rules that match the expected regular expressions
    """

    patterns =  ['(INIT)\\s+(\[.*\])\\s?\\s?\{(.*)\}',     #INIT [...] {...}
                 '(UPD)\\s+(\[.*\])\\s?\\s?\{(.*)\}',      #UPD [...] {...}
                 '(REN)\\s+(\[.*\])\\s?->\\s?(\[.*\])',     #REN [...]->[...]
                 '(DEL)\\s+(\[.*\])']                       #DEL [...]

    dsldict = dict()
    def extract_from_re(estr):
        for p in patterns:
            if re.match(p,estr) is not None:
                cmd_re = re.compile(p)
                cmd = cmd_re.search(estr)
                print cmd_re.groups
                for i in range(1,cmd_re.groups+1):
                    print "inner Group " +str(i) + " = " +  cmd.group(i)
                return cmd
            else:
                print "FAIL"

    for line in dslfile:
        print "first line" + line
        line = line.rstrip('\n')
        print "next line" + line
        
        # parse multiline cmds. INIT and UPD have usercode, DEL and REN do not.
        if (("INIT" in line) or ("UPD" in line)): 
            while ("}" not in line):
                tmp = next(dslfile, None)
                if tmp is not None:
                    line += '|' + tmp.rstrip('\n')
                    print line
                else: # EOF
                    break
        print "=========================================\n\nline = " + line
        curr = extract_from_re(line)
        if curr is not None:
            print "found " + str(len(curr.groups())) + " groups"
            print curr.group(2)
            keys = json.loads(curr.group(2),object_hook=decode.decode_dict)
            if (type(keys[0]) is list): #TODO other cases?? What if mid-list?  more testing needed.
                dsldict[keys[0][0]] = [curr]
            elif(keys[0] not in dsldict.keys()):
                dsldict[keys[0]] = [curr]
            else:
                dsldict[keys[0]].append(curr)
    print dsldict
    return dsldict

def parse_dslfile(dslfile):
    """
    Takes as input the DSL file in the format of: 
    for * {  .....(Rules beginning with INIT, UPD, REN, DEL).....}
    
    @return: a list of tuples (key:string (if any), commands:dictionary)
    """
    patterns =  ['(for) \\s?(.*)\\s?{',
                 '(add) \\s?(.*)\\s?{']

    def extract_for_keys(estr):
        for p in patterns:
            if re.match(p,estr) is not None:
                cmd_re = re.compile(p)
                cmd = cmd_re.search(estr)
                print "outer Group 2  = " +  cmd.group(2)
                return cmd
            else:
                print "FAIL (for/add)"

    tups = list() # for returning
    for line in dslfile:
        l = list() # list of all the readin dsl lines

        # skip blank lines in between "for key *{...};" stanzas
        if line == "\n":
           continue

        # get the "for/add ..." line,

        parsed = extract_for_keys(line)
        if parsed is None:
            sys.exit("\n\nFatal - Parse error near line containing: " + line)
        cmd = parsed.group(1)
        keyglob = parsed.group(2).strip()
        curr = next(dslfile, None)
        while curr and "};" not in curr:
            l.append(curr)
            curr = next(dslfile, None)
        print "LIST=" + str(l)
        # parse the stuff inside the "for" stanza
        if (cmd == "for"):
            inner = parse_dslfile_inner(iter(l))
            print "for INNER = " + str(inner)
        else: #guaranteed cmd == "add", else would have failed in 'extract'
            if "*" in keyglob or "?" in keyglob:
                sys.exit("\n\nFatal - Cannot use wildcards in keyglob for adding keys.\n")
            inner =  '|'.join(l)
        tups.append((cmd, keyglob, inner))
    print tups
    return tups


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


def make_template(file1, file2):
    """
    This function is the entry point for generating the template
  
    This function creates a file called "generated_dsl_init" from
    the diff of two json templates.

    @param file1: the original 'schema' sample json file
    @type file1: string
    @param file2: the new 'schema' sample json file
    @type file2: string
    """
    f1 = open(file1, 'r')
    f2 = open(file2, 'r')
    outfile = open("generated_dsl_init", 'w') #TODO params
    jsonarray1 = []
    jsonarray2 = []

    bulkload(f1, jsonarray1)
    bulkload(f2, jsonarray2)
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

def process_dsl(file1, outfile="dsu.py"):
    """
    This function is the entry point for generating the update code.

    This function processes the dsl file and generates the update file "dsu.py"
    (or other name as specified) to update the json entries in the databse
    """

    # Open the init file
    dslfile = open(file1, 'r')

    # Open the output file
    outfile = open(outfile, 'w')

    # parse DSL file
    dsllist = parse_dslfile(dslfile)

    # create a list to store the parsed dsl output
    kv_update_pairs = list()

    # Generate the functions based on the DSL file contents
    # (Use the index as the namespace, as the keystring has too many special chars) 
    for idx, curr_tup in enumerate(dsllist):
        if (curr_tup[0] == "for"):
            kv_update_pairs.append((curr_tup[1], generate_upd(curr_tup[2], outfile, "group_"+str(idx))))
        elif (curr_tup[0] == "add"):
            kv_update_pairs.append((curr_tup[1], generate_add_key(curr_tup[1], curr_tup[2], outfile, "group_"+str(idx))))

    # write the name of the key globs and corresponding functions
    outfile.write("\ndef get_update_pairs():\n    return " + str(kv_update_pairs))

    # cleanup
    outfile.close()
    dslfile.close()
         

def main():

    """
    To generate a template to fill out (containing the added/deleted fields between 2 json files):
  
    >>> python json_patch_creator.py --t ../tests/data/example_json/sample1.json ../tests/data/example_json/sample2.json

    To generate the update code from the template:

    >>> python json_patch_creator.py --d ../tests/data/example_json/sample_init

    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--t', nargs=2, help='generate the template dsl file from 2 json template files')
    parser.add_argument('--d', nargs=1, help='process the dsl file and generate the update file')
    args = parser.parse_args()

    # Template option
    if (args.t) is not None:
        make_template(args.t[0], args.t[1])

    # Process DSL file option
    if (args.d) is not None:
        process_dsl(args.d[0])


if __name__ == '__main__':
    main()
