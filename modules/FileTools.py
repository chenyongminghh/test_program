#!/usr/local/bin/python35

import sys
import glob
import hashlib
import os
import os.path as osp
import logging
import tempfile
from collections import namedtuple

import PlatformABC
import Logging
import Default

import Fails  # this will import all Fail classes and ItemType into builtins namespace

logger = logging.getLogger(__name__)

FindFileArgs = namedtuple('FindFileArgs', ['topdirs', 'middledirs',
                                           'bits', 'extensions'])

UTPFileNotFound = FileNotSearchedFail


class LocalTools(PlatformABC.LocalABC, PlatformABC.FileToolsABC):
    def __init__(self, cwd, scope):
        self._cwd = cwd
        self._scope = scope
        self._log = Logging.Log(logger, scope)

    @property
    def scope(self):
        return self._scope

    @property
    def log(self):
        return self._log

    @property
    def cwd(self):
        return self._cwd

    @property
    def media(self):
        if self._cwd.startswith(Default.MTSN_DIR):
            return osp.split(self._cwd[len(Default.MTSN_DIR)+1:])[0]
        else:
            return None

    def mkdtemp(self, suffix, prefix, dir):
        """! Wrapper for tempfile.mkdtemp()
        """
        return tempfile.mkdtemp(suffix, prefix, dir)

    def rename_file(self, old, new):
        os.rename(old, new)

    def rmdir(self, path, *, dir_fd=None):
        """! Wrapper for os.rmdir()
        """
        return os.rmdir(path, dir_fd=None)
        
    def find_file(self, name, args):
        """! Finds a file given only the basename

        This is where the UTP standard search happens. 

        If the name starts with '/' and that path exists, then return value 
        will be be same as name.

        If not an absolute path, the search moves on.
        Each directory given by parameter topdirs, middledirs, bits, and
        extensions,  is seached in depth-first order:

        @code
        $cwd/$topdir/$middledir/$bits/$name$extension
        @endcode

        The parameters for this function are:

        @param name   Basename of a file
        @param cwd    Use this directory as the current working directory
        @param args   A FindFileArgs() or like object

        The names of the fields for FindFileArgs are given:

        @param topdirs    List of top-level directories to search
        @param middledirs List of subdirectories to search
        @param bits       List of arch subdirs 
        @param extensions A list of endings to try.  No extensions would be ['']

        @throws UTPFileNotFound
        If the given name is not found

        @return Full absolute path to file.  @b Note this means
        if you change the current working directory, the path returned
        will still refer to the @b SAME file
        """
        # If this is an absolute path that exists return it
        if name.startswith('/'):
            if osp.exists(name):
                self.log.find_file(name, name, self.media)
                return name
            else:
                self.log.find_file(name, 'NOT FOUND', self.media)
                raise UTPFileNotFound(name, [name])

        # Still not found? then start checking subdirs
        searched = []
        for top in args.topdirs:
            topdir = osp.join(self.cwd, top)
            for middle in args.middledirs:
                middle_path = osp.join(topdir, middle)
                for bit in args.bits:
                    bit_path = osp.join(middle_path, bit)
                    for ext in args.extensions:
                        searched.append(osp.join(bit_path, name + ext))
                        if osp.exists(searched[-1]):
                            real_path = osp.realpath(osp.abspath(searched[-1]))
                            self.log.find_file(name, real_path, self.media)
                            return real_path


        self.log.find_file(name, 'NOT FOUND', self.media)
        raise UTPFileNotFound(name, searched)

    def glob_file(self, pattern, args):
        """! Similar to find_file, but returns a list of file paths that
        match given pattern

        @param pattern  A shell-like pattern for matching

        @b see find_file() for other parameters

        @return  A list of matching (full) paths.  May be empty.

        Does not throw UTPFileNotFound, but may return an empty list
        """
        if pattern.startswith('/'):
            # If this an absolute path, we can just return glob
            result = glob.glob(pattern)
            logger.debug('glob result for {}: {}'.format(pattern, result))
            return result

        # Check subdirs
        found_files = {}
        for top in args.topdirs:
            topdir = osp.join(self.cwd, top)
            for middle in args.middledirs:
                middle_path = osp.join(topdir, middle)
                for bit in args.bits:
                    bit_path = osp.join(middle_path, bit)
                    for ext in args.extensions:
                        logger.debug('glob search: {}'.format(osp.join(bit_path, pattern+ext)))
                        for path in glob.glob(osp.join(bit_path, pattern+ext)):
                            found_files[osp.realpath(osp.abspath(path))] = 1
        result = list(found_files.keys())
        logger.debug('glob result for {}: {}'.format(pattern, result))
        return result


    def open_file(self, name, args, **keywords):
        """! Searches for the given name and returns an open file handle

        @param name       Basename of a file to look up
        @param mode       The mode to pass to open()
        @param keywords   other parameters passed on to find_file()

        @b see find_file() for other parameters

        @return   Open file handle for 'r'
        """
        mode = keywords.get('mode', 'r') # for mode check
        if 'mode' in keywords and any(c in mode for c in 'wxa'):
            # this is open for write, so won't attempt a search
            # because the file does not have to exist
            return open(name, **keywords)
        else:
            # The file should already exist
            return open(self.find_file(name, args), **keywords)


    def sha1_file(self, name, args):
        """! Searches for the given name and returns the full path
        and the sha1 of the content

        @b  see find_file() for parameters

        @return   path, hexdigest
        """
        path = self.find_file(name, args)

        with self.open_file(path, args, mode='rb') as fh:
            content = fh.read()

        sha1 = hashlib.sha1()
        sha1.update(content)

        result = (path, sha1.hexdigest())
        return result


    def unlink_file(self, name, args, throw=False):
        """! Searches for the given name and deletes the first found

        @b  see find_file() for parameters
        """
        try:
            path = self.find_file(name, args)
        except UTPFileNotFound:
            if throw:
                raise
            return
        
        os.unlink(path)
        self.log.unlink_file(path)

    def close(self):
        pass

