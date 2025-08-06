#!/usr/bin/python3.5
## @package UTP
# This module provides accesss to all platform core functions
#
# It should be imported in any code that needs to use platform core functions.
# This include other platform modules and tools.
#
# It will automatically configure the python logging so after you import
# you only need to log info in the python way:
#
# @code
#
# logging.debug('debug message')
# logging.info('message with variable message: {}', 'blah')
# logging.warn('you shall not pass')
# logging.error('this is error message rc: {}', rc)
#
# @endcode
#
# In addition to these normal logging methods, you can will probably want to use
# run() around your main() and log_data() to log parametric data
#
import os
import io
import sys
import logging
import os.path as osp
import json
import re
import time
import types
import marshal
import hashlib
import argparse
import importlib
import importlib.abc
import importlib.machinery
import traceback
import functools
import subprocess
import copy
import pprint
import zipfile
from abc import ABC, abstractmethod
from importlib.util import MAGIC_NUMBER
from fcntl import flock,LOCK_EX,LOCK_UN,LOCK_SH,LOCK_NB
from itertools import groupby
from contextlib import suppress


os.umask(0o002)

# assumes we start in rt/ or rt_N/ or $debug/ or $debug_N/ which is subdir of mtsn
OUR_RT_DIR = os.getcwd()
OUR_REPO_DIR = osp.abspath(osp.dirname(osp.dirname(__file__))) # Our repo dir
OUR_MODULE_DIR = osp.join(OUR_REPO_DIR, 'modules') # Our repo/modules

######  We are bootstrapping...
if OUR_MODULE_DIR not in sys.path:
    sys.path.append(OUR_MODULE_DIR)

from Fails import *
from MediaTools import get_media_name, get_media_path, get_media_rt_path


##### Setup logging first thing
# At first we can only log to the console
#

# Monkey patch the Logger
from Logging import *

def _my_log(self, level, msg, args, exc_info=None, extra=None, stack_info=False,
            _log=logging.Logger._log, section=False, subsection=False, table=False):
    if section:
        msg = create_section(msg)
    elif subsection:
        msg = create_subsection(msg)
    elif table:
        header = None
        footer = False
        name = None
        str_is_str = False
        max_col_width = 35
        if isinstance(table, dict):
            header = table.get('header', None)
            footer = table.get('footer', False)
            name = table.get('name', None)
            str_is_str  = table.get('str_is_str', False)
            max_col_width  = table.get('max_col_width', 35)
        elif hasattr(table, 'header'):
            header = table.header
            footer = getattr(table, 'footer', False)
            name = getattr(table, 'name', None)
            str_is_str = getattr(table, 'str_is_str', False)
            max_col_width = getattr(table, 'max_col_width', 35)

        msg = create_table(header, rows=msg, footer=footer, name=name, str_is_str=str_is_str,
                           max_col_width=max_col_width)

    with suppress(NameError, KeyError):
        # use the variables dictionary on finder, because the top-most get() causes a recursion
        finder = _get_media_scope(scope, media)
        exec_mode = finder.variables.get('exec_mode', None)  # sequence exec mode: NORMAL, RESUME, FAIL
        if exec_mode:
            if extra:
                extra.update(exec_mode=exec_mode)
            else:
                extra = dict(exec_mode=exec_mode)

    return _log(self, level, msg, args, exc_info=exc_info, extra=extra, stack_info=stack_info)

logging.Logger._log = _my_log


from Default import *
import IAm

IAM_TYPE = IAm.on_type()

## Finally, set the loggger level, hook the logger, and setup some short_cut
## functions

# Force the level to INFO or to the level specified in UTP_LOG_LEVEL
logging.basicConfig(style='{', level=os.environ.get('UTP_LOG_LEVEL', logging.INFO))


## setup the root logger
_logger = logging.getLogger()

# Setup some shortcuts for root-level special logging events
_log = Log(_logger, IAM_TYPE)

for attr in dir(_log):
    if attr.startswith('_'):
        continue
    globals()['log_{}'.format(attr)] = getattr(_log, attr)

# Patch this one up
globals()['log_pass'] = globals()['log_pass_']


class KeepSetOnPass:
    """! Provide a conext for pre-incrementing a variable,
    but restoring if the context is left via exception
    """
    delete_me = 'delete me!!!!'
    def __init__(self, name, value, media, scope, ignore=None):
        self.name = name
        self.value = value
        self.media = media
        self.scope = scope
        self.ignore = ignore
        self._original = get(self.name, default=self.delete_me, media=media, scope=scope)
        globals()['set'](self.name, self.value, media=self.media, scope=self.scope)

    def __enter__(self):
        pass

    def __exit__(self, *exc):
        if exc[0] or exc[1] or exc[2]:
            if self.ignore is None or not isinstance(exc[1], self.ignore):
                if self._original == self.delete_me:
                    delete(self.name)
                else:
                    globals()['set'](self.name, self._original, media=self.media, scope=self.scope)

class temp_set:
    """! Set a variable in context, restore on exiting context """
    delete_me = 'delete me!!!'
    def __init__(self, name, value, media=None, scope='l1'):
        self.name = name
        self.value = value
        self.media = media
        self.scope = scope
        self._original = get(self.name, default=self.delete_me, media=media, scope=scope)

    def __enter__(self):
        globals()['set'](self.name, self.value, media=self.media, scope=self.scope)

    def __exit__(self, *exc):
        if self._original == self.delete_me:
            delete(self.name)
        else:
            globals()['set'](self.name, self._original, media=self.media, scope=self.scope)


def our_media():
    """ ! Return the name of our own media
    @return basename of our MTSN

    Requires variables SN and MT be set.
    """
    return get_media_name(get('SN'), get('MT'))

def our_media_path():
    """ ! Return the full path of our MTSN
    @return The full path of our MTSN as it would be found on L1 or L2

    Requires variables SN and MT be set.
    """
    #return get_media_path(our_media())
    return OUR_REPO_DIR

### Setup the global store for remote control
## There are two types of Platform, local and remote
import PlatformABC
import Variable
import FileTools
import Remote
import Run
import Misc

from PlatformABC import UTPVariableNotSet
from Locations import *   # Bring the attributes defined in Locations into our namespace


_loc = {}

LOCAL_LOGGING_SCOPES = ('l1', )


def _get_scope(scope, cwd):
    if scope not in _loc:
        _loc[scope] = {}

    if cwd not in _loc[scope]:
        if scope == IAM_TYPE or scope == 'local':
            # our actual scope matched to requested scope
            # or the scope is being forced to local => access our resources locally
            _loc[scope][cwd] = LocalLocation(cwd, scope)
        else:
            # non-local scope requires $SCOPE_IP (at minimum) be set and that we can login with ssh at that location
            remote = get_remote_by_scope(log=Log(_logger, scope=scope), scope=scope, target_cwd=cwd)
            if scope not in LOCAL_LOGGING_SCOPES:
                remote.remote.enable_logging(scope, _logger.getEffectiveLevel())
            _loc[scope][cwd] = remote

    return _loc[scope][cwd]


def _get_media_scope(scope, media, media_index=None):
    ## Allow an override that will force all access to local access
    if os.environ.get('UTP_ALL_SCOPE_LOCAL', False):
        rt_path = '.' if media is None and media_index is None else get_media_rt_path(media, media_index)
        return LocalLocation(cwd=rt_path, scope=os.environ['UTP_ALL_SCOPE_LOCAL'])

    assert not (scope == 'local' and media), 'local scope can be on any machine so media must be None (cannot expect media to be present)'
    assert not (scope == 'l3' and media), 'l3 scope and specifying a media does not make sense'
    assert not (scope == 'uut' and media), 'uut scope and media is not currently supported, use scope=$OTHER_IP'
    
    if scope == 'local':
        return _get_scope('local', OUR_RT_DIR)
    elif scope == 'uut':
        return _get_scope('uut', '/var/tmp')
    elif scope == 'l3':
        return _get_scope('uut', '/var/tmp')
    elif scope in ('l1', 'l2'):
        media_path = get_media_rt_path(media, media_index)
        return _get_scope(scope, media_path)
    else:
        # Assume scope=[user[:password]@]IP[:port][/dir]
        return _get_scope(scope, None)


# Finally hook the logging
def _hook_logging():
    """! Fetch the root logger and add platform handlers """
    import LogHandlers

    # Need to remove any handlers that got auto-added
    for handler in list(_logger.handlers):
        _logger.removeHandler(handler)

    # Always add the STD logger
    _logger.addHandler(LogHandlers.STDLogHandler(owner=osp.basename(sys.argv[0]), cwd=get_media_rt_path(), scope=IAM_TYPE))

    # When running on the L1 always do direct file logging
    # tester.log/test.log/error.log/errors.log/logdata.utp model
    _logger.addHandler(LogHandlers.ErrorLogHandler(owner=osp.basename(sys.argv[0]), cwd=OUR_RT_DIR, scope=IAM_TYPE))
    _logger.addHandler(LogHandlers.TestLogHandler(owner=osp.basename(sys.argv[0]), cwd=OUR_RT_DIR, scope=IAM_TYPE))
    _logger.addHandler(LogHandlers.LogDataHandler(cwd=OUR_RT_DIR))
    
## Allow log handlers to not be loaded by setting an env variable
_hook_logging()


#### Now we setup the file finding
import FileTools
from FileTools import FindFileArgs, UTPFileNotFound

# Setup our find args

class UTPFileType(argparse.FileType):
    """! Wraps FileType object with Platform file finding capability.

    This class takes advantage of the file finding ability of the
    platform and allows argparse to consume the file.
    """
    def __call__(self, string):
        # We want to resolve files that are already on the filesystem
        _string = string if 'w' in self._mode else find_file(string)
        return super().__call__(_string)
"""!
Run-anywhere theory

We want to be able to run testcase from anywhere.   For instance, on our laptop, on the l1, on the UUT.
So the UTP interface needs to be robust to this situation.   We assume the following

   * for the run* functions, the assumption is these default to running on the UUT
   * for the logging functions, the assumption is these should log to a rt/ or $debug/ (peer to /rt) on
     L1.  rt/ for production mode and $debug/ for debug mode.
   * for the *_file functions, the assumpiton is the search is to take place on the L1 by default
   * variables access will be rt/variables by default
   * assume code running and importing happen from local directories only

The run, file, and variable functions will allow a scope override.  The override allows the user
to force a context like 'uut'|'l1'|'local'

In addition, the user can also specify a media= flag for run, file, and variable.

"""

def exists(*bares, **kw):
    """! Check if a path exists

    @return None if file does not exist, full path to file if it does

    @b NOTE: see find_file() for parameter definition
    Follows exact logic of find_file, only it returns a None if path is not found
    or the full path of the first match if the path is found.
    Does not throw an exception.
    """
    try:
        path = find_file(*bares, **kw)
        return path
    except UTPFileNotFound:
        return None


def mkdtemp(suffix=None, prefix=None, dir=None, scope='local'):
    """! Create a temporary, secure directory within the given scope

    @param  *      See Python stdlib tempfile.mkdtemp()
    @param  scope  'local'|'uut'|'l1'|'l2'|'l3'  default='local'
    """
    finder = _get_media_scope(scope, None)
    real_path = finder.mkdtemp(suffix, prefix, dir)
    return real_path


def rmdir(path, *, dir_fd=None, scope='local'):
    """!
    @param  *      See Python stdlib os.rmdir()
    @param  scope  'local'|'uut'|'l1'|'l2'|'l3'  default='local'
    """
    finder = _get_media_scope(scope, None)
    finder.rmdir(path, dir_fd=dir_fd)


def find_file(name, media=None, args=GENERAL_ARGS, scope='local'):
    """! Find the full and absolute path to a file

    @param  name   The name of a file to find
    @param  scope  'local'|'uut'|'l1'|'l2'|'l3'  default='local'
    @param  media  If given, it should be the MTSN name of another order (no path, just name)
                   If not given it will default to run-time dir where the program started
    @param  args   A directory structure to search.   Defaults to a very general search
                   that always checks depth first in product, common, platform order.  If
                   given, must have same attributes as UTP.FindFileArgs.

                   @b See LocalLocation.find_file()  for additional detail
    """
    finder = _get_media_scope(scope, media)
    real_path = finder.find_file(name, args)
    return real_path

def glob_file(pattern, args=RT_ARGS, scope='uut', media=None):
    """! Find any paths that match the given pattern, checking all locations

    @param  name   The name of a file to find
    @param  args   A directory structure to search.   Defaults to a search from /var/tmp
    @param  scope  'local'|'uut'|'l1'|'l2'|'l3'
    @param  media  If given, it should be the MTSN name of another order (no path, just name)
                   If not given it will default to run-time dir where the program started

                   @b See find_file() for additional detail
    """
    finder = _get_media_scope(scope, media)
    paths = finder.glob_file(pattern, args)
    return paths

def open_file(name, *, args=GENERAL_ARGS, media=None, scope='local', **kw):
    """! An object that mimics open() and calls find_file() first
    @b See find_file() for parameters
    """
    finder = _get_media_scope(scope, media)
    fh = finder.open_file(name, args=args, **kw)
    return fh

def sha1_file(name, args=GENERAL_ARGS, media=None, scope='local'):
    """!  Calls find_file() first and returns a fullpath and sha1 of the found file
    @b See find_file() for parameters

    @return full_path, sha1
    """
    finder = _get_media_scope(scope, media)
    return finder.sha1_file(name, args=args)


def unlink_file(name, args=RT_ARGS, media=None, scope='local', throw=False):
    """!  Unlinks (deletes) the file found

    Calls find_file() first to return the full path to the file and then unlinks (deletes)
    that file.  Throws same exception as UTP.find_file

    @b See find_file() for parameters
    @b Note the args parameter defauls to finding  files in the run-time directory
    """
    finder = _get_media_scope(scope, media)
    finder.unlink_file(name, args=args, throw=throw)


def variables(scope, media=None, filename='variables'):
    finder = _get_media_scope(scope, media)
    return finder.variables(filename)

def global_vars():
    """! The global variables that persist for the entire test """
    finder = _get_media_scope('l1', None)
    return finder.variables('variables')

def get_global_vars(name_spec, base_names):
    """! Get UTP global variables which matched the name spec.

    @param name_spec: regular expression pattern to match the name of global
    variable.
    @param base_names: a list of base names, only variables whose name ending
    in one of the base names returned.

    @return: a dict mapping from base name to value.

    @notes: all names performed case-insensitive matching.
    """
    g_vars = {}
    name_regex = re.compile(name_spec, re.IGNORECASE)

    for name, value in global_vars().items():
        if name_regex.search(name):
            for base_name in base_names:
                if re.search(r'(?:^|_){}$'.format(base_name), name, re.IGNORECASE):
                    assert base_name not in g_vars, \
                        'Another variable <{}> matched the name spec: {}, {}'.format(
                            name, name_spec, base_name)
                    g_vars[base_name] = value
                    break

    return g_vars

def local_vars():
    """! The global variables that persist for the entire test """
    finder = _get_media_scope('local', None)
    return finder.variables('variables')

def uut_vars():
    """! The variables that live and die with UUT reboots """
    finder = _get_media_scope('uut', None)
    return finder.variables('variables')

def get(name, default=KeyError, media=None, media_index=None, scope='local'):
    """! Retrieve a global process variable

    @param  name     Name of the variable
    @param  default  A value to return if the name does not exist.  If
                     set to KeyError, the KeyError will be raised.  This
                     is the default behavior
    @param  media    Use alternate media directory. None, means the current
                     media
    @param media_index  Index of the targeted media (None is default = OUR_RT, 0 = rt, x = rt_x)
    @param  scope  'local'|'uut'|'l1'|'l2'|'l3'  default='l1'

    @return Value of the variable.  Note that this can be any python object
    that can be stored in JSON format
    """
    finder = _get_media_scope(scope, media, media_index)
    return finder.get(name, default=default)

def increment(name, default=0, media=None, scope='local'):
    """! Increment by one the given variable name

    @param name    Variable name to increment
    @param default If name does not exist, then set to this value
                   BEFORE the increment (default=0)
    @param media   Set a variable in alternate media dir.  None meands current
    @param scope   Set variable on 'local'|'uut'|'l1'|'l2'|'l3' (default='l1')

    You can call this normally like:
    @code
    UTP.increment('blah')
    @endcode
        Or in a situation where you want the increment to happen first, but to
    roll back if there is any exception:
    @code
    with UTP.increment('blah'):
        do some stuff, that may throw exception
        maybe this block never returns (reboot/powercycles itself)
    @endcode

    In this case 'blah' is incremented upon entering the `with` code block.
    Upon exiting the code block normally, nothing happens (the incremented
    value remains).   If the block is exited due to an exception, then
    the 'blah' is decremented so that it remains unchanged.
    """
    value = int(get(name, default=0, media=media, scope=scope))
    context = KeepSetOnPass(name, value + 1, media=media, scope=scope)
    context.__enter__()
    return context

def set(name, value, media=None, scope='local', rollback=False):
    """! Set a global process variable

    @param  name   Name of the variable
    @param  value  Can be any simple python types that format as JSON
    @param  media   Use alternate media directory. None means current dir
    @param  scope  'local'|'uut'|'l1'|'l2'|'l3'  default='l1'

    Or in a situation where you want to set a value and keep it set only
    if the following block of code runs without an exception:
    @code
    with UTP.set('blah', 99, rollback=True):
        do some stuff, that may throw exception
        maybe this block never returns (reboot/powercycles itself)
    @endcode

    In this case 'blah' is first set to 99 on entering the  `with` code block.
    Upon exiting the code block normally, nothing happens (the set
    value remains).   If the block is exited due to an exception, then
    the 'blah' is restored to its original state (including not exisiting at all)
    """
    if rollback:
        return KeepSetOnPass(name, value, media=media, scope=scope)

    finder = _get_media_scope(scope, media)
    finder.set(name, value)


def delete(name, media=None, scope='local'):
    """! Delete a global process variable

    @param name Name of the variable
    @param media Do delete on alternate UUT.  None means current MTSN
    @param  scope  'local'|'uut'|'l1'|'l2'|'l3'  default='l1'
    """
    finder = _get_media_scope(scope, media)
    finder.delete(name)

def runproc(args, password=None, log_stdout=logging.DEBUG, log_stderr=True, scope='uut', media=None, **keywords):
    """! Run command and return process result
    @b See Run.runproc()
    """
    finder = _get_media_scope(scope, media)
    return finder.runproc(args, password=password, log_stdout=log_stdout, log_stderr=log_stderr, **keywords)

def runproc_rt(args, password=None, log_stdout=logging.DEBUG, log_stderr=True, scope='uut', media=None,
               stdin_msg='', timeout=None, check=True, **keywords):
    """! Run command and return process result
    @b See Run.runproc()
    """
    finder = _get_media_scope(scope, media)
    return finder.runproc_rt(args, password=password, log_stdout=log_stdout, log_stderr=log_stderr,
                             stdin_msg=stdin_msg, timeout=timeout, check=check, **keywords)

def runcmd(args, *bares, scope='uut', media=None, **keywords):
    """! Run command and return the output
    @b See PlatformABC.runcmd()
    """
    finder = _get_media_scope(scope, media)
    return finder.runcmd(args, *bares, **keywords)

run = runcmd


def runxterm(args, tail_file_name=None, xterm_params=['-geometry', '80x30+350+200', '-fg', 'black', '-bg', 'yellow'],
             **keywords):
    """! Run the command and tail the ouptut in an xterm

    Similar to runcmd(), but will open an xterm tailing the output of the command
    in real-time.

    @param tail_file_name   A name of a file to log the output.  Defaults to None, in which case a temp name will be
                            used and deleted.
    @param xterm_params     Extra parameters to send to xterm.  Do not inlclude -e parameter,  it is used for
                            tail -f command

    @b NOTE Like runcmd(), the default is to log stderr to tester.log at level ERROR.  Only stdout will be automatically logged
    to tail_file_name (and shown in xterm) by default.   If you want stderr and stdout combined, then use

    stderr=subprocess.STDOUT

    """
    ## Start an xterm tailing the tail file
    if 'env' not in keywords:
        keywords['env'] = eval(run(['python35', '-c', 'import os; print(repr(dict(os.environ)))'],
                                   scope=keywords.get('scope', 'uut'),
                                   cwd=keywords.get('cwd', None)))

    keywords['env'].setdefault('DISPLAY', ':0')
    keywords['env'].setdefault('MTSN', get_media_rt_path())

    fname = None
    xterm_proc = None

    if tail_file_name is None:
        fname = run('mktemp', scope=keywords.get('scope', 'uut'), env=keywords['env']).strip()
    else:
        path = run('pwd', scope=keywords.get('scope', 'uut'), env=keywords['env'],
                   cwd=keywords.get('cwd', None)).strip()
        fname = osp.join(path, tail_file_name)
        if not exists(fname):
            run(['touch', fname], scope=keywords.get('scope', 'uut'))
    try:
        xterm_proc = runpopen(['xterm']+ xterm_params + ['-e', 'tail', '-f', fname],
                              scope=keywords.get('scope', 'uut'), env=keywords['env'],
                              cwd=keywords.get('cwd', None))

        keywords['rt'] = True
        if 'log_stdout' in keywords:
            log_stdout = keywords['log_stdout']
            del keywords['log_stdout']
            return run(args, log_stdout=(fname, log_stdout), **keywords)
        else:
            return run(args, log_stdout=fname, **keywords)
    finally:
        if xterm_proc is not None:
            xterm_proc.kill()
            xterm_proc.communicate()
        if tail_file_name is None and fname is not None:
            unlink_file(fname, scope=keywords.get('scope', 'uut'))



def runpopen(args, *bares, scope='uut', media=None, **keywords):
    """! Run command and return the Popen object

    @b See Run.runpopen() for parameter details

    @b Note this allows scope='uut' for now
    """
    assert scope == 'local' or scope == IAM_TYPE or \
        (keywords.get('stdin', None) is None
         and keywords.get('stdout', None) is None
         and keywords.get('stderr', None) is None), \
        'For now this function will only run locally'
    finder = _get_media_scope(scope, media)
    return finder.runpopen(args, *bares, **keywords)


def get_macs(media=None):
    """! Return a list of MACs associated with an MTSN
    @return list: of 12d MAC
    """
    media = our_media()  if media is None else media
    media_path = get_media_path(media)
    if IAM_TYPE == 'l1':
        import MediaTools
        return MediaTools.get_mac_list(media_path)
    else:
        return _get_media_scope('l1', media).run_remote_function('MediaTools.get_mac_list', media_path)


def get_ip(kind='uut', media=None):
    """! Return the UUT's system IP
    @return str:  IP  or None if the MAC is not in dhcp lease or arp
    """
    media = our_media() if media is None else media
    media_path = get_media_path(media)
    return Misc.find_latest_ip(media_path, kind=kind)


def log_dictionary(subsystem, author, data, filename='config.log.zip'):
    """! Append a dictionary to compressed file 

    The dictionary is appended to any existing list and each entry includes
    timestamp, author, and subsystem

    @param subsystem  str: 'hdd', 'pci', etc
    @param author str: Name of testcase, etc
    @param data  dict: any (must be repr()'able)
    """
    # Log file is python eval'able list:
    # [ {...}, {...}, ..]
    # Each dict entry has keys():
    # timestamp', 'author', 'subsystem', 'data'

    # Don't try to lock file, instead read contents, generate new tempfile, then rename
    assert filename.endswith('.zip')
    assert pprint.isreadable(data), 'Can only pass object for data that can pass eval(repr(o))'

    base_file = filename.rsplit('.', 1)[0]

    log_list = []
    with suppress(UTPFileNotFound):
        with open_file(filename, mode='rb', scope='l1', args=RT_ARGS) as fh:
            zipf = zipfile.ZipFile(fh)
            log_list = eval(zipf.read(base_file))
            
    log_list.append({'timestamp':time.time(), 'author':author, 'subsystem':subsystem,
                     'data':data})

    temp_file = '{}.{}'.format(filename, time.time())

    with open_file(temp_file, mode='wb', scope='l1') as fh:
        zipfile.ZipFile(fh, 'w', compression=zipfile.ZIP_DEFLATED)\
               .writestr(base_file, pprint.pformat(log_list, indent=4, width=140))
        fh.flush()

    run(['mv', temp_file, filename], scope='l1')


# The directory where compiled versions will be cached is
# ~/.utp/MAGIC_NUMBER
CACHE_ROOT = osp.join(osp.expanduser('~'), '.utp', str(int.from_bytes(MAGIC_NUMBER[:2], 'little')))


class MetaPathFinder (importlib.abc.SourceLoader):
    """! Implements a meta path finder and source loader

    This object is added to sys.meta_path and will find modules
    in the UTP setting using UTP methods to find paths to files

    It also acts as a source loader.
    """

    def __init__(self):
        self._fullname_to_code = {}

    def find_spec(self, fullname, import_path, target_module=None):
        """! Finds a given module name and returns a module spec
        @note  See https://docs.python.org/3/library/importlib.html#importlib.abc.MetaPathFinder

        Our implementation uses the sha1_file() function to get a path and
        sha1 if the file can be found.   If it is found, a cache name will
        be derived from the sha1, but that does not mean the cache entry
        exists.   Instead, when the module is loaded, the cache will be
        checked and will be created as needed using the info stored in the
        spec.
        """
        if fullname in ('common', 'product', 'utp_platform'):
            return importlib.machinery.ModuleSpec(name=fullname, loader=None, is_package=True)

        # This is a work-around for namespace platform conflicting with builtin lib platform
        fullname = fullname.replace('utp_platform.', 'platform.')

        finder_args = MODULE_ARGS
        base_name = fullname
        if '.' in fullname:
            parent_name, base_name = fullname.split('.', 1)
            finder_args = FindFileArgs(topdirs=(parent_name,),
                                       middledirs=MODULE_ARGS.middledirs,
                                       bits=GENERAL_ARGS.bits,
                                       extensions=PYTHON_EXTENSIONS)

        try:
            path, sha1 = sha1_file(base_name.replace('.', os.pathsep), args=finder_args, scope='local')
        except UTPFileNotFound:
            return None

        compiled_source = osp.join(CACHE_ROOT, sha1[:2], sha1, path.replace(os.sep, '.'))
        module_spec = importlib.machinery.ModuleSpec(name=fullname, loader=self, origin=path)
        module_spec.cached = compiled_source

        return module_spec

    def get_data(self, *b, **kw):
        return None

    def get_filename(sefl, *b, **kw):
        return None

    def create_module(self, spec):
        """! Create a module for later exec

        To create a module efficiently the source has to be byte compiled
        and cached somewhere.   Rather than cache in the default
        location, this function will cache in $HOME/utp/$MAGICNUM
        and create cache names based on the sha1 of the source file content.

        @param spec   Module spec,
                      see https://docs.python.org/3/reference/import.html

        @returns Module created
        """
        if not osp.exists(spec.cached):
            # Need to compile and cache it
            with open_file(spec.origin, args=MODULE_ARGS, mode='rb', scope='local') as fh:
                content = fh.read()
            # recompute the sha1 in case the file changed since we originally
            # created the spec
            sha1 = hashlib.sha1()
            sha1.update(content)
            sha1 = sha1.hexdigest()
            compiled_source = osp.join(CACHE_ROOT, sha1[:2], sha1,
                                       spec.origin.replace(os.sep, '.'))
            # create the compiled file and rename it to make it appear
            # in an atomic way
            create_name = '{}.{}'.format(spec.cached, os.getpid())
            if not osp.exists(osp.dirname(create_name)):
                os.makedirs(osp.dirname(create_name))
            with open(create_name, 'wb') as fh:
                marshal.dump(self.source_to_code(content, spec.origin), fh)
            os.replace(create_name, compiled_source)
            spec.cached = compiled_source
        else:
            os.utime(spec.cached)  # so we can use mtime for cleanup

        self._fullname_to_code[spec.name] = spec.cached

        module_object = types.ModuleType(spec.name)
        module_object.__file__ = spec.origin

        return module_object


    def get_code(self, fullname):
        with open(self._fullname_to_code[fullname], 'rb') as fh:
            return marshal.load(fh)


def _hook_import():
    sys.meta_path.insert(0, MetaPathFinder())
    for path in list(sys.path):
        if 'dfcxact' in path or 'product/' in path or 'common/' in path \
           or 'platform/' in path:
            sys.path.remove(path)


# The UTP_HOST environment controls the type of logger
_hook_import()


# these are loaded after we hook the import
import Variable


def run_sequence(name):
    """! Run a .seq file

    @param name    The name of a sequence file. If you give a relative path, it
                   will be tried in in the standard locations.   A full path
                   may also be given.
    """
    sequence_path = find_file(name, args=SEQUENCE_ARGS, scope='local')
    os.environ['CURRENT_SEQ'] = osp.basename(sequence_path)

    from LogHandlers import TEST_LOG, ERROR_LOG
    import Sequencer

    if os.path.exists(TEST_LOG):
        os.unlink(TEST_LOG)
    if os.path.exists(ERROR_LOG):
        os.unlink(ERROR_LOG)

    sequence = Sequencer.Sequence()
    if not sequence.parse_file(sequence_path):
        sequence.print_errors()
        return 111

    rc = 122
    log_sequence_start(sequence_path)
    try:
        rc =  sequence.run()
    finally:
        log_sequence_end('PASS' if rc == 0 else 'FAIL', sequence_path)

    return rc

from Run import runmain

if __name__ == '__main__':
    logging.error('hello world')
