#  This modification of "class StrictRedis(object)" is from: 
#  https://github.com/andymccurdy/redis-py/blob/master/redis/client.py
#
#  That code had the following license:
#
#  Copyright (c) 2012 Andy McCurdy
#  Permission is hereby granted, free of charge, to any person
#  obtaining a copy of this software and associated documentation
#  files (the "Software"), to deal in the Software without
#  restriction, including without limitation the rights to use,
#  copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the
#  Software is furnished to do so, subject to the following
#  conditions:
#  The above copyright notice and this permission notice shall be
#  included in all copies or substantial portions of the Software.
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
#  OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
#  NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#  HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
#  OTHER DEALINGS IN THE SOFTWARE.
"""
    The following modifications were made to address key versioning:
    * All keys are prepended with a version number and pipe.  
        ex:  key0 at version v0 becomes "v0|key0".

    To make redis operation work, this class:
    * Tries prepending all possible version strings for:
        delete, get
    * Prepends only the most recent version string for:
        set
    * Prepend wildcard (*|) to keyglob for:
        keys
  
    Also, 'flushall' preserves the stored list of versions

    Additional bookkeeping for lazy update:
    * A redis list called "UPDATE_VERSIONS_NS", which is a list of version name strings
         for each namespace NS.  (There will be a list of versions for each namespaces)
         Ex: "UPDATE_VERSIONS_NS" -> ["V1"]

    * A redis hash of "UPDATE_DSL_STRINGS", which stores a hash mapping version name strings
         concatinated with namespaces to DSL strings (for generating to modules later by 
         other connected clients into the self.upd_dict 
         as clients connect)  One "UPDATE_DSL_STRINGS" hash total.
         Ex:  "UPDATE_DSL_STRINGS" -> { "(V1, V2, NS)" : "for ns:... v0->v1", 
              "(V1, V2, NS2)" : "add ns2....v0"}
    * Update functions are stored in a dictionary named self.upd_dict
      This stores "version string+ -> (version module, dict of (keyglob->module function strings))
         Ex: TODO 
 
   
    The initial (preupdate) version is named "INITIAL_V0" 
    (global string "initial_version" for now).  Subsequent
    versions will be named when the user passes in the set of corresponding
    update functions.
"""

import redis
import json, re, sys, fnmatch, decode, time
import json_patch_creator
from ast import literal_eval
sys.path.append("/tmp") # for generating update modules from dsl

from redis.client import (dict_merge, string_keys_to_dict, sort_return_tuples,
    float_or_none, bool_ok, zset_score_pairs, int_or_none, parse_client_list,
    parse_config_get, parse_debug_object, parse_hscan, parse_info,
    timestamp_to_datetime, parse_object, parse_scan, pairs_to_dict, 
    parse_sentinel_get_master, parse_sentinel_master, parse_sentinel_masters,
    parse_sentinel_slaves_and_sentinels, parse_slowlog_get, parse_zscan)

from redis._compat import (basestring, iteritems, iterkeys, itervalues, long,
    nativestr)

from redis.connection import (ConnectionPool, UnixDomainSocketConnection,
    SSLConnection, Token)
from redis.exceptions import (
    ConnectionError,
    DataError,
    ExecAbortError,
    NoScriptError,
    PubSubError,
    RedisError,
    ResponseError,
    TimeoutError,
    WatchError,
)
from redis.client import StrictPipeline, StrictRedis

class LazyUpdateRedis(StrictRedis):
    """
    Lazy implementation of the Redis protocol, with wrappers to add/remove version 
    strings to/from the keys, and to update the keys as necessary.

    ----------

    From previous "StrictRedis:"
    This abstract class provides a Python interface to all Redis commands
    and an implementation of the Redis protocol.

    Connection and Pipeline derive from this, implementing how
    the commands are sent and received to the Redis server
    """

    def __init__(self, client_ns_versions, host='localhost', port=6379,  
                 db=0, password=None, socket_timeout=None,
                 socket_connect_timeout=None,
                 socket_keepalive=None, socket_keepalive_options=None,
                 connection_pool=None, unix_socket_path=None,
                 encoding='utf-8', encoding_errors='strict',
                 charset=None, errors=None,
                 decode_responses=False, retry_on_timeout=False,
                 ssl=False, ssl_keyfile=None, ssl_certfile=None,
                 ssl_cert_reqs=None, ssl_ca_certs=None):
        if not connection_pool:
            if charset is not None:
                warnings.warn(DeprecationWarning(
                    '"charset" is deprecated. Use "encoding" instead'))
                encoding = charset
            if errors is not None:
                warnings.warn(DeprecationWarning(
                    '"errors" is deprecated. Use "encoding_errors" instead'))
                encoding_errors = errors

            kwargs = {
                'db': db,
                'password': password,
                'socket_timeout': socket_timeout,
                'encoding': encoding,
                'encoding_errors': encoding_errors,
                'decode_responses': decode_responses,
                'retry_on_timeout': retry_on_timeout
            }
            # based on input, setup appropriate connection args
            if unix_socket_path is not None:
                kwargs.update({
                    'path': unix_socket_path,
                    'connection_class': UnixDomainSocketConnection
                })
            else:
                # TCP specific options
                kwargs.update({
                    'host': host,
                    'port': port,
                    'socket_connect_timeout': socket_connect_timeout,
                    'socket_keepalive': socket_keepalive,
                    'socket_keepalive_options': socket_keepalive_options,
                })

                if ssl:
                    kwargs.update({
                        'connection_class': SSLConnection,
                        'ssl_keyfile': ssl_keyfile,
                        'ssl_certfile': ssl_certfile,
                        'ssl_cert_reqs': ssl_cert_reqs,
                        'ssl_ca_certs': ssl_ca_certs,
                    })
            connection_pool = ConnectionPool(**kwargs)
        self.connection_pool = connection_pool
        self._use_lua_lock = None
        self.response_callbacks = self.__class__.RESPONSE_CALLBACKS.copy()
        self.client_ns_versions = dict()

        # check to see if we are the initial version and must init
        for (ns, v) in client_ns_versions:
            self.append_new_version(v, ns, startup=True)

        # check to see if existing updates need to be loaded into this client
        self.upd_dict = dict()
        self.load_upd_tuples()
 
        print "Connected with the following versions: " + str(self.client_ns_versions)

    def append_new_version(self, v, ns, startup=False):
        """
        Append the new version (v) to redis for namespace (ns)
        """
        try:
            pipe = self.pipeline()
            pipe.watch("UPDATE_VERSIONS_"+ns)
            pipe.multi()
            curr_ver = self.global_curr_version(ns)
            self.client_ns_versions[ns] = v
            # Check if we're already at this namespace
            if (v == curr_ver):
                return 0
            # Check to see if this version is old for this namespace
            elif (startup and (v in self.global_versions(ns))):
                raise ValueError('Fatal - Trying to connect to an old version')
            # Check to see if we're trying to connect to a bogus version
            elif (startup and (curr_ver is not None) and (v != curr_ver)):
                raise ValueError('Fatal - Trying to connect to a bogus version for namespace: ' + ns)
            # Either the namespace exists, and we need to add a new version
            # or no such namespace exists, so create a version entry for new namespace
            # This call will do either.
            else:
                pipe.rpush("UPDATE_VERSIONS_"+ns, v)
            rets = pipe.execute()
            if rets:
                return rets[-1]
            return None
        except WatchError:
            print "WATCH ERROR, Value not set for UPDATE_VERSIONS"
            return None

    def global_versions(self, ns):
        """
        Return the LIST of ALL versions from redis for namespace ns
        @param ns: the namespace
        """
        return self.lrange("UPDATE_VERSIONS_"+ns, 0, -1)

    def global_curr_version(self, ns):
        """
        Return the most current version from redis for namespace ns
        @param ns: the namespace
        """
        val = self.lindex("UPDATE_VERSIONS_"+ns, -1)
        if val is not None:
            return val
        print "WARNING: no namespace found for \'" + ns + "\'. Checking default:"
        return self.lindex("UPDATE_VERSIONS_*", -1)

    def namespace(self, name):
        return json_patch_creator.parse_namespace(name)


    def delete(self, *names):
        "Delete one or more keys specified by ``names``"
        # Delete doesn't allow keyglob, must expand all
        newnames = list()
        for n in names:
            v = self.global_versions(self.namespace(n))
            newnames.extend(map(lambda x: x + "|" + n, v))
        return self.execute_command('DEL', *newnames)

   
    def update(self, currkey, redisval, funcs, m):
        """ 
        Loop over the list of funcs and apply it to the value at currkey

        @return: A list [key, value] to feed to redis for setting
        """
        jsonkey = json.loads(redisval, object_hook=decode.decode_dict)
        for funcname in funcs:
            try:
                func = getattr(m,funcname)
            except AttributeError as e:
                print "(Could not find function: " + funcname + ")"
                return None
            # Call the function for the current key and current jsonsubkey
            (modkey, modjson) = func(currkey, jsonkey)
            print "GOT BACK: " + str(modkey) + " " + str(modjson)

        modjsonstr = json.dumps(modjson)
        return [modkey, modjsonstr]

    def get(self, name):
        """
        Return the value at key ``name``, updating to most recent version if necessary,
        or return None if the key doesn't exist
  
        Return False if there was a concurrency error. #TODO what is best here?!?!
        """

        ns = self.namespace(name)
        global_ns_ver = self.global_curr_version(ns)
        client_ns_ver = self.client_ns_versions[ns]

        # Make sure the client has been updated to this version
        if global_ns_ver != client_ns_ver:
            err= "Could not update key:" + name + ".\nTo continue, " +\
                "you must update namespace \'" + ns + "\' to version " + global_ns_ver +\
                ".  Currently at namespace version " + client_ns_ver +\
                " for \'" + ns + "\'"
            raise DeprecationWarning(err)
        
        # Check to see if the requested key is already current
        orig_name = global_ns_ver + "|" + name
        val = self.execute_command('GET', orig_name)
        # Return immediately if no update is necsesary
        if(val):
            print "\tNo update necessary for key: " + name + " (version = " + global_ns_ver + ")"
            return val

        # No key found at the current version.
        # Try to get a matching key. Ex: if key="foo", try "v0|key", "v1|key", etc
        vers_list = self.global_versions(ns)
        curr_key_version = None
        for v in reversed(vers_list[:-1]): # this will test the most current first
            orig_name = v + "|" + name
            val = self.execute_command('GET', orig_name)
            # Found a key!  Figure out which version and see if it needs updating
            if val is not None:
                curr_key_version = orig_name.split("|", 1)[0]
                ### print "key ns version: " + curr_key_version
                print "GOT KEY " + name + " at VERSION: " + v
                break
        # no key at 'name' for any eversion.
        if curr_key_version == None:
            return None


        ######### LAZY UPDATES HERE!!!! :)  ########

        # Version isn't current.  Now check for updates
        curr_idx = vers_list.index(curr_key_version)
        new_name = vers_list[-1] + "|" + name
        print "\tCurrent key is at position " + str(curr_idx) +\
            " in the udp list, which means that there is/are " + \
            str(len(vers_list)-curr_idx-1) + " more update(s) to apply"

        try:
            pipe = self.pipeline()
            pipe.watch(orig_name)
            # must call "watch" on all before calling multi.
            for upd_v in vers_list[curr_idx+1:]:
                pipe.watch(upd_v + "|" + name)
            pipe.multi()

            # Apply 1 or multiple updates, from oldest to newest, if necessary
            for upd_v in vers_list[curr_idx+1:]:

                # Make sure we have the update in the dictionary
                upd_name = (curr_key_version, upd_v, ns)
                if upd_name not in self.upd_dict:
                    err= "Could not update key:" + name + ".  Could not find " +\
                        "update \'" + str(upd_name) +"\' in update dictionary."
                    raise KeyError(err)

                # Grab all the information from the update dictionary...
                print "Updating to version " + upd_v + " using update \'" + str(upd_name) +"\'"
                # Combine all of the update functions into a list "upd_funcs_combined"
                #
                # There may be more than one command per update
                #   Ex: for edgeattr:n*@n5 v0->v1
                #       for edgeattr:n4@n* v0->v1
                upd_funcs_combined = list()
                for (module, glob, upd_funcs, new_ver) in self.upd_dict[upd_name]:

                    print "Found a rule."
                    print "new_ver = " + new_ver + " upd_v = " + upd_v
                    # Make sure we have the expected version
                    if (new_ver != upd_v):
                        print "ERROR!!! Version mismatch at : " + name + "ver=" + upd_v 
                        return val
                    # Check if the keyglob matches this particular key
                    # Ex: if the glob wanted key:[1-3] and we are key:4, no update,
                    #     eventhough the namespace matches.
                    print "Searching for a match with glob = " + glob 
                    print "and name = " + name 
                    if re.match(fnmatch.translate(glob), name):
                        print "\tUpdating key " + name + " to version: " + upd_v
                        print "\tusing the following functions:" + str(upd_funcs)
                        print "\twith value:" + val
                        upd_funcs_combined.extend(upd_funcs)

                # if we found some functions to call, then call them (all at once) so the
                # version string only gets written once.
                if upd_funcs_combined:  
                    print "Applying some updates:" + str(upd_funcs_combined)
                    mod = self.update(name, val, upd_funcs_combined, module)
                    if mod:
                        mod[0] = upd_v + "|" + mod[0]
                        pipe.execute_command('SET', *mod)
                        pipe.execute_command('DEL', curr_key_version+ "|" + name)
                        curr_key_version = new_ver
                    else:
                        raise ValueError( "ERROR!!! Could not update key: " + name )
                # no functions matched, update version string only.                   
                else:
                    print "\tNo functions matched.  Updating version str only"
                    print "orig_name "+orig_name + " -> new_name " +new_name
                    pipe.rename(orig_name, new_name)
            # now get and return the updated value
            pipe.execute_command('GET', new_name)
            rets = pipe.execute()
            if rets:
                return rets[-1]
            return None
        except WatchError:
            print "WATCH ERROR, Value not set"
            return False #TODO what to return here?!?!
        

    def keys(self, pattern='*'):
        """
        Returns a list of keys matching ``pattern`` (update tracking version
        strings are stripped off before returning
        """
        pattern = "*|" + pattern
        keylist = self.execute_command('KEYS', pattern)
        return map(lambda x: x.split("|", 1)[1], keylist)


    def set(self, name, value, ex=None, px=None, nx=False, xx=False):
        """
        If the client is at the correct version, then we don't need to run the
        update function, since the client should only set the correct value.
        We only need to update the version string.

        Set the value at key ``name`` to ``value``

        Prepends the current version string to key ``name``.

        ``ex`` sets an expire flag on key ``name`` for ``ex`` seconds.

        ``px`` sets an expire flag on key ``name`` for ``px`` milliseconds.

        ``nx`` if set to True, set the value at key ``name`` to ``value`` if it
            does not already exist.

        ``xx`` if set to True, set the value at key ``name`` to ``value`` if it
            already exists.
        """
        ns = self.namespace(name)
        curr_ver = self.global_curr_version(ns)
        if curr_ver is None:
            raise ValueError("ERROR, Bad current version (None) for key \'" + name +\
                  "\'. Global versions are: " + str(self.global_versions(ns)))
        new_name = curr_ver + "|" + name
        pieces = [new_name, value]
        if ex:
            pieces.append('EX')
            if isinstance(ex, datetime.timedelta):
                ex = ex.seconds + ex.days * 24 * 3600
            pieces.append(ex)
        if px:
            pieces.append('PX')
            if isinstance(px, datetime.timedelta):
                ms = int(px.microseconds / 1000)
                px = (px.seconds + px.days * 24 * 3600) * 1000 + ms
            pieces.append(px)

        if nx:
            pieces.append('NX')
        if xx:
            pieces.append('XX')

        # Even though we're not doing the udpate on the value (since the client 
        # was asserted to be at the correct verson), we still need to update the
        # version string.
        prev = self.global_versions(ns)
        try:
            pipe = self.pipeline()
            pipe.watch(new_name)
            pipe.multi()
            for v in reversed(prev[:-1]):
                oldname = v + "|" + name
                old = pipe.execute_command('GET', oldname)
                if old is not None:
                    pipe.execute_command('DEL', oldname)
                else:
                    break

            pipe.execute_command('SET', *pieces)
            rets = pipe.execute()
            if rets:
                return rets[-1]
            return False
        except WatchError:
            print "WATCH ERROR, Value not set"
            return False
        
   
    def do_upd(self, dsl_file, upd_file_out=None):
        """
        Switch the version string and load up the update functions for lazy updates.
           
        In order for an update to be applied, there must exist a valid namespace.
        Ex: If the update is for namespace = "foo" from "v0"->"v1", but the data
            in redis is "ver0|foo", the update will be rejected, and this function
            will return false 

        @type dsl_file: string
        @param dsl_file: The file with the update functions.

        @return: True for success, False for failure.
        
        """
        if upd_file_out == None:
            upd_file_out = "/tmp/gen_" + str(int(round(time.time() * 1000))) + ".py"
        
        dsl_for_redis = json_patch_creator.parse_dslfile_string_only(dsl_file)

        # Verify that these updates are sensible with the current database.
        for (old,new,ns) in dsl_for_redis:
            if (old != self.global_curr_version(ns)):
                error = "ERROR: Namespace " + str(ns) + " is at \'" +\
                    str(self.global_curr_version(ns)) + "\' but update was for: " + str(old)
                raise KeyError(error)

        json_patch_creator.process_dsl(dsl_file, upd_file_out)
        # strip off extention, if provided
        upd_module = upd_file_out.replace(".py", "").replace("/tmp/", "")

        # do the "add" functions now.
        # NOTE: this code is ONLY for the "add" keys in the dsl, NOT the "for" keys!
        print "importing from " + upd_module
        m = __import__ (upd_module) #m stores the module
        get_newkey_tuples = getattr(m, "get_newkey_tuples")
        tups = get_newkey_tuples()
        for (glob, funcs, ns, version) in tups:
            self.append_new_version(version, ns)

            try:
                func = getattr(m,funcs[0])
            except AttributeError as e:
                print "(Could not find function: " + funcs[0] + ")"
                continue
            # retrieve the list of keys to add, and the usercode to set it to
            (keys, userjson) = func()
            for k in keys:
                self.set(k,json.dumps(userjson))


        # Now, onto the "for" keys.
        # store the update tuples to be called lazily later
        get_update_tuples = getattr(m, "get_update_tuples")
        tups = get_update_tuples()

        
        for (glob, funcs, ns, version_from, version_to) in tups:
            try:
                pipe = self.pipeline()
                pipe.watch("UPDATE_DSL_STRINGS")
                pipe.multi()
                vOldvNewNs = (version_from, version_to, ns)
                if vOldvNewNs not in dsl_for_redis:
                    raise ValueError("ERROR, dsl string not found: "+ str(vOldvNewNs))
                prev = self.hget("UPDATE_DSL_STRINGS", vOldvNewNs)
                joined = '\n'.join(dsl_for_redis[vOldvNewNs])
                if ((prev is not None) and (prev != joined)):
                    raise ValueError("\n\nERROR!!! Already had an update at version " + str(vOldvNewNs) )
                elif (prev != joined):
                    pipe.hset("UPDATE_DSL_STRINGS", vOldvNewNs, joined)
                # make sure we can append to the version list without contention
                if(self.append_new_version(version_to, ns) is None):
                    pipe.reset()
                    return False  #abort!!
                self.upd_dict.setdefault(vOldvNewNs, []).append((m, glob, funcs, version_to))
                pipe.execute()
            except WatchError:
                print "WATCH ERROR, UPD not completed"
                return False
        return True

    def load_upd_tuples(self):
        """
        Load up (on client connect) the existing updates from redis (stored as user DSL)
        by generating the update functions and then loading them into self.upd_dict
        """
        dsl_files = self.hgetall("UPDATE_DSL_STRINGS")
        for vvn_string in dsl_files:
            # Tuple of will be read in as string "("v0", "v1", "ns")". Convert to tuple ("v0", "v1", "ns")
            vvn_tup = literal_eval(vvn_string) 
            # Ensure a unique name to checkout the generated code later if necessary
            name = "/tmp/gen_" + str(int(round(time.time() * 1000))) + "_"+ vvn_tup[2]
            # Write the contents of redis to a file
            dsl_file = open(name, "w")
            dsl_file.write(dsl_files[vvn_string])
            dsl_file.close()

            # Process the DSL file and generate the python update functions
            json_patch_creator.process_dsl(name, name+".py")

            # Now load the generated update functions to be called lazily later
            name = name.replace("/tmp/", "")
            m = __import__ (name) #m stores the module
            get_upd_tuples = getattr(m, "get_update_tuples")
            tups = get_upd_tuples()
            for (glob, funcs, ns, version_from, version_to) in tups:
                self.upd_dict.setdefault(vvn_tup, []).append((m, glob, funcs, version_to))


# Utility function...may move this later...
def connect(client_ns_versions):
    """ 
    Connect to (lazy) redis. Default is localhost, port 6379.
    (Redis must be running.)

    """
    r = LazyUpdateRedis(client_ns_versions)
    try:
        r.ping()
    except r.ConnectionError as e:
        print(e)
        sys.exit(-1)
    return r

