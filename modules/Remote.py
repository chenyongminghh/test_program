#!/usr/local/bin/python35
import traceback
import logging

logger = logging.getLogger(__name__)

import gc
import os
import pickle
import struct
import time
import os.path as osp
import subprocess
import collections
import select
import threading
import functools
from abc import ABC, abstractmethod

import Fails  # this will import all Fail classes and ItemType into builtins namespace


HELPER_PROGRAM = osp.join(osp.dirname(osp.dirname(__file__)), 'utilities', 'remote_helper_pickle.py')
BOOTSTRAP_COMMAND =  '/usr/local/bin/python35 -u -c"import sys,struct,pickle,os; exec(pickle.loads(sys.stdin.buffer.read(struct.unpack(\'!L\', sys.stdin.buffer.read(4))[0])))"'


# Need _Instance so execfile
with open(HELPER_PROGRAM) as fh:
    exec(compile(fh.read(), HELPER_PROGRAM, 'exec'))

# The helper will have _Instance defined as attribute to module __main__, so
# to keep pickle happy we load it there too
sys.modules['__main__']._Instance = _Instance

L_SIZE = struct.Struct('!L').size

class ShortOutputError(RuntimeFail):
    def __init__(self, item, msg, errs):
        super().__init__(item, msg, errs=errs)

class RemoteException(Exception):
    def __repr__(self):
        return 'RemoteException{!r}'.format(self.args)
    def __str__(self):
        return self.args[1] + str(self.args[0])
    
def _callit(self, func, what, *bares, **kw):
    return func(self, what)(*bares, **kw)


class RemoteInstance:
    def __new__(cls, remote, instance):
        """! A RemoteInstance is a proxy to a real instance created on the target.

        As such, it needs to morph into a class that looks like the real instance.
        The underlying python logic won't assume a __func__ is defined unless it is
        at the class level.   It is not enough to add these functions as attributes
        to the instance.   Python will look for something like __enter__ and if not
        found as part of the class, it will throw an AttributeError (or TypeError?).
        
        To get around this, we will use the __new__ method to create new class
        methods.
        """
        for callfunc in instance.callables:
#            if callfunc in ('__getattribute__', '__call__', '__class__', '__new__',
#                            '__init__', '__setattr__', '__del__', '__exit__'):
            
            if callfunc in ('__getattribute__', '__class__',  '__setattr__'):
                continue

            if hasattr(cls, callfunc):
                continue 

            setattr(cls, callfunc, functools.partialmethod(_callit, cls.__getattr__, callfunc))

        #Tweak name for easier debug
        cls.__name__ = '<remote> {}'.format(instance.name)

        return super().__new__(cls)

    def __init__(self, remote, instance):
        self._ri_instance = instance
        self._ri_thread_id = threading.get_ident()
        self._ri_remote = remote

    def __getattr__(self, name):
        if name not in self._ri_instance.attributes + self._ri_instance.callables:
            raise AttributeError('Remote object {} does not have attribute {}'.format(self._ri_instance.name, name))
        assert self._ri_thread_id == threading.get_ident()
        return self._ri_remote.getattr(self, name)
   
    def __call__(self, *bares, **kw):
        if '__call__' not in self._ri_instance.callables:
            raise TypeError('<remote> {} not callable'.format(self._ri_instance.name))
        return self._ri_remote.call_instance(self, *bares, **kw)

    def __exit__(self, exc_class, exc_instance, exc_tb):
        if '__exit__' not in self._ri_instance.callables:
            raise AttributeError('<remote> {} lacks __exit__ method'.format(self._ri_instance.name))

        # tb does not pickle so just send a None instead
        return self.__getattr__('__exit__')(exc_class, exc_instance, None)

    def __bool__(self):
        ## We should not have to implement this.  We should let it pass thru to remote object
        ## However we have a strange case where doing 'not obj' sometimes calls __len__ which, 
        ## if not defined, results in an AttributeError.  According to the documentation, if the __bool__ 
        ## and __len__ are not defined, python should assume True.   This would imply that if an
        ## ask for __len__ is yielding an AttributeError, that it should absorb the AttributeError 
        ## and assume this object is True, however, the AttributeError, instead, is allowed to surface.
        if '__bool__' in self._ri_instance.callables:
            return self.__getattr__('__bool__')()
        elif '__len__' in self._ri_instance.callables:
            return self.__getattr__('__len__')() != 0
        return True

    def __del__(self):
        ## Normally I *hate* __del__ because you can never depend on other objects being around.
        ## see: https://docs.python.org/3/reference/datamodel.html#object.__del__
        ## However, going against my own rule, I use __del__ here to clean up the remote side
        ## instances.  As long as the this object is just getting gc'ed during the normal flow
        ## of a program it should work because the _ri_remote will stil be there. It's only
        ## at the exit of the program that things fall apart and therefore, we have to catch
        ## and smother the exceptions because there is nothing we can do.  I think, in the sum,
        ## this okay because if this program is exiting then the remote helper will be 
        ## going away too, so remote cleanup is moot.
        try:
            self._ri_remote.delete_instance(self._ri_instance.uid)
        except:
            pass #for reasons so well stated above

def read_any(fh,timeout=0):
    buffer = ''
    while 1:
        rout = select.select([fh.fileno()], [], [], timeout)[0]
        if rout:
            msg = os.read(fh.fileno(), 1024)
            if not msg:
                return buffer
            buffer += msg.decode()
        else:
            return buffer


# Helper functions
def pickle_read(stdout, stderr):
    """! Read one pickle object from stdout

    Read stderr and raises a ShortOutputError if the expected number of bytes cannot be read
    """
    # first read any error chars
    err = read_any(stderr)

    while 1:
        # now read stdout which should always be formatted
        msg  = stdout.read(L_SIZE)

        if len(msg) != L_SIZE:
            raise ShortOutputError(ItemType.data, 'Possible error with helper', err + read_any(stderr))
        length = struct.unpack('!L', msg)[0]

        msg = stdout.read(length)

        if not msg or len(msg) != length:
            raise ShortOutputError(ItemType.data, 'Possible error with helper', err + read_any(stderr))

        what, result = pickle.loads(msg)

        err  += read_any(stderr)

#debug        print('ERR', err)
        if what == 'r':
            return result, err
        elif what == 'e':
            # any other error ?
            e, tb = result
            try:
                e.tb = err + '\n' + tb
            except:
                pass
            raise e
        elif what == 'l':
            logger.handle(result)
        else:
            raise RuntimeFail(ItemType.data, 'Not a valid result!: ({what!r}, {result!r})', what=what, result=result)

def pickle_write(stdin, o):
    """! Pickle and send one object on stdin"""
    pickle_o = pickle.dumps(o)
    stdin.write(struct.pack('!L', len(pickle_o)))
    stdin.write(pickle_o)
    stdin.flush()


def ssh_process(ip, cwd, port=22, user=None, ssh_cmd='/usr/bin/ssh', env=None):
    port = int(port)
    user_cmd = ['-l', user] if user else []

    for wait in (0, 1, 10, 100):
        time.sleep(wait)
        proc = subprocess.Popen([ssh_cmd, '-p', str(port), '-T'] + user_cmd + [ ip, BOOTSTRAP_COMMAND],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, env=env)

        with open(HELPER_PROGRAM) as fh:
            # Check the initial connection and send the helper prog
            try:
                pickle_write(proc.stdin, fh.read())
                    
                result, err = pickle_read(proc.stdout, proc.stderr)
                assert result  == None, 'helper did not load:\nstderr -begin-\n{}\nstderr -end-'.format(err)
                break
            except ShortOutputError as e:
                logger.warning('ssh command failed: {}'.format(e.errs))
    else:
        raise RuntimeFail(ItemType.ssh, 'Tried 4 times to start ssh to {host} but failed', host=ip)

    pickle_write(proc.stdin, ('call', 'os.chdir', (cwd, ), {}))
    result, err = pickle_read(proc.stdout, proc.stderr)
    assert result == None, err
    
    pickle_write(proc.stdin, ('call', 'os.getcwd', (), {}))
    result, err = pickle_read(proc.stdout, proc.stderr)
    return proc


        

class RemoteControl:
    def __init__(self, proc):
        """! Create a proxy or controller for objects running at the end of pipe/socket-ish thing

        @param proc  A process object. 

        proc can be a subprocess.Popen() object or 
        any object that has the following attributes and methods:

        @code
        .stdin          A file-like object that supports a filehandle-like .write() method
        .stdout         A file-like object that supports a filehandle-like .readline() .readlines() methods
        .stderr         A file-like object that supports a filehandle-like .read() methods
        .poll()         A method that does not block.  Returns None if the process is still running, something
                        other than None if it has exited
        @endcode

        The stdin/out/err should be attached to python3.5 running HELPER_PROGRAM. 

        Use functions such as Remote.ssh_process() to generate ready-to-use proc objects
        """
        self.proc = proc
        self.error_stream = ''
        self._thread_id = threading.get_ident()

    def _read(self):
        self.proc.stdin.flush()  # make sure the stdin is flushed
        result, err = pickle_read(self.proc.stdout, self.proc.stderr)
        self.error_stream += err
        if isinstance(result, _Instance):
            result = RemoteInstance(self, result)
        return result

    def _write(self, o):
        assert self._thread_id == threading.get_ident()
        pickle_write(self.proc.stdin, o)
        self.proc.stdin.flush()

    def _write_read(self, obj):
        ## The gc.disable()/enable() was a nasty bug fix
        ## I added the above _thread_id assert to ensure these functions never got called outside one thread
        ## This allowed me to make a very simple call/result interface, with no locking necessary.   Or so I thought.
        ## The system works well as long as NOTHING can preempt or inject charaters into the socket between or 
        ## during the _write and the _read call.
        ## So here is where I got caught.  See my comments on __del__ above  on why I hate 
        ## implementing  __del__.  Now I have another reason.  Note in my implementation of __del__ I also 
        ## make a _write_read() call?   Well image this:
        ##   - program calls make_instance, do_import, any of the normal remote calls below
        ##   - method calls _write to write an object to the socket
        ##   - you have bad luck and python decides to gc (this can happen between the _write() and _read())
        ##   - gc runs and tags some objects for delete
        ##   - these objects trigger this objects __del__ method 
        ##   - __del__ calls _write()  --> now you have two _write objects written to the socket (normal, __del__)
        ##   - __del__ calls _read() --> meanwhile remote on the other end is none the wiser and responds normally to
        ##                               the normal object and puts a response object in the socket.  The __del__
        ##                               _read() now consumes the wrong response object... it doesn't care 
        ##   - program resumes
        ##   - now the original _read() happens --> now  it reads the remaing response for __del__ call which is None
        ##   - programmer pulls out clumps of hair wondering why None gets returned by a function that should
        ##     NEVER return None.   It's random, it's confusing, and now I have another reason to hate __del__,
        ##     yet in this case I think we need to keep the remote objects trimmed so it's a necessary evil.
        ## It's a bit kludgy but appears to work.  We disable gc until the write/read cycle is complete.
        gc.disable()
        try:
            self._write(obj)
            return self._read()
        finally:
            gc.enable()
        

    def do_import(self, content, name, path):
        assert self._write_read(['import', content, name, path]) == None

    def make_instance(self, what, *bares, **kw):
        return self._write_read(['instance', what, bares, kw])

    def delete_instance(self, uid):
        return self._write_read(['delete_instance', uid])

    def call(self, what, *bares, **kw):
        return self._write_read(['call', what, bares, kw])

    def eval(self, *bares):
        return self._write_read(['eval'] + list(bares))

    def exec(self, *bares):
        assert self._write_read(['exec'] + list(bares)) == None

    def enable_logging(self, name, level='INFO'):
        assert self._write_read(['enable_remote_logging', name, level]) == None
        
    def getattr(self, remote_obj, name):
        assert isinstance(remote_obj, RemoteInstance)
        return self._write_read(['__getattr__', remote_obj._ri_instance.uid, name])

    def call_instance(self, remote_obj, *bares, **kw):
        assert isinstance(remote_obj, RemoteInstance)
        return self._write_read(['call_instance', remote_obj._ri_instance.uid,  bares, kw])

    
if __name__ == '__main__':
    import sys
    import IAm
    
    my_type = IAm.on_type()


    logging.getLogger().setLevel(os.environ.get('UTP_LOG_LEVEL', 'DEBUG'))    
    logging.basicConfig(format='{scope:10s} {message}', style='{')

    remote = RemoteControl(ssh_process('192.168.11.20', cwd='.', user='root'))
        
#    remote.enable_logging('uut', 'DEBUG')


    logging.info('start')

    remote.eval('logging.info("hello")')
    

    for module in ('FileLock', 'Fails', 'Helper', 'Logging', 'PlatformABC', 'Variable', 'Default', 'FileTools', 'Run', 'Remote', 'IAm'):
        fname = osp.join('./platform', 'modules', module + '.py')
        with open(fname) as fh:
            remote.do_import(fh.read(), module, fname)

    o = remote.make_instance('Variable.FileBackedVariables', '/var/run/variables')

    ft = remote.make_instance('FileTools.LocalTools', '.')

    remote.eval('logging.info("hello2")')
    

    #o['bla']

    logging.info(o.get('blah'))

    
    o['blah'] =  sys.argv[1]

    for i in range(10):
        logging.info(o.get('blah'))

    o = remote.eval('Variable.KEY_RE')
    logging.info(o)


    logging.info(remote.call_method(ft, 'find_file', '/var/tmp', args=None))

    remote.exec('def x(): logging.debug("hello xxxx")')

    logging.info(remote.call('x'))

    logging.info('Starting run test')
    proc = remote.call('Run.runproc', 'ifconfig', stdout=subprocess.PIPE)

    logging.info('rc={}'.format(proc.returncode))

    remote_log = remote.make_instance('logging.getLogger')

    class RemoteHandler(logging.Handler):
        def emit(self, record):
            remote_log.handle(record)

    logging.getLogger().addHandler(RemoteHandler())

    logging.getLogger('blahblah').info("here is a log from L1")

    remote.exec('')
    logging.error(remote.error_stream)

#    remote.exec('xxxx')
        
