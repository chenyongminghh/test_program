#!/usr/local/bin/python35
## A disk-backed persistant variable store
#
#  Variables are stored as $name=$value
#  Where $name and $value are guaranteed to not have a newline embedded
#  $name is string and limited to [_.a-Z0-9] (ialphanumerics and 
#  and '.', '_')
#
#  The $value is a JSON encoded value
#
#  The default file name to use is 'variables'
#  The $name/$values will be cached as a dicitonary
#  An exclusive flock is used when writing the dicitonary back to file
#  and a shared lock is used whne reloading the dictionary
#  The dictionary cached if validated with the file mtime
import os
import os.path as osp
import re
import json
import time
import collections
from errno import EACCES, EAGAIN
from contextlib import suppress

from Fails import *
from FileLock import FileLock
from Helper import readvars


KEY_RE = re.compile('^[_.a-zA-Z0-9]+$')


class FileBackedVariables(collections.MutableMapping):
    def __init__(self, filename='variables', mode='r+', flock_block_on_read=True):
        super().__init__()
        self.mtime = 0
        self.filename = filename
        self.flock_block_on_read = flock_block_on_read
        self.cache = {}
        if not osp.exists(filename):
            if mode == 'r':
                raise FileNotFoundFail(filename)
            # 'touch' a file 
            try:
                with open(filename, 'x') as fh:
                    pass
                os.chmod(filename, 0o0666)
            except:
                pass

        self.fh = open(filename, mode)
        self._reload_cache()

    def close(self):
        self.fh.close()

    def _load_cache(self, fh):
        """! Only call under filelock """
        self.cache = readvars(fh)
        self.mtime = os.stat(fh.fileno()).st_mtime

    def _write_cache(self):
        """! Only call under filelock """
        self.cache['zzzz_lastwrite'] = [time.time(), time.asctime()]
        self.fh.seek(0)
        for k in sorted(self.cache.keys()):
            self.fh.write('{} = {}\n'.format(k, json.dumps(self.cache[k], sort_keys=True)))
        self.fh.truncate()

        self.mtime = os.stat(self.fh.fileno()).st_mtime

    def _reload_cache(self):
        try:
            fh = None
            with FileLock(self.fh, shared=True, do_not_block=not self.flock_block_on_read):
                if os.stat(self.fh.fileno()).st_mtime == self.mtime:
                    return  # mtime is okay
                # mtime has changed,reload cache

                ## call _load_cache with a new file handle.  We have seen a problem on NFS where if you 
                ## use the already open file handle (self.fh) and block waiting on the lock, 
                ## then get the lock and read, you can catch the file writes in transition, which should not
                ## happen.

                # Note that the lockf-type lock that FileLock uses is strange.  If you open another file
                # handle to same file and close it, this process will release the lock, so we need to 
                # close the fh outside this 'with lock' blokc
                fh = open(self.filename)
                self._load_cache(fh)
        except OSError as e:
            if e.errno not in (EACCES, EAGAIN):
                raise
        if fh is not None:
            fh.close()

    def __getitem__(self, key):
        self._reload_cache()
        return self.cache.__getitem__(key)


    def __contains__(self, key):
        self._reload_cache()
        return self.cache.__contains__(key)


    def __iter__(self):
        self._reload_cache()
        return self.cache.__iter__()

    def __enter__(self):
        return self

    def __exit__(self, *b, **kw):
        self.close()
    
    def keys(self):
        # Seem to need to override this one to make certain corner-case remote access work
        self._reload_cache()
        return self.cache.keys()


    def __setitem__(self, key, value):
        assert KEY_RE.match(key), 'Names must be alphanum or "_" or ".": illegal: <{}>'.format(key)
        with FileLock(self.fh):
            if os.stat(self.fh.fileno()).st_mtime != self.mtime:
                self._load_cache(self.fh)

            self.cache[key] = value
            self._write_cache()


    def __delitem__(self, key):
        with FileLock(self.fh):
            if os.stat(self.fh.fileno()).st_mtime != self.mtime:
                self._load_cache(self.fh)

            del self.cache[key]
            self._write_cache()

    def __len__(self):
        return self.cache.__len__()

    def __repr__(self):
        return self.cache.__repr__()


if __name__ == '__main__':
    import sys

    v = FileBackedVariables()

    if len(sys.argv) == 1:
        for key in sorted(v.keys()):
            print('{:30} {}'.format(key, json.dumps(v[key])))
    elif len(sys.argv) == 2:
        print(v[sys.argv[1]])
    elif len(sys.argv) == 3:
        if sys.argv[2].startswith('j:'):
            value = json.loads(sys.argv[2][2:])
        else:
            value = sys.argv[2]
        v[sys.argv[1]] = value
    else:
        print('Usage: {}'.format(sys.argv[0]))
        print('Usage: {} NAME'.format(sys.argv[0]))
        print('Usage: {} NAME VALUE'.format(sys.argv[0]))
        print('Usage: {} NAME j:VALUE'.format(sys.argv[0]))
        exit(1)
