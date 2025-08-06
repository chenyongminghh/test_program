#!/usr/local/bin/python35
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
import logging
import os.path as osp
import copy
import json
import subprocess
from abc import ABC, abstractmethod

import Logging

import Fails  # this will import all Fail classes and ItemType into builtins namespace

logger = logging.getLogger(__name__)

class RunCommandError(Exception): pass

class UTPVariableNotSet(InfoFail):
    """! Raised when variable is not set
    """

    def __init__(self, name):
        super().__init__('UTP variable - {name} not set', name=name)

class LocalABC(ABC):
    @property
    @abstractmethod
    def cwd(self):
        pass

    @property
    @abstractmethod
    def media(self):
        pass


class ScopedABC(ABC):
    @property
    @abstractmethod
    def scope(self):
        pass


class LoggedScopedABC(ScopedABC):
    @property
    @abstractmethod
    def log(self):
        pass
    

class RemoteFunctionABC(LoggedScopedABC):
    @property
    @abstractmethod
    def run_remote_function(self, func, *bares, **keywords):
        pass


class RunABC(LoggedScopedABC):
    @abstractmethod
    def runproc(self, args, password=None, *bares, **keywords):
        pass

    @abstractmethod
    def runproc_rt(self, args, password=None, *bares, **keywords):
        pass


    def runcmd(self, args, *bares, **keywords):
        """!  Have the platform run a command and return output

        @see Run.runproc()

        If not given as keywords, the following parameters are set to these default values:
        @param stdout             subprocess.PIPE
        @param stderr             subprocess.PIPE
        @param check              True
        @param universal_newlines True

        You may call with any of these set to a value.   For instances stdout=None will log
        to the current stdout instead of log.   stderr=subprocess.STDOUT will
        force all stdout and stderr to be mixed in the return string.
        
        universal_newlines=False will cause a byte array to returned instead of a string

        @return   The command's stdout
        """
        kw_copy = keywords.copy()
        if 'stdout' not in kw_copy:
            kw_copy['stdout']= subprocess.PIPE
        if 'stderr' not in kw_copy:
            kw_copy['stderr'] = subprocess.PIPE
        if 'check' not in keywords:
            kw_copy['check'] = True
        if 'universal_newlines' not in keywords:
            kw_copy['universal_newlines'] = True
        if 'rt' in keywords:
            do_rt = keywords['rt']
            del kw_copy['rt']
        else:
            do_rt = False

        if do_rt:
            completed_proc = self.runproc_rt(args, *bares, **kw_copy)
        else:
            completed_proc = self.runproc(args, *bares, **kw_copy)
            

        return completed_proc.stdout

    ## UTP.run(...) is natural method folks will use instinctively
    run = runcmd


class VariablesABC(LoggedScopedABC):
    @abstractmethod
    def variables(self, filename):
        pass
    
    def get(self, name, default=KeyError):
        try:
            value = self.variables(osp.join(self.cwd, 'variables'))[name]
        except KeyError:
            if default == KeyError:
                self.log.variable('GET', name, Logging.NOTSET, media=self.media)
                raise
            else:
                self.log.variable('GET', name, Logging.NOTSET_DEFAULT.format(json.dumps(default)), media=self.media)
                return default
        else:
            self.log.variable('GET', name, value, media=self.media)
            # return a deep copy so we don't get any spooky action at a distance
            return copy.deepcopy(value)

        raise UTPVariableNotSet(name)

    def set(self, name, value):
        self.variables(osp.join(self.cwd, 'variables'))[name] = value
        self.log.variable('SET', name, value, media=self.media)


    def delete(self, name):
        try:
            del self.variables(osp.join(self.cwd, 'variables'))[name]
            self.log.variable('DEL', name, '', media=self.media)
        except KeyError:
            pass


class FileToolsABC(LoggedScopedABC):
    @abstractmethod
    def find_file(self, name, args):
        pass

    @abstractmethod
    def glob_file(self, name, args):
        pass

    @abstractmethod
    def open_file(self, name, args):
        pass
        
    @abstractmethod
    def sha1_file(self, name, args):
        pass

    @abstractmethod
    def mkdtemp(self, suffix, prefix, dir):
        pass

    @abstractmethod
    def rmdir(self, path, dir_fd):
        pass


class PlatformABC(LocalABC, RunABC, VariablesABC, FileToolsABC): 
    pass
