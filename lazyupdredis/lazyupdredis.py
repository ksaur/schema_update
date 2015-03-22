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
#import logging
import json, re, sys, fnmatch, decode, time, os
import json_patch_creator
import socket
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
    SSLConnection, Token, Connection, PythonParser)
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
class NoReConnection(Connection):
    """
    When we kill clients with redis because they are deprecated, don't let
    them simply grab a new connection from the pool!!!!
    """

    def __init__(self, fun_ptr=None, host='localhost', port=6379, db=0, password=None,
                 socket_timeout=None, socket_connect_timeout=None,
                 socket_keepalive=False, socket_keepalive_options=None,
                 retry_on_timeout=False, encoding='utf-8',
                 encoding_errors='strict', decode_responses=False,
                 parser_class=PythonParser, socket_read_size=65536):
        self.pid = os.getpid()
        self.host = host
        self.port = int(port)
        self.db = db
        self.password = password
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout or socket_timeout
        self.socket_keepalive = socket_keepalive
        self.socket_keepalive_options = socket_keepalive_options or {}
        self.retry_on_timeout = retry_on_timeout
        self.encoding = encoding
        self.encoding_errors = encoding_errors
        self.decode_responses = decode_responses
        self._sock = None
        self._parser = parser_class(socket_read_size=socket_read_size)
        self._description_args = {
            'host': self.host,
            'port': self.port,
            'db': self.db,
        }
        self._connect_callbacks = []
        self.vers_check = fun_ptr

    def disconnect(self):
        self.vers_check()



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

        kwargs = {
            'db': db,
            'password': password,
            'socket_timeout': socket_timeout,
            'encoding': encoding,
            'encoding_errors': encoding_errors,
            'decode_responses': decode_responses,
            'retry_on_timeout': retry_on_timeout,
            'fun_ptr': self.verify_ns_info
        }
        # TCP specific options
        kwargs.update({
            'host': host,
            'port': port,
            'socket_connect_timeout': socket_connect_timeout,
            'socket_keepalive': socket_keepalive,
            'socket_keepalive_options': socket_keepalive_options,
        })

        self.connection_pool = ConnectionPool(connection_class=NoReConnection, **kwargs)
        self._use_lua_lock = None
        self.response_callbacks = self.__class__.RESPONSE_CALLBACKS.copy()
        self.client_ns_versions = dict()
        #dict of lists of namespace versions
        self.ns_versions_dict = dict()

        # check to see if we are the initial version and must init
        for (ns, v) in client_ns_versions:
            self.append_new_version(v, ns, startup=True)
        #logging.debug(self.client_ns_versions)

        # check to see if existing updates need to be loaded into this client
        self.upd_dict = dict()
        self.load_upd_tuples()
        self.client_setname(self.ns_dict_as_string())
 
        #logging.info("Connected with the following versions: " + str(self.client_ns_versions))


    def verify_ns_info(self):
        for ns in self.client_ns_versions:
            globalv = self.lindex("UPDATE_VERSIONS_"+ns, 0)
            if (globalv != self.client_ns_versions[ns]):
                 raise DeprecationWarning ("You are at \'" + self.client_ns_versions[ns] + "\' but system is at \'" + globalv + "\' for namespace \'" + ns + "\'")

    def get_connected_client_list_at_ns(self, ns):
        clients = list()
        for c in self.client_list():
            if c["name"] == "": #control channel
                continue
            d = self.name_to_dict(c["name"])
            for e in d:
                if d[e] == ns:
                    clients.append(c)
        return clients

    def kill_connected_clients_at(self, updated_ns):
        """
        @param updated_ns: a set of namespaces to kill the client
        """
        for c in self.client_list():
            if c["name"] == "": #control channel
                continue
            d = self.name_to_dict(c["name"])
            for e in d:
                if (e, d[e]) in updated_ns:
                    #logging.info("Killing deprecated client" + str(c["addr"]))
                    self.client_kill(c["addr"])
            #logging.debug(self.client_list())
        

    def ns_dict_as_string(self):
        d = self.ns_versions_dict
        ret = ""
        for e in d:
            ret += e + ":" + d[e][0] + "|"
        return ret[:-1]

    def name_to_dict(self, name):
        ret = dict()
        for s in name.split('|'):
            p = s.split(':')
            ret[p[0]] = p[1]
        return ret

    def append_new_version(self, v, ns, startup=False):
        """
        Append the new version (v) to redis for namespace (ns)
        """
        try:
            pipe = self.pipeline()
            pipe.watch("UPDATE_VERSIONS_"+ns)
            pipe.multi()
            global_versions = self.lrange("UPDATE_VERSIONS_"+ns, 0, -1)
            if global_versions != []:
                #logging.info("setting curr_ver to: " + str(global_versions[0]))
                #logging.info("global_versions "  + str(global_versions))
                curr_ver = global_versions[0]
            else:
                curr_ver = None
            self.client_ns_versions[ns] = v
            # Check if we're already at this namespace
            if (v == curr_ver):
                if startup:
                    self.ns_versions_dict[ns] = global_versions
                pipe.reset()
                return 0
            # Check to see if this version is old for this namespace
            elif (startup and (v in global_versions)):
                pipe.reset()
                raise ValueError('Fatal - Trying to connect to an old version')
            # Check to see if we're trying to connect to a bogus version
            elif (startup and (curr_ver is not None) and (v != curr_ver)):
                pipe.reset()
                #logging.critical("curr_ver = " + curr_ver)
                #logging.critical("v = " + v)
                raise ValueError('Fatal - Trying to connect to a bogus version for namespace: ' + ns)
            # Either the namespace exists, and we need to add a new version
            # or no such namespace exists, so create a version entry for new namespace
            # This call will do either.
            else:
                #if curr_ver is None:
                    #logging.info("Creating new namespace: " + ns)
                pipe.lpush("UPDATE_VERSIONS_"+ns, v)
            #logging.debug("Prepending new version: " + v)
            global_versions.insert(0, v) 
            self.ns_versions_dict[ns] = global_versions
            rets = pipe.execute()
            pipe.reset()
            if rets:
                return rets[-1]
            return None
        except WatchError:
            #logging.warning("WATCH ERROR, Value not set for UPDATE_VERSIONS")
            return None

    def global_versions(self, ns):
        """
        Return the LIST of ALL versions from local for namespace ns
        @param ns: the namespace
        """
        return self.ns_versions_dict[ns]

    def global_curr_version(self, ns):
        """
        Return the most current version from local for namespace ns
        @param ns: the namespace
        """
        return self.ns_versions_dict[ns][0]

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
        for func_ptr in funcs:
            (modkey, modjson) = func_ptr(currkey, jsonkey)
            #logging.debug("GOT BACK: " + str(modkey) + " " + str(modjson))

        modjsonstr = json.dumps(modjson)
        return [modkey, modjsonstr]

    def get(self, name):
        """
        Return the value at key ``name``, updating to most recent version if necessary,
        or return None if the key doesn't exist
  
        Auto retry if there was a concurrency error. 
        """

        ns = self.namespace(name)
        curr_ver = self.ns_versions_dict[ns][0]
        
	# The "express route" where we find a key at the current version and
	# immediately return.
        val = self.execute_command('GET', curr_ver + "|" + name)
        # Return immediately if no update is necsesary
        if(val):
            return val

        #logging.debug("\tNo curr_ver key: " + name + " (version = " + curr_ver + ")")

        # optimization to quickly (atomically with mget) check if the key exists ANY version
        # (before bothering with the overhead of 'watch' below)
        # Ex: try "v0|key", "v1|key", etc
        vers_list = self.global_versions(ns) #local call, indexes array only
        all_potential_keys = (map(lambda x: x + "|" + name, vers_list))
        vals = self.mget(all_potential_keys) # get ALL the vals!
        if len(vals) == vals.count(None):
            #logging.debug("\tNo key at any version: " + name )
            return None


        ######### LAZY UPDATES HERE!!!! :)  ########
        try:

            # Init the pipe.  Must call "watch" on all before calling multi.
            pipe = self.pipeline()
            for upd_v in vers_list:
                pipe.watch(upd_v + "|" + name) # abort if any version of key 'name' changes.
            pipe.watch("UPDATE_VERSIONS_" +ns) # abort if any new versions added to this namespace
            pipe.multi()

            # atomically get ALL the vals for all possible versions of the key
            vals = self.mget(all_potential_keys) 
            
            # "vals" now contains a list of all Nones if there is no key anywhere
            # else it contains somethign like [None, {data!!}, None] if there's a key at v1.
            curr_idx = -1
            curr_key_version = None
            for idx, v in enumerate(vals):
                if v != None:
                    # Found a key!  Figure out which version and see if it needs updating
                    val = v # stored for use below
                    curr_idx = idx
                    curr_key_version = vers_list[curr_idx]
                    orig_name = curr_key_version + "|" + name 
                    #logging.debug("GOT KEY " + name + " at VERSION: " + curr_key_version)
                    break
            # Check if current key was sucessfully retrived now in concurrent get
            if curr_idx == 0:
                pipe.reset() #return pipe to connection pool, unwatch keys.
                return val
            # Check if no key at 'name' for any version.
            if curr_key_version == None:
                pipe.reset()
                #logging.debug("MISS at key " + name +"\n")
                return None

            #logging.debug("\n>>>>UPDATING " + name)

            # Version isn't current.  Now check for updates
            new_name = vers_list[0] + "|" + name
            #logging.info("\tCurrent key is at position " + str(curr_idx) +\
                #" in the udp list, which means that there is/are " + \
                #str(curr_idx) + " more update(s) to apply")

            # Apply 1 or multiple updates, from oldest to newest, if necessary
            while curr_idx > 0:
                upd_v = vers_list[curr_idx-1]

                # Make sure we have the update in the dictionary
                upd_name = (curr_key_version, upd_v, ns)
                if upd_name not in self.upd_dict:
                    err= "Could not update key \'" + name + "\'.  Could not find " +\
                        "update \'" + str(upd_name) +"\' in update dictionary."
                    pipe.reset()
                    raise KeyError(err)

                # Grab all the information from the update dictionary...
                #logging.info("Updating \'"+ name +"\' to version " + upd_v +\
                    #" using update \'" + str(upd_name) +"\'")
                # Combine all of the update functions into a list "upd_funcs_combined"
                #
                # There may be more than one command per update
                #   Ex: for edgeattr:n*@n5 v0->v1
                #       for edgeattr:n4@n* v0->v1
                upd_funcs_combined = list()
                for (module, glob, upd_funcs, new_ver) in self.upd_dict[upd_name]:

                    #logging.debug("Found a rule. new_ver = " + new_ver + " upd_v = " + upd_v)
                    # Make sure we have the expected version
                    if (new_ver != upd_v):
                        err = "ERROR!!! Version mismatch at : " + name + "ver=" + upd_v 
                        pipe.reset()
                        raise KeyError(err)
                    # Check if the keyglob matches this particular key
                    # Ex: if the glob wanted key:[1-3] and we are key:4, no update,
                    #     eventhough the namespace matches.
                    #logging.debug("Searching for a match with glob = " + glob +"and name = " + name )
                    if re.match(fnmatch.translate(glob), name):
                        #logging.debug( "\tUpdating key " + name + " to version: " + upd_v)
                        #logging.debug( "\tusing the following functions:" + str(upd_funcs))
                        #logging.debug( "\twith value:" + val)
                        upd_funcs_combined.extend(upd_funcs)

                # if we found some functions to call, then call them (all at once) so the
                # version string only gets written once.
                if upd_funcs_combined:  
                    #logging.debug("Applying some updates:" + str(upd_funcs_combined))
                    mod = self.update(name, val, upd_funcs_combined, module)
                    if mod:
                        mod[0] = upd_v + "|" + mod[0]
                        # This is the modifiied JSON value:
                        val = mod[1]
                    else:
                        pipe.reset()
                        raise ValueError( "ERROR!!! Could not update key: " + name )
                # no functions matched, update version string only.                   
                #else:
                    #logging.debug("\tNo functions matched.  Updating version str only")
                    #logging.debug("orig_name "+orig_name + " -> new_name " +new_name)
                curr_key_version = new_ver
                curr_idx=curr_idx-1

            # All updates done, write the new key and wipe the original
            pipe.execute_command('SET', new_name, val)
            pipe.execute_command('DEL', orig_name)
            # execute everything in the pipe (will abort with WatchError if issues)
            pipe.execute()
            pipe.reset()
            return val
        except WatchError:
            pipe.reset()
            #logging.warning("WATCH ERROR on update, retrying get for " + name + "\n")
            return self.get(name)


    def keys(self, pattern='*'):
        """
        Returns a list of keys matching ``pattern`` (update tracking version
        strings are stripped off before returning
        """
        pattern = "*|" + pattern
        keylist = self.execute_command('KEYS', pattern)
        return map(lambda x: x.split("|", 1)[1], keylist)

    def incr(self, name, amount=1):
        """
        Increments the value of ``key`` by ``amount``. If no key exists,
        the value will be initialized as ``amount``
        """
        ns = self.namespace(name)
        vers_list = self.global_versions(ns)
        curr_ver = vers_list[0]

        new_name = curr_ver + "|" + name
        return self.execute_command('INCRBY', new_name, amount)


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
        # this call just locally indexes an array; need list to check if we need to del old ln 533
        vers_list = self.global_versions(ns) 

        new_name = vers_list[0] + "|" + name
        pieces = [new_name, value]

        # This block not-modified from pyredis originalcode
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
        # end not-modified block

        # if there is only one version, don't bother deleting
        #
        # TODO: There needs to be a better way to check if we don't need
        #       to delete old keys than if there is more than 1 version...
        #       Maybe a background thread for deletes or some additional 
        #       bookkeeping would be faster...TBD empirically
        ret =  self.execute_command('SET', *pieces) 
        if (len(vers_list) == 1):
            return ret

        keys_to_del = map(lambda x: x + "|" + name, vers_list[1:])
        self.execute_command('DEL', *keys_to_del)

        return ret

        
    def do_upd_all_now(self, dsl_file):
        """
        Scan through all keys in the database and update as necessary
 
        @param dsl_file: If you haven't already loaded in the update, this will do that
        """ 

        self.do_upd(dsl_file)
 
        arr = self.scan(0)
        if len(arr) is not 2:
            #logging.warning( "WARNING: Could not update...error starting iterator")
            return 0
        updated = 0
        # Memorize the ns version info from the database to cut down on hits to Redis.
        # This assumes that any update triggered AFTER "do_upd_all_now" can be ignored
        # due to the ordering of the calls.
        memo = dict()
        while True:
            #logging.debug("looping over " + str(len(arr[1])))
            for e in arr[1]:
                if "|" not in e:
                    continue
                # Strip off namespace
                (vers, name) = e.split('|',1)
                # Skip current keys
                if ":" in name:
                    ns = self.namespace(name)
                    if ns not in memo:
                        memo[ns] = self.global_curr_version(ns)
                        #logging.info("memoized " + str(memo))
                    if(vers == memo[ns]):
                        #logging.debug("Skipping current " + name)
                        continue
                self.get(name)
                updated+=1
            if arr[0] == 0:
                break
            arr = self.scan(arr[0])
        return updated
   
    def do_upd(self, dsl_file):
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

        upd_file_out = "/tmp/gen_" + str(int(round(time.time() * 1000))) + ".py"
        dsl_for_redis = json_patch_creator.parse_dslfile_string_only(dsl_file)
        if dsl_for_redis is None:
            #logging.error("COULD NOT PARSE DSL")
            return

        # Verify that these updates are sensible with the current database.
        for (old,new,ns) in dsl_for_redis:
            if (old != self.global_curr_version(ns)):
                error = "ERROR: Namespace " + str(ns) + " is at \'" +\
                    str(self.global_curr_version(ns)) + "\' but update was for: " + str(old)
                raise KeyError(error)

        json_patch_creator.process_dsl(dsl_file, upd_file_out)
        # strip off extention, if provided
        upd_module = upd_file_out.replace(".py", "").replace("/tmp/", "")
        #logging.debug("importing from " + upd_module)
        m = __import__ (upd_module) #m stores the module

        # do the "add" functions now.
        # NOTE: this code is ONLY for the "add" keys in the dsl, NOT the "for" keys!
        get_newkey_tuples = getattr(m, "get_newkey_tuples")
        tups = get_newkey_tuples()
        for (glob, funcs, ns, version) in tups:
            self.append_new_version(version, ns)

            try:
                func = getattr(m,funcs[0])
            except AttributeError as e:
                #logging.error("(Could not find function: " + funcs[0] + ")")
                continue
            # retrieve the list of keys to add, and the usercode to set it to
            (keys, userjson) = func()
            for k in keys:
                self.set(k,json.dumps(userjson))


        # Now, onto the "for" keys.
        # store the update tuples to be called lazily later
        get_update_tuples = getattr(m, "get_update_tuples")
        tups = get_update_tuples()

        updated_ns = set() 
        for (glob, funcs, ns, version_from, version_to) in tups:
            try:
                updated_ns.add((ns,version_from))
                pipe = self.pipeline()
                pipe.watch("UPDATE_DSL_STRINGS")
                pipe.multi()
                vOldvNewNs = (version_from, version_to, ns)
                if vOldvNewNs not in dsl_for_redis:
                    pipe.reset()
                    raise ValueError("ERROR, dsl string not found: "+ str(vOldvNewNs))
                prev = self.hget("UPDATE_DSL_STRINGS", vOldvNewNs)
                #logging.debug(dsl_for_redis[vOldvNewNs])
                #logging.debug('\n'.join(dsl_for_redis[vOldvNewNs]))
                joined = '\n'.join(dsl_for_redis[vOldvNewNs])
                if ((prev is not None) and (prev != joined)):
                    pipe.reset()
                    raise ValueError("\n\nERROR!!! Already had an update at version " + str(vOldvNewNs) )
                elif (prev != joined):
                    pipe.hset("UPDATE_DSL_STRINGS", vOldvNewNs, joined)
                # make sure we can append to the version list without contention
                if(self.append_new_version(version_to, ns) is None):
                    pipe.reset()
                    return False  #abort!!
                try:
                    func_ptrs = map(lambda x: getattr(m,x), funcs)
                except AttributeError as e:
                    #logging.warning("(Could not find function: " + funcname + ")")
                    pipe.reset()
                    return False  #abort!!
                self.upd_dict.setdefault(vOldvNewNs, []).append((m, glob, func_ptrs, version_to))
                pipe.execute()
                pipe.reset()
            except WatchError:
                #logging.warning("WATCH ERROR, UPD not completed")
                return False

		# Ok great.  Now disconnect all the clients at old namespaces by
		# killing the connection, erm, but not us.
        self.client_setname(self.ns_dict_as_string())
        self.kill_connected_clients_at(updated_ns)

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
                func_ptrs = map(lambda x: getattr(m,x), funcs)
                self.upd_dict.setdefault(vvn_tup, []).append((m, glob, func_ptrs, version_to))


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
        #logging.error(e)
        sys.exit(-1)
    return r


