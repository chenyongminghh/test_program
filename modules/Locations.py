#!/usr/local/bin/python35
import sys
import os
import os.path as osp
import time
from urllib.parse import urlparse
from functools import wraps

import Default
import Remote
import PlatformABC
import FileTools
import Misc
import Run
import Variable
from Cache import Cache
from FileTools import UTPFileNotFound
import Helper

import Fails  # this will import all Fail classes and ItemType into builtins namespace


COMMAND_TRACE = 'cmd_trace.log'

## A handy way to tell bit width
BITS = '64bit' if sys.maxsize > 2**32 else '32bit'

OUR_REPO_DIR = osp.abspath(osp.dirname(osp.dirname(__file__))) # Our repo dir
OUR_MODULE_DIR = osp.join(OUR_REPO_DIR, 'modules') # Our repo/modules
OUR_UTILITY_DIR = osp.join(OUR_REPO_DIR, 'utilities') # Our repo/utilities


## Version string for version of python running
VERSION = '{}{}'.format(*sys.version_info[:2])

## Standard python extensions for this env
PYTHON_EXTENSIONS = tuple('_{}.{}'.format(VERSION, x) for x in ('py', 'so'))
PYTHON_EXTENSIONS += ('.py', '.so')




GENERAL_ARGS = FileTools.FindFileArgs(
    topdirs=   ['product', 'common', 'platform', '..', OUR_REPO_DIR],
    middledirs=['modules', 'tables','tests', 'utilities', 'sequences','tools',''],
    bits=      [BITS, ''],
    extensions=['']
)

ORDER_ARGS = FileTools.FindFileArgs(topdirs=('..',), middledirs=('',),
                          bits=('',),
                          extensions=GENERAL_ARGS.extensions)
SEQUENCE_ARGS = FileTools.FindFileArgs(topdirs=GENERAL_ARGS.topdirs,
                             middledirs=('sequences',),
                             bits=('',),
                             extensions=GENERAL_ARGS.extensions)
TABLE_ARGS = FileTools.FindFileArgs(topdirs=GENERAL_ARGS.topdirs,
                          middledirs=('tables',),
                          bits=('',),
                          extensions=GENERAL_ARGS.extensions)
UTILITY_ARGS = FileTools.FindFileArgs(topdirs=GENERAL_ARGS.topdirs,
                            middledirs=('utilities',),
                            bits=('',),
                            extensions=GENERAL_ARGS.extensions)
TEST_ARGS = FileTools.FindFileArgs(topdirs=GENERAL_ARGS.topdirs,
                         middledirs=('tests','utilities'),
                         bits=('',),
                         extensions=GENERAL_ARGS.extensions)
MODULE_ARGS = FileTools.FindFileArgs(topdirs=GENERAL_ARGS.topdirs,
                         middledirs=('modules', 'tests', 'utilities'),
                         bits=GENERAL_ARGS.bits,
                         extensions=PYTHON_EXTENSIONS)
RT_ARGS = FileTools.FindFileArgs(topdirs=('',),
                       middledirs=('',),
                       bits=('',),
                       extensions=('',))

TOOL_ARGS = FileTools.FindFileArgs(topdirs=GENERAL_ARGS.topdirs,
                                   middledirs=('tools'),
                                   bits=('',),
                                   extensions=('',))

PRODUCT_ONLY_ARGS = FileTools.FindFileArgs(topdirs=['product'],
                                           middledirs=GENERAL_ARGS.middledirs,
                                           bits=GENERAL_ARGS.bits,
                                           extensions=GENERAL_ARGS.extensions)


def cache_factory(ip, cwd, port, user, ssh_cmd='/usr/bin/ssh', env=None):
    proc = Remote.ssh_process(ip=ip, cwd=cwd, port=port, user=user, ssh_cmd=ssh_cmd, env=env)

    def close(proc_):
        proc_.stdin.close()
        proc_.stdout.close()
        proc_.stderr.close()

        # Removed the terminate/kill logic because it is killing the Master ssh when setup for MasterControl
        try:
            proc_.wait(timeout=0.1)
        except:
            pass

    return proc, close


def get_remote_by_scope(log, scope, target_cwd):
    env = None
    ssh_cmd = None
    if target_cwd is None:
        # Assume scope=[user[:password]@]IP[:port][/dir]
        parsed = urlparse('ssh://' + scope)
        ip = parsed.hostname
        port = parsed.port if parsed.port else 22
        scope = ip
        target_cwd = parsed.path if parsed.path else '/var/tmp'
        password = parsed.password if parsed.password else 'passw0rd'
        user = parsed.username if parsed.username else 'root'
    else:
        local = LocalLocation(scope=scope, cwd=Default.OUR_RT_DIR)
        ip = local.get('{}_IP'.format(scope.upper()), None)
        if not ip:
            raise InfoFail('We are not running on {scope} so you must provide {scope}_IP definition in variables',
                           scope=scope.upper())
        port = int(local.get('{}_PORT'.format(scope.upper()), default=22))
        user = local.get('{}_USER'.format(scope.upper()), default='root' if scope == 'uut' else None)
        password = local.get('{}_PASSWORD'.format(scope.upper()), default=None)

    if password:
        env =  env={**os.environ, **{'LC_MONETARY': repr({ip: password})}}
        ssh_cmd = osp.join(OUR_UTILITY_DIR, 'ssh.py')

    return SSHLocation(local_cwd=Default.OUR_RT_DIR, ip=ip, target_cwd=target_cwd, log=log, scope=scope,
                       port=port, user=user, env=env, ssh_cmd=ssh_cmd)


_procs = Cache(cache_factory)


def command_trace(run):
    """! A decorator for run* methods in RunABC, tracing the commands execution.
    """
    parents = []  # list of processes command names for me and ancestors
    p = Helper.Process()
    try:
        while p:
            parents.append(p.comm_ex)
            p = p.parent
    except (FileNotFoundError, ProcessLookupError):
        pass

    if not ('seq.py' in parents or  # in processes initiated by seq.py (include runseqs, srun)
            'start_utp.py' in parents or  # in start_utp.py process, and children
            'tstrun.py' in parents or
            os.environ.get('CMD_TRACE')):
        return run

    @wraps(run)
    def run_wrapper(self, *args, **kwargs):
        op = None
        tc = None  # test case
        if 'seq.py' in parents[1:]:  # seq.py is my ancestor process
            op = os.environ.get('CURRENT_OP') or None
            tc = os.environ.get('TEST_CASE') or None
        elif 'seq.py' == parents[0]:  # in process of seq.py
            # Skip command tracing for this calling path: seq.py -> Sequencer.py -> CodeLink.py
            if 'CodeLink.py' in (osp.basename(f.filename) for f in Helper.stack()):
                return run(self, *args, **kwargs)

        if not tc:
            tc = osp.basename(sys.argv[0])

        sep = ' | '
        ret = None
        with open(osp.join(COMMAND_TRACE), 'a') as fh:
            ts = time.time()
            start = time.strftime('%y%m%d-%H:%M:%S')
            cmd = args[0]
            if isinstance(cmd, (list, tuple)):
                cmd = ' '.join(cmd)

            try:
                ret = run(self, *args, **kwargs)
            finally:
                sec = '{:.3f}'.format(time.time() - ts)
                if isinstance(ret, int):
                    rc = ret
                elif hasattr(ret, 'returncode'):
                    rc = ret.returncode
                    if rc is None:  # may return a local/remote subprocess.Popen
                        sec = '>= ' + sec
                else:
                    rc = None

                print(start, self.scope, op, tc, cmd, rc, sec, sep=sep, file=fh, flush=True)

        return ret

    return run_wrapper


class LocalLocation(PlatformABC.PlatformABC, FileTools.LocalTools):
    """! A class that utilizes all local access to files """
    def variables(self, filename):
        return Variable.FileBackedVariables(osp.join(self.cwd, filename))

    @command_trace
    def runproc(self, *bares, **kw):
        with Misc.InDir(self.cwd):
            return Run.runproc(*bares, **kw)

    @command_trace
    def runproc_rt(self, *bares, **kw):
        with Misc.InDir(self.cwd):
            return Run.runproc_rt(*bares, **kw)

    @command_trace
    def runpopen(self, *bares, **kw):
        with Misc.InDir(self.cwd):
            return Run.runpopen(*bares, **kw)


class SSHLocation(PlatformABC.PlatformABC, PlatformABC.RemoteFunctionABC):
    """! Class that provides access to platform functions over ssh """
    def __init__(self, local_cwd, ip, scope, target_cwd, log, port=22, user=None, ssh_cmd=None, env=None):
        self.target_cwd = target_cwd
        self._log = log
        self._scope = scope
        self.ssh_cmd = ssh_cmd if ssh_cmd is not None else '/usr/bin/ssh'
        self.env = env
        self.proc = _procs.get(self, ip=ip, port=port, user=user, cwd=target_cwd, ssh_cmd=self.ssh_cmd, env=self.env)
        self.remote = Remote.RemoteControl(self.proc)

        # The RemoteControl  uses proc, so force a reference
        _procs.get(self.remote, ip=ip, port=port, user=user, cwd=target_cwd, ssh_cmd=self.ssh_cmd, env=self.env)

        # Remotely import some modules we will need
        l = LocalLocation(local_cwd, scope)
        for py_module in ('IAm', 'Default', 'Helper', 'Fails', 'EventAPI', 'UWIP', 'SSHTool', 'FileLock', 'Variable',
                          'MediaTools', 'Logging', 'LogHandlers', 'PlatformABC', 'FileTools', 'Misc', 'Run'):
            with l.open_file(py_module, args=MODULE_ARGS) as fh:
                self.remote.do_import(fh.read(), py_module,  fh.name)
        self.remote_file_tool = self.remote.make_instance('FileTools.LocalTools', target_cwd, scope)


    @property
    def cwd(self):
        return self.target_cwd

    @property
    def scope(self):
        return self._scope

    @property
    def log(self):
        return self._log

    @property
    def media(self):
        if self.cwd.startswith(Default.MTSN_DIR):
            return osp.split(self.cwd[len(Default.MTSN_DIR)+1])[0]
        else:
            return None

    def mkdtemp(self, *bares, **kw):
        return self.remote_file_tool.mkdtemp(*bares, **kw)

    def rmdir(self, *bares, **kw):
        return self.remote_file_tool.rmdir(*bares, **kw)
        
    def find_file(self, *bares, **kw):
        return self.remote_file_tool.find_file(*bares, **kw)

    def glob_file(self, *bares, **kw):
        return self.remote_file_tool.glob_file(*bares, **kw)

    def sha1_file(self, *bares, **kw):
        return self.remote_file_tool.sha1_file(*bares, **kw)

    def open_file(self, *bares, **kw):
        return self.remote_file_tool.open_file(*bares, **kw)

    def unlink_file(self, *bares, **kw):
        return self.remote_file_tool.unlink_file(*bares, **kw)

    def variables(self, filename, **kw):
        if not filename.startswith('/'):
            filename = osp.abspath(osp.join(self.target_cwd, filename))
        return self.remote.make_instance('Variable.FileBackedVariables', filename, **kw)

    @command_trace
    def runproc(self, *bares, **kw):
        return self.remote.make_instance('Run.runproc', *bares, **kw)

    @command_trace
    def runproc_rt(self, *bares, **kw):
        return self.remote.make_instance('Run.runproc_rt', *bares, **kw)

    @command_trace
    def runpopen(self, *bares, **kw):
        return self.remote.make_instance('Run.runpopen', *bares, **kw)

    def run_remote_function(self, func, *bares, **kw):
        return self.remote.call(func, *bares, **kw)

    def enable_logging(self, scope, level='INFO'):
        self.remote.enable_logging(scope, level)


if __name__ == '__main__':
    import os
    import logging
    import Logging
    import LogHandlers

    logging.basicConfig(style='{')

    ip = sys.argv[1]
    cmd = sys.argv[2:]
    scope = 'blah'

    logger = logging.getLogger()
    
    logger.setLevel(os.environ.get('UTP_LOG_LEVEL', 'INFO'))
    
    local = LocalLocation('.', scope)
    local.run(cmd)

    log = Logging.Log(logger, scope)
    remote = SSHLocation(local_cwd='.', ip=ip, scope=scope, target_cwd='/var/tmp', log=scope)
    remote.enable_logging(scope, logger.getEffectiveLevel())

    remote.run(cmd)


