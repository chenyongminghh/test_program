#!/usr/local/bin/python35
import sys
import os
import subprocess
import logging
import errno
import time
import select

import Logging

import Fails  # this will import all Fail classes and ItemType into builtins namespace

logger = logging.getLogger(__name__)

class LogFile:
    def __init__(self, fh, name, is_bytes, level=logging.DEBUG, cmd=None):
        self.fh = fh
        self.log_fh = open(name, 'ab')
        self.is_bytes = is_bytes
        self.buffer = b''
        self.name = name
        self.level = level
        self.cmd = cmd
        self.incomplete = b''

    def log(self):
        msg = os.read(self.fh.fileno(), 1024)
        self.buffer += msg
        if not self.is_bytes:
            self.log_fh.write(msg.decode(errors='replace').encode())
        else:
            self.log_fh.write(msg)
        self.log_fh.flush()
        self.incomplete += msg
        while b'\n' in self.incomplete:
            line, self.incomplete = self.incomplete.split(b'\n', 1)
            logger.log(self.level, '{}{}'.format('' if self.cmd == None else '<{}> '.format(self.cmd), 
                                                 line.decode(errors='replace')))

        return len(msg)
        
    def fileno(self):
        return self.fh.fileno()

    def close(self):
        self.log_fh.close()

    def get(self):
        if self.is_bytes:
            return self.buffer
        return self.buffer.decode(errors='replace')


class LogLog:
    def __init__(self, fh, cmd, level, is_bytes):
        self.fh = fh
        self.cmd = cmd
        self.level = level
        self.is_bytes = is_bytes
        self.buffer = b''
        self.incomplete = b''

    def log(self):
        msg = os.read(self.fh.fileno(), 1024)
        self.buffer += msg
        self.incomplete += msg
        while b'\n' in self.incomplete:
            line, self.incomplete = self.incomplete.split(b'\n', 1)
            logger.log(self.level, '<{}> {}'.format(self.cmd, line.decode(errors='replace')))
        return len(msg)
        
    def fileno(self):
        return self.fh.fileno()

    def get(self):
        if self.is_bytes:
            return self.buffer
        return self.buffer.decode(errors='replace')

    def close(self):
        if self.incomplete:
            logger.log(self.level, '<{}> {}'.format(self.cmd, self.incomplete))


def runproc(args, password=None, log_stdout=logging.DEBUG, log_stderr=True, **keywords):
    """!  Run a command and return the results

    The command will run in the current directory unless the
    media parameter is not None. If media=MTSN and MTSN is not None and valid,
    it will run in the context of the other MTSN/rt.  When the command runs,
    the stdout will be logged at DEBUG level, and the stderr at ERROR level.

    If the command itself uses UTP for logging and the call is in the
    current rt/ (local call) then consider setting log_stdout=False and
    stderr=False avoid double entries in the local logs.

    @param args     Same as subprocess run parameter [https://docs.python.org/3/library/subprocess.html#subprocess.run]
    @param password If the command does an 'ssh-style' prompt for password, the given password will be used
    @param timeout  If not None the command will be killed after the given number of seconds if still running
    @param log_stdout Defaults to logging.DEBUG. Set to a logging Level described in Logging.py to log output to tester.log
                      Output will always be logged if UTP_LOG_LEVEL or logging.setLevel is lowered to logging.DEBUG.
    @param log_stderr Defaults to True. Set to False to avoid saving the
                      stderr to log.
    @param **keywords  Additional keywords are passed as-is to
                       subprocess.run [https://docs.python.org/3/library/subprocess.html#subprocess.Popen]

    @b NOTE the stderr=stdout=subprocess.PIPE is set by default.
    If you don't like this behavior call with stdout=None, stderr=None

    @return subprocess.CompletedProcess
    """
    if not log_stdout:
        log_stdout = logging.DEBUG

    assert logging.DEBUG <= log_stdout <= logging.CRITICAL, '`log_stdout` level must be in between DEBUG and CRITICAL'

    logger.log(log_stdout, 'Running command: {!r}'.format(args))
    if 'stdout' not in keywords:
        keywords['stdout'] = subprocess.PIPE

    if 'stderr' not in keywords:
        keywords['stderr'] = subprocess.PIPE

    cmd = args.split(None,1)[0] if isinstance(args, str) else args[0]

    try:
        proc = subprocess.run(args, **keywords)
    except subprocess.SubprocessError as e:
        # Make sure we log the stdout, error
        if hasattr(e, 'stdout') and e.stdout and log_stdout:
            if not keywords.get('universal_newlines', False):
                output = e.stdout.decode(errors='replace')
            else:
                output = e.stdout

            for l in output.splitlines():
                logger.log(log_stdout, '<{}> {}'.format(cmd, l))

        if hasattr(e, 'stderr') and e.stderr and log_stderr:
            if not keywords.get('universal_newlines', False):
                errput = e.stderr.decode(errors='replace')
            else:
                errput = e.stderr

            for l in errput.splitlines():
                logger.error('<{}> {}'.format(cmd, l))
        # now re-raise
        raise
    except OSError as e:
        if e.errno == errno.ENOEXEC:
            logger.error('subprocess.run cannot execute the command\n{}'.format(args))
            logger.error('This is likely due to a problem with the executable format')
            logger.error('Most often, a script with no #! at the beginning can cause this error')
            logger.error("Try adding 'bash' or 'sh' as first arg to fix this problem")
        raise

    except:
        logger.error('subprocess.run has raised an unexpected error for command')
        logger.error(args)
        raise

    if proc.stdout and log_stdout:
        if not keywords.get('universal_newlines', False):
            output = proc.stdout.decode(errors='replace')
        else:
            output = proc.stdout

        for l in output.splitlines():
            logger.log(log_stdout, '<{}> {}'.format(cmd, l))

    if proc.stderr and log_stderr:
        if not keywords.get('universal_newlines', False):
            errput = proc.stderr.decode(errors='replace')
        else:
            errput = proc.stderr

        for l in errput.splitlines():
            logger.error('<{}> {}'.format(cmd, l))

    logger.log(log_stdout, '{!r} RC={}'.format(args, proc.returncode))
    return proc


def runproc_rt(args, password=None, log_stdout=logging.DEBUG, log_stderr=True, stdin_msg='', timeout=None, 
            check=True, **keywords):
    """!  Run a command and return the results

    The command will run in the current directory unless the
    media parameter is not None. If media=MTSN and MTSN is not None and valid,
    it will run in the context of the other MTSN/rt.  When the command runs,
    the stdout will be logged at DEBUG level, and the stderr at ERROR level.

    If the command itself uses UTP for logging and the call is in the
    current rt/ (local call) then consider setting log_stdout=False and
    stderr=False avoid double entries in the local logs.

    @param args     Same as subprocess run parameter [https://docs.python.org/3/library/subprocess.html#subprocess.run]
    @param password If the command does an 'ssh-style' prompt for password, the given password will be used
    @param log_stdout Defaults to logging.DEBUG. Set to a logging.LEVEL described in Logging.py to log 
                      output to tester.log (Normally, only INFO level and above is written)
                      Output will always be logged if UTP_LOG_LEVEL or logging.setLevel is lowered to logging.DEBUG.
                      Can also set to a string which will be treated as a file to be
                      opened with 'a' and any stdout from the command will be immediately written
    @param log_stderr Defaults to True. Set to False to avoid saving the
                      stderr to log.  Can also set to a string which will be treated as a file to be
                      opened with 'a' and any stdout from the command will be immediately written
    @param stdin_msg  A string which default to '' to pass to stdin.   stdin=PIPE will automatically be set
    @param timeout    Number of seconds to wait until the command is killed and subprocess.TimeoutExpired is returnted
    @param check      If True and return code is non-zero, will raise subprocess.CalledProcessError
    @param **keywords  Additional keywords are passed as-is to
                       subprocess.run [https://docs.python.org/3/library/subprocess.html#subprocess.Popen]

    @b NOTE the stderr=stdout=subprocess.PIPE is set by default.
    If you don't like this behavior call with stdout=None, stderr=None

    @return subprocess.CompletedProcess
    """
    cmd = args.split(None,1)[0] if isinstance(args, str) else args[0]
    
    def _to_bytes(buff):
        if isinstance(buff, str):
            return buff.encode()
        return buff
    
    if stdin_msg:
        keywords['stdin'] = subprocess.PIPE
        assert isinstance(stdin_msg, (str, bytes))
        stdin_msg = _to_bytes(stdin_msg)

    if log_stderr is True:
        log_stderr = logging.ERROR

    logger.debug('Running command: {!r}'.format(args))

    if 'stdout' not in keywords:
        keywords['stdout'] = subprocess.PIPE

    if 'stderr' not in keywords:
        keywords['stderr'] = subprocess.PIPE

    olog = None
    elog = None
    try:
        proc = subprocess.Popen(args, **keywords)

        rin = []
        if keywords.get('stdout') == subprocess.PIPE:
            if isinstance(log_stdout, str):
                olog = LogFile(proc.stdout, name=log_stdout, is_bytes=not keywords.get('universal_newlines'),
                               cmd=cmd)
            elif isinstance(log_stdout, tuple):
                olog = LogFile(proc.stdout, name=log_stdout[0], level=log_stdout[1], 
                               is_bytes=not keywords.get('universal_newlines'), cmd=cmd)
            elif isinstance(log_stdout, int):
                assert logging.DEBUG <= log_stdout <= logging.CRITICAL, '`log_stdout` level must be in between DEBUG and CRITICAL'
                olog = LogLog(proc.stdout, cmd=cmd, level=log_stdout, is_bytes=not keywords.get('universal_newlines'))
            else:
                olog = LogFile(proc.stdout, name='/dev/null', is_bytes=keywords.get('universal_newlines'),
                               cmd=cmd)
            rin.append(olog)

        if keywords.get('stderr') == subprocess.PIPE:
            if isinstance(log_stderr, str):
                elog = LogFile(proc.stderr, name=log_stderr, is_bytes=keywords.get('universal_newlines'))
            elif isinstance(log_stderr, int):
                assert logging.DEBUG <= log_stderr <= logging.CRITICAL, '`log_stderr` level must be in between DEBUG and CRITICAL'
                elog = LogLog(proc.stderr, cmd=cmd, level=log_stderr, is_bytes=keywords.get('universal_newlines'))
            else:
                elog = LogFile(proc.stderr, name='/dev/null', is_bytes=keywords.get('universal_newlines'))
            rin.append(elog)

        win = []
        if keywords.get('stdin') == subprocess.PIPE:
            win.append(proc.stdin)

        end_time = time.time() + timeout if timeout is not None else 2**32 
        while rin or win:
            remaining_time = end_time - time.time() 
            if remaining_time <= 0:
                for fh in rin + win:
                    fh.close()
                raise subprocess.TimeoutExpired(args, timeout, output=olog.get() if olog else None, 
                                                stderr=elog.get() if elog else None)

            rout, wout, eout = select.select(rin, win if stdin_msg else [], [], remaining_time)

            for rh in rout:
                n = rh.log()
                if not n:
                    rin.remove(rh)

            for wh in wout:
                n = os.write(wh.fileno(), stdin_msg)
                stdin_msg = stdin_msg[n:]
                if not n or not stdin_msg:
                    win.remove(wh)
                    wh.close()
                    continue

        # we are here because all file handles are closed
        rc = proc.wait(max(end_time - time.time(), 0))

    except OSError as e:
        if e.errno == errno.ENOEXEC:
            logger.error('subprocess.run cannot execute the command\n{}'.format(args))
            logger.error('This is likely due to a problem with the executable format')
            logger.error('Most often, a script with no #! at the beginning can cause this error')
            logger.error("Try adding 'bash' or 'sh' as first arg to fix this problem")
        raise

    except:
        logger.error('subprocess.run has raised an unexpected error for command')
        logger.error(args)
        raise
    finally:
        for log in (elog, olog):
            if log:
                log.close()

    logger.debug('{!r} RC={}'.format(args, rc))
    
    if check and rc:
        raise subprocess.CalledProcessError(rc, args, output=olog.get() if olog else None, 
                                            stderr=elog.get() if elog else None)

    return subprocess.CompletedProcess(args, rc, stdout=olog.get() if olog else None, 
                                       stderr=elog.get() if elog else None)



def runpopen(args, password=None, **keywords):
    """!  Run a command and return a Popen() object

    The command will run in the current directory unless the
    media parameter is not None. If media=MTSN and MTSN is not None and valid,
    it will run in the context of the other MTSN/rt.

    @param args     Same as subprocess run parameter [https://docs.python.org/3/library/subprocess.html#subprocess.run]
    @param password If the command does an 'ssh-style' prompt for password, the given password will be used
    @param **keywords  Additional keywords are passed as-is to
                       subprocess.run [https://docs.python.org/3/library/subprocess.html#subprocess.Popen]

    @b NOTE Only the args will be logged, stdout and stderr logging will be up to the caller

    @return subprocess.Popen
    """
    logger.debug('Running command: {}'.format(args))
    return subprocess.Popen(args, **keywords)


def runmain(func, *bares, **keywords):
    """! Wrap another function call with handy exception handler

    Use this function to call any main() running under the platform
    Will try/except around the call and log any excepitons and
    handle test exit with 0 (no fail) or 1 if criticial failure.

    Any exception is considered critical.

    @param                func    The function to run (almost always main)
    @param                bares   Pass any number of bare parameters to func
    @param                keywords        Pass any keyword=values on to func

    @b Examples
    @code
        import UTP

        def main():
            print('hello')

        if __name__ == __main__:
            exit(UTP.run(main))
    @endcode
    """
    import sys
    import IAm
    import signal

    def handler(signum, frame):
        raise RuntimeFail(ItemType.other, 'Killed with signal {signum}', signum=signum)

    signal.signal(signal.SIGTERM, handler)

    try:
        result = func(*bares, **keywords)
        if result:
            Logging.Log(logger, IAm.on_type()).fail()
            sys.exit(result)
        else:
            Logging.Log(logger, IAm.on_type()).pass_()
    except SystemExit as e:
        sys.exit(e.args[0])
    except:
        try:
            logger.error('<remote tb> {}'.format('\n<remote tb> '.join(sys.exc_info()[1].tb.splitlines())))
        except:
            pass
        logger.exception('Unhandled Exception has been thrown')
        Logging.Log(logger, IAm.on_type()).fail()
        sys.exit(99)



if __name__ == '__main__':
    import sys
    print(runmain(sys.argv[1:]))
