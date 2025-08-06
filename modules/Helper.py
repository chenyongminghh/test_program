#!/usr/local/bin/python35
# -*- coding: utf-8 -*-
#
# @module Helper
#
# Provide lot of common, convenient, reliable functions.
#


import os
import os.path as osp
import sys
import pty
import tty
import termios
import errno
import signal
import re
import time
import datetime
import tempfile
import shlex
import shutil
import inspect
import subprocess
import select
import telnetlib
import contextlib
import collections
import logging
import itertools
import json
from functools import wraps
from contextlib import suppress

hexdigits_pattern = r'[0-9a-fA-F]'
mac_pattern = r'[0-9a-fA-F]{2}(?P<d>[-:]?)[0-9a-fA-F]{2}(?:(?P=d)[0-9a-fA-F]{2}){4}'
ip_pattern = r'(?:[0-9]{1,3}\.){3}[0-9]{1,3}'
pci_slot_pattern = r'(?:([0-9a-fA-F]+):)?([0-9a-fA-F]{2}):([01][0-9a-fA-F])\.([0-7])'

RE_TYPE = type(re.compile('blah'))


class Closing:
    """! Context to automatically close something at the end of a block.
    """

    def __init__(self, thing, close_only_exc=False):
        self.thing = thing
        self.close_only_exc = close_only_exc

    def __enter__(self):
        return self.thing

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.close_only_exc or exc_tb:
            self.thing.close()


class CachedProperty(object):
    """! Decorator that converts a method with a single self argument into a
    property cached on the instance.
    """

    def __init__(self, func):
        self.func = func
        self.__doc__ = getattr(func, '__doc__')

    def __get__(self, instance, cls=None):
        if instance is None:
            return self

        res = instance.__dict__[self.func.__name__] = self.func(instance)
        return res


class LineIter:
    """! A line-by-line iterator, which will skip blank lines, and optional
    comment lines.
    """

    def __init__(self, text, single_line_comment=None, trim=True):
        self._text = text
        self._trim = trim
        self._comment = single_line_comment

    def __iter__(self):
        self._iter = self._text.splitlines().__iter__()
        return self

    def __next__(self):
        while True:
            line = self._iter.__next__()
            if self._trim:
                line = line.strip()

            if line and not (self._comment and re.match(self._comment, line)):
                return line


class AttrDict(collections.MutableMapping):
    """! A dictionary where members can be accessed as attributes.
    """

    def __init__(self, *args, **kwargs):
        self.__dict__['_store'] = dict()
        self.update(dict(*args, **kwargs))

    def __getattr__(self, item):
        if item in self._store:
            return self._store[item]
        else:
            raise AttributeError(
                "'{}' object has no attribute '{}'".format(type(self).__name__, item))

    def __setattr__(self, key, value):
        self._store[key] = value

    def __delattr__(self, item):
        if item in self._store:
            del self._store[item]
        else:
            raise AttributeError(
                "'{}' object has no attribute '{}'".format(type(self).__name__, item))

    def __getitem__(self, key):
        return self._store[key]

    def __setitem__(self, key, value):
        self._store[key] = value

    def __delitem__(self, key):
        del self._store[key]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def __repr__(self):
        return self._store.__repr__()


class Table(list):
    """! A Table representing a list of related data rows.
    """

    class Row(tuple):
        """! A row representing a tuple of columns which can be accessed by
        index or column name (if specified).
        """

        def __new__(cls, iterable, *args, **kwargs):
            return super().__new__(cls, iterable)

        def __init__(self, iterable, tbl=None):
            super().__init__()
            self.table = tbl

        def __getitem__(self, item):
            if self.table and self.table.col_names:
                with contextlib.suppress(Exception):
                    i = self.table.col_names.index(item)
                    return super().__getitem__(i)

            return super().__getitem__(item)

    def __init__(self, data=None, row_sep=None, col_sep=None, col_names=None):
        """! Initialize a table object.

        @param data: string or bytes that will be split into rows, columns in table.
        @param row_sep: delimiter of rows, default is newline (\n, \r\n, \r).
        @param col_sep: delimiter of columns, default is whitespace.
        @param col_names: list of column names, if a column name is empty (eval to False),
        the corresponding column will be discarded.
        """
        super().__init__()

        self._col_names = tuple()
        if data:
            self.load(data, row_sep, col_sep, col_names)

    @property
    def col_names(self):
        return tuple(n for n in self._col_names if n)

    def load(self, data, row_sep=None, col_sep=None, col_names=None):
        """! Split data into rows, columns, and fill in table.
        """
        self.clear()
        if col_names:
            self._col_names = tuple(n for n in col_names if n)
        else:
            col_names = tuple()
            self._col_names = col_names

        rows = data.splitlines() if row_sep is None else data.split(sep=row_sep)
        for r in rows:
            cols = get_values(r, sep=col_sep, maxsplit=len(col_names) - 1)
            if col_names:
                cols = list(v for n, v in itertools.zip_longest(col_names, cols) if n)

            self.append(Table.Row(cols, tbl=self))


class FString(str):
    """! A formatted string (f-string) literal may contain replacement fields,
    which are expressions delimited by curly braces {}.
    While other string literals always have a constant value, formatted strings
    are really expressions evaluated at run time.

    Usage:
        fs = FString('x is {x} and y is {y}')
        x = 6
        y = 7
        print(fs)  # x is 6 and y is 7
        x = 'a'
        y = 'b'
        print(fs)  # x is a and y is b
    """

    def __new__(cls, f_string):
        obj = super().__new__(cls, f_string)
        obj.f_string = f_string
        return obj

    def __str__(self):
        # get all accessible variables in LEGB namespaces
        caller_frame = inspect.currentframe().f_back
        vars_ = caller_frame.f_builtins.copy()  # Built-in scope

        e_vars = []  # Enclosed scopes (the outermost is global)
        while caller_frame:
            e_vars = list(caller_frame.f_locals.items()) + e_vars
            caller_frame = caller_frame.f_back

        vars_.update(e_vars)

        return self.format_map(vars_)

    def __repr__(self):
        return '{}({!r})'.format(__class__.__name__, self.f_string)


def get_values(line, sep=None, maxsplit=-1, names=None, trim=True):
    """! Return a list of the values in <line>, using <sep> as the delimiter string.

    @param names: a dict of name/value pairs is returned if given.
    """
    values = line.split(sep, maxsplit)
    if trim:
        values = [v.strip() for v in values]

    if names:
        assert len(values) == len(names)
        return {n: v for n, v in zip(names, values) if n}

    return values


def _update_key_value(d, line, sep=None, keys=None, trim=True):
    """! Parse the <line> which format is KEY<sep>VALUE, and update the KEY/VALUE
    to dict - d.

    @param keys: only these keys are considered if given.

    @return: True if the <line> is format of KEY<sep>VALUE.
    """
    k_v = line.split(sep, maxsplit=1)
    if len(k_v) == 2:
        k, v = k_v
        k = k.strip()
        if not keys or k in keys:
            v = v.strip() if trim else v
            if k in d:  # already exist this key
                prior_v = d[k]
                if isinstance(prior_v, list):
                    prior_v.append(v)
                else:
                    d[k] = [prior_v, v]
            else:
                d[k] = v

        return True


def get_key_values(text, sep=None, keys=None, trim=True):
    """! Parse each line in <text>, which format is KEY<sep>VALUE, and
    return a dict of KEY/VALUE pairs.

    @param keys: only these keys are considered if given.
    """
    d = {}
    for line in LineIter(text, single_line_comment='#', trim=False):
        _update_key_value(d, line, sep=sep, keys=keys, trim=trim)

    return d


def get_grouped_key_values(text, group_pattern, sep=None, keys=None, trim=True, func=None):
    """! Parse each line in <text>, which format is:
        KEY<sep>VALUE or
        group (matched the <group_pattern>),
    and return a dict of {group: {key: value, ...}, ...}.

    @param group_pattern: pattern to match group line. All the named groups
    in it also will be updated to the dict under this group. A named group - key
    must be there used as the group key.

    @param keys: only these keys are considered if given.

    @param func: called after each group parsed complete. The prototype is:
        func(group_key, group_dict, discard_lines)
    discard_lines is a list of lines which are not the format of KEY<sep>VALUE in group.
    If a value (True evaluated) returned, it will be used as the new group key.
    """
    groups = {}

    def add_group(group_key, group, discard_lines):
        if callable(func):
            new_group_key = func(group_key, group, discard_lines)
            if new_group_key:
                group_key = new_group_key

        assert group_key not in groups
        groups[group_key] = group

    group = None  # this is a dict of a certain group
    for line in LineIter(text, single_line_comment='#', trim=False):
        m = re.search(group_pattern, line, re.I)
        if m:
            if group is not None:
                add_group(group_key, group, discard_lines)

            group = m.groupdict()
            group_key = group.pop('key')
            discard_lines = []
        elif group:
            if not _update_key_value(group, line, sep=sep, keys=keys, trim=trim):
                discard_lines.append(line)

    if group is not None:
        add_group(group_key, group, discard_lines)

    return groups


def get_dict_values(d, keys, default=None):
    """! Get a list of values for the specified keys from dict - d.
    """
    return [d.get(k, default) for k in keys]


def get_obj_attrs(obj, attrs, default=None):
    """! Get a list of values for the specified attributes from obj.
    """
    return [getattr(obj, attr, default) for attr in attrs]


def any_in(value, iterable, ignore_case=True):
    """! Return True if the <value> in any item of the <iterable>.
    """
    if ignore_case and hasattr(value, 'lower'):
        value = value.lower()

    for x in iterable:
        if ignore_case and hasattr(x, 'lower'):
            x = x.lower()

        if value in x:
            return True


def join(*objs, sep=', ', to_str=str):
    """! Join one or more to_str(...) of objects intelligently.
    """
    return sep.join(map(to_str, objs))


def countdown(duration, start=True):
    """! A countdown timer.

    @param duration: specify the total seconds.

    @param start: start the countdown at once if True, otherwise at the first call
    of the returned closure function.

    @return: a closure function which return the seconds left when called.

    @usage:
        time_left = countdown(60)
        while True:
            # Do something here...
            if time_left() <= 0:
                break
    """
    if duration is None:
        return lambda: float('inf')

    end_time = time.time() + duration if start else 0

    def time_left():
        nonlocal end_time
        if end_time == 0:
            end_time = time.time() + duration

        tl = end_time - time.time()
        return tl if tl > 0.0 else 0

    return time_left


def version_tuple(version, pattern=r'[-\._]', func=lambda x: int(x, 16)):
    """! Breaks a version string into a comparable tuple of version parts.

    @param version: version string to convert.
    @param pattern: regex pattern of delimiter to break version string up.
    @param func: called for each version parts if given, and the returned value
    is regard as this version part.

    @return: tuple of version parts.
    """
    return tuple(func(v) if func else v for v in re.split(pattern, version))


def compact(string):
    """! Compact a string - remove all whitespace from string, and convert it
    to lowercase.
    """
    return re.sub(r'\s+', '', string).lower()


def split_args(args):
    """! Split the command line args into list using shell-like syntax.
    """
    if args:
        if isinstance(args, str):
            return shlex.split(args)
        else:
            assert isinstance(args, (list, tuple))
            return args
    else:
        return []


def retry(max_retries=3, interval=2, check_ret=None, check_exc=None, logger=None):
    """Retry calling the decorated function <max_retries> amount of times.

    @param max_retries: maximum number of retries to have.
    @param interval: interval between retries in seconds.
    @param check_ret: None or a callable function to indicate success criteria
    on return of decorated function - retrying if check_ret(r) evaluated False.
    @param check_exc: None or a callable function to indicate retrying criteria
    when exception raised - retrying if check_exc(e) evaluated True.
    @param logger: logger to use if specified.
    """

    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            nonlocal max_retries

            while max_retries > 1:
                try:
                    r = f(*args, **kwargs)
                    if check_ret is None or check_ret(r):
                        return r

                    if logger:
                        logger.warning('{} returned, retrying in {} seconds...'.format(r, interval))
                except Exception as e:
                    if check_exc is None or not check_exc(e):
                        raise

                    if logger:
                        logger.warning('{!r} raised, retrying in {} seconds...'.format(e, interval))

                time.sleep(interval)
                max_retries -= 1

            return f(*args, **kwargs)

        return f_retry

    return deco_retry


def run(args, *, timeout=None, check=True, run_func=None, **kwargs):
    """! Run the command described by args. Wait for command to complete, then
    return a CompletedProcess instance.
    """
    if 'stdout' not in kwargs:
        kwargs['stdout'] = subprocess.PIPE
    if 'stderr' not in kwargs:
        kwargs['stderr'] = subprocess.PIPE
    if 'universal_newlines' not in kwargs:
        kwargs['universal_newlines'] = True

    if isinstance(args, str):
        if not kwargs.get('shell', False):
            args = shlex.split(args)

    if not run_func:
        run_func = subprocess.run

    return run_func(args, timeout=timeout, check=check, **kwargs)


def stack(context=0):
    """! Return a list of frame records from the caller's stack to outermost.

    @return: a list of named tuples FrameInfo(frame, filename, lineno, function,
    code_context, index).
    """
    return inspect.stack(context)[1:]  # skip the frame record of Helper itself


def pids():
    return [int(entry.name) for entry in os.scandir('/proc') if entry.name.isdigit()]


def ppid_map():
    """! Obtain a {pid: ppid, ...} dict for all running processes in one shot.
    """
    the_map = {}
    for pid in pids():
        try:
            p = Process(pid)
        except (FileNotFoundError, ProcessLookupError):
            pass
        else:
            the_map[pid] = p.ppid

    return the_map


def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


class Process:
    """! Linux process implementation.
    """

    def __init__(self, pid=None):
        if pid is None:
            pid = os.getpid()

        os.kill(pid, 0)
        self.pid = pid

        stat = self._parse_stat_file()
        self.comm = stat[1]
        self.ppid = int(stat[3])

    def _read_file(self, filename):
        assert self.pid
        with open(osp.join('/proc', str(self.pid), filename)) as fh:
            return fh.read()

    def _read_link(self, link_name):
        assert self.pid
        return os.readlink(osp.join('/proc', str(self.pid), link_name))

    def _parse_stat_file(self):
        stat = self._read_file('stat')
        lpar = stat.find('(')
        rpar = stat.rfind(')')

        pid = stat[:lpar].strip()
        comm = stat[lpar + 1:rpar]

        return (pid, comm, *stat[rpar + 2:].split())

    @property
    def parent(self):
        if self.ppid and check_pid(self.ppid):
            return __class__(self.ppid)

    @property
    def state(self):  # one char of "RSDZTW"
        return self._parse_stat_file()[2]

    @property
    def cmdline(self):
        if not hasattr(self, '_cmdline'):
            cmdline = self._read_file('cmdline')
            self._cmdline = [x for x in cmdline.strip().split('\x00') if x]

        return self._cmdline

    @property
    def cwd(self):
        return self._read_link('cwd')

    @property
    def exe(self):
        if not hasattr(self, '_exe'):
            self._exe = self._read_link('exe')

        return self._exe

    @property
    def comm_ex(self):
        if not hasattr(self, '_comm_ex'):
            if re.match(r'python\d[.]*\d$', self.comm.strip(), re.I):  # python interpreter
                # Try to find the python script file
                for arg in self.cmdline[1:]:
                    if arg.endswith('.py') and arg[0] != '-':
                        self._comm_ex = osp.basename(arg)
                        break
                else:
                    self._comm_ex = ''
            else:
                self._comm_ex = self.comm

        return self._comm_ex

    def kill(self, timeout=6):
        try:
            os.kill(self.pid, signal.SIGTERM)
        except OSError:
            self.pid = None
            return

        time_left = countdown(timeout)
        while check_pid(self.pid):
            if time_left() <= 0:
                break

            time.sleep(1)
        else:
            self.pid = None
            return

        try:
            os.kill(self.pid, signal.SIGKILL)
        except OSError:
            pass

        self.pid = None


def tty_run(args, *, timeout=None, check=True, tty_input=None, tty_raw_mode=False,
            newline_end=True):
    """! Run the command described by args in a new pseudo-terminal. Wait for
    command to complete, then return a CompletedProcess instance.

    @param tty_input: str, or dict of hint, answer pairs for TTY input.
    @param tty_raw_mode: TTY raw mode if True, otherwise canonical mode.
    @param newline_end: if True, and input and/or each answer of tty_input doesn't
    end in newline this is added.

    @notes: it is useful for command that read input from TTY rather than stdin, e.g.
    sudo, ssh, scp, ssh-copy-id...

    @usage:
        tty_run(['sudo', '-u', 'root', 'ls'], tty_input=...), here tty_input can be:
            - '<password>' (str)
            - {'[sudo] password for': '<password>'} OR
            {re.compile('[sudo] password for', re.I): '<password>'} (dict of hint, answer pairs)

        tty_run(['ssh', 'root@192.168.12.177', 'ip link'], tty_input='yes\npassw0rd\n')
        tty_run(['ssh', 'root@192.168.12.177', 'ip link'], tty_input={
            'continue connecting (yes/no)?': 'yes',
            'password:': 'passw0rd',
            })
    """

    def newline_wrap(input, encode=True):
        x = (input + '\n') if newline_end and input[-1] not in ('\n', '\r') else input
        return x.encode() if encode else x

    def close_fds(*fds):
        for fd in fds:
            try:
                os.close(fd)
            except OSError:
                pass

    def tty_disable_echo(tty_fd):
        tty_attrs = termios.tcgetattr(tty_fd)
        tty_attrs[3] &= ~termios.ECHO
        termios.tcsetattr(tty_fd, termios.TCSADRAIN, tty_attrs)

    def get_prompt_line(lines):
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip():
                return i

    def terminate_process(pid):
        try:
            Process(pid).kill(timeout=3)
            return os.waitpid(pid, 0)
        except OSError:
            return 0, -1

    # Create pipes to communicate with stdout, stderr of child process
    stdout_r, stdout_w = os.pipe()
    stderr_r, stderr_w = os.pipe()

    pid, master_fd = pty.fork()
    if pid == 0:  # child process
        os.dup2(stdout_w, 1)
        os.dup2(stderr_w, 2)
        close_fds(stdout_r, stdout_w, stderr_r, stderr_w)

        if isinstance(args, str):
            args = shlex.split(args)
        os.execlp(args[0], *args)
    else:
        child = Process(pid)

    # Parent process
    close_fds(stdout_w, stderr_w)

    if tty_raw_mode:  # TTY raw mode
        tty.setraw(master_fd, termios.TCSANOW)
    else:  # TTY canonical mode and turn off input echo
        tty_disable_echo(master_fd)

    w_pid = 0
    status = -1

    prompt_fds = master_fd, stdout_r  # FDs that may prompt user input
    # Prompt lines of TTY and stdout, which is last effective line in output.
    # Search here for tty_input matching: fd -> prompt line no
    prompt_lines = {fd: None for fd in prompt_fds}

    read_fds = [*prompt_fds, stderr_r]
    outputs = {fd: [] for fd in read_fds}

    try:
        time_left = countdown(timeout)
        while w_pid != pid:
            rlist, _, _ = select.select(read_fds, [], [], 1)
            if rlist:
                for fd in rlist:
                    data = ''
                    try:
                        data = os.read(fd, 1024)
                    except OSError as err:
                        if err.errno != errno.EIO:
                            raise

                    if data:
                        lines = data.decode().splitlines(keepends=True)
                        output = outputs[fd]
                        if output:
                            x = output.pop()
                            output.extend((x + lines[0]).splitlines(keepends=True))
                            output.extend(lines[1:])
                        else:
                            output.extend(lines)

                        if fd in prompt_lines:
                            i = get_prompt_line(outputs[fd])
                            if i is not None:
                                prompt_lines[fd] = i
                    else:  # no data read (EOF) - peer side of pipe closed
                        read_fds.remove(fd)
            else:  # no data available
                if time_left() <= 0:
                    raise subprocess.TimeoutExpired(args, timeout)

                child_state = None
                with contextlib.suppress(FileNotFoundError, ProcessLookupError):
                    child_state = child.state

                if tty_input and child_state in ('S',):  # # sleeping in an interruptible wait
                    if isinstance(tty_input, dict):  # dict of hint, answer pairs
                        for (fd, lno), hint in itertools.product(prompt_lines.items(), tty_input):
                            if lno is not None:
                                prompt = outputs[fd][lno]
                                if isinstance(hint, str) and hint in prompt or \
                                        isinstance(hint, RE_TYPE) and hint.search(prompt):
                                    answer = tty_input[hint]
                                    os.write(master_fd, newline_wrap(answer))
                                    del tty_input[hint]  # remove matched hint from tty_input
                                    break
                    elif isinstance(tty_input, str):
                        os.write(master_fd, newline_wrap(tty_input))
                        tty_input = ''

                w_pid, status = os.waitpid(pid, os.WNOHANG)
    finally:
        close_fds(master_fd, stdout_r, stderr_r)
        if w_pid != pid:  # terminate child process
            w_pid, status = terminate_process(pid)

    proc = subprocess.CompletedProcess(args, status,
                                       ''.join(outputs[stdout_r]), ''.join(outputs[stderr_r]))
    proc.ttyout = ''.join(outputs[master_fd])  # although master_fd closed, used as key is OK
    if check:
        proc.check_returncode()

    return proc


def ssh_tty_input(password):
    return {'continue connecting (yes/no)?': 'yes',
            re.compile(r'password:', re.I): str(password), }


def ssh_run(cmd, host, user=None, password=None, port=22, ssh_options=None, timeout=20, check=True,
            tty_input=None):
    """! Run a command on remote host over SSH. Wait for command to complete, then
    return a CompletedProcess instance.
    """
    args = ['ssh',
            '-o', 'PreferredAuthentications=publickey,password',
            '-o', 'NumberOfPasswordPrompts=1',
            '-o', 'StrictHostKeyChecking=no',
            ]

    if ssh_options:
        args.extend(split_args(ssh_options))

    if port != 22:
        args.extend(['-p', str(port)])

    args.append('{}@{}'.format(user, host) if user else host)

    if isinstance(cmd, (list, tuple)):
        cmd = ' '.join(shlex.quote(x) for x in cmd)
    args.append(cmd)

    if tty_input is None:
        tty_input = ssh_tty_input(password)

    return tty_run(args, timeout=timeout, check=check, tty_input=tty_input)


class SSHClient:
    """! This class is utilized to run command on remote host over SSH. (based
    on Public Key Authentication)

    @usage:
        with Closing(SSHClient()) as ssh:
            ssh.connect('192.168.12.2', 'root', 'passw0rd')
            proc = ssh.run('ip addr')
    """

    AUTH_KEYS = {'rsa': 'id_rsa', 'dsa': 'id_dsa', 'ecdsa': 'id_ecdsa'}
    KEY_TYPE = 'rsa'

    def __init__(self):
        self.host = None

    def connect(self, host, user=None, password=None, port=22, retain_public_key=False):
        """! Setup a SSH connection to the host specified.
        """
        self.close()

        args = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=no']
        cmd = 'hostname'

        if port != 22:
            args.extend(['-p', str(port)])

        self._user_host = '{}@{}'.format(user, host) if user else host
        args.append(self._user_host)
        args.append(cmd)

        proc = run(args, timeout=20, check=False)
        if proc.returncode:
            self.setup_pubkey_auth(host, user, password, port)
            run(args, timeout=20)
        else:
            self._key_file = None

        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.retain_auth_key = retain_public_key

    def setup_pubkey_auth(self, host, user=None, password=None, port=22):
        """! Set up public key authentication.
        """
        user_ssh_dir = osp.join(osp.expanduser('~'), '.ssh')
        if osp.exists(user_ssh_dir):
            stat_info = os.stat(user_ssh_dir)
            if not oct(stat_info.st_mode).endswith('700'):
                os.chmod(user_ssh_dir, 0o700)
        else:
            os.mkdir(user_ssh_dir, mode=0o700)

        key_file = osp.join(user_ssh_dir, self.AUTH_KEYS[self.KEY_TYPE])
        if not osp.exists(key_file):
            run('echo Y | ssh-keygen -t {} -N "" -f {}'.format(self.KEY_TYPE, key_file),
                shell=True, timeout=6)

        args = ['ssh-copy-id', '-i', key_file]
        # Certain old ssh-copy-id doesn't support parameters of <-p port>, <-o option> 
        # in command line, so that we wrap it into [user@]host.
        proc = run('ssh-copy-id -h', shell=True, check=False)
        if '[-p port]' in proc.stderr:
            args.extend(['-p', str(port), '-o', 'StrictHostKeyChecking=no', self._user_host])
        else:  # old ssh-copy-id
            args.append('-p {} -o StrictHostKeyChecking=no {}'.format(port, self._user_host))

        tty_run(args, timeout=20, tty_input=ssh_tty_input(password))

        proc = run(['ssh-keygen', '-y', '-f', key_file])
        self._auth_key = proc.stdout.strip()
        self._key_file = key_file

    def run(self, cmd, *, ssh_options=None, timeout=10, check=True, **kwargs):
        """! Run a command on remote host over SSH. Wait for command to complete, then
        return a CompletedProcess instance.
        """
        assert self.host

        args = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=no']
        if self.port != 22:
            args.extend(['-p', str(self.port)])

        if self._key_file:
            args.extend(['-i', self._key_file, '-o', 'PreferredAuthentications=publickey'])

        if ssh_options:
            args.extend(split_args(ssh_options))

        args.append(self._user_host)
        if isinstance(cmd, (list, tuple)):
            cmd = ' '.join(shlex.quote(x) for x in cmd)
        args.append(cmd)

        if 'start_new_session' not in kwargs:
            kwargs['start_new_session'] = True

        return run(args, timeout=timeout, check=check, **kwargs)

    def close(self):
        if self.host:
            if self._key_file and not self.retain_auth_key:
                pub_key = self._auth_key.split()[1]  # ssh-rsa key_blob [comment]
                self.run('sed -i "\\#{}#d" .ssh/authorized_keys'.format(pub_key), check=False)

            self.host = None

    def __del__(self):
        self.close()


class TelnetClient:
    """! This class is utilized to run command on remote host over telnet.

    @usage:
        with Closing(TelnetClient()) as tn:
            tn.connect('192.168.0.254', 'admin', 'admin', ...)
            tn.run('set group group_all cycle)
    """

    def __init__(self):
        self.tn = None

    def open(self, host, user, password=None,
             login_prompt='login: ', password_prompt='Password: ',
             pre_cmd=None, command_prompt='telnet> ',
             exit_cmd=None,
             port=0, timeout=20):
        """! Create a new telnet client, connect to a host and login.

        @return: bytes of output from this telnet login.
        """
        self.close()

        outs = bytearray()
        with Closing(telnetlib.Telnet(host, port), close_only_exc=True) as tn:
            if login_prompt:
                expect, m, data = tn.expect([login_prompt.encode()], timeout)
                if expect != 0:
                    raise TimeoutError('telnet: timed-out waiting for login prompt')

                outs += data
                tn.write(user.encode() + b'\n')

                if password_prompt:
                    expect, m, data = tn.expect([password_prompt.encode()], timeout)
                    if expect != 0:
                        raise TimeoutError('telnet: time-out waiting for password prompt')

                    outs += data
                    tn.write(password.encode() + b'\n')

            if pre_cmd:
                pre_expect, pre_cmd = pre_cmd
                if pre_expect:
                    expect, m, data = tn.expect([pre_expect.encode()], timeout)
                    if expect != 0:
                        raise TimeoutError('telnet: time-out waiting for PRE command prompt')

                    outs += data

                if pre_cmd:
                    tn.write(pre_cmd.strip().encode() + b'\n')

            self.command_prompt = command_prompt.encode()
            expect, m, data = tn.expect([self.command_prompt], timeout)
            if expect != 0:
                raise TimeoutError('telnet: time-out waiting for command prompt')

        outs += data
        self.exit_cmd = exit_cmd.strip() if exit_cmd else exit_cmd
        self.tn = tn

        return outs

    def run(self, cmd, trim=True, expected=None, timeout=20):
        """Run a command on remote host over telnet.

        @return: bytes of output from command executing.
        """
        assert self.tn

        expected_list = [self.command_prompt]
        if expected:
            expected_list.append(expected)

        cmd = cmd.strip().encode()
        self.tn.read_very_eager()  # try to clear data buffer
        self.tn.write(cmd + b'\n')

        expect, m, data = self.tn.expect(expected_list, timeout)
        if expect != 0:
            raise TimeoutError('telnet: run command "{}" timed out'.format(cmd.decode()))

        if trim:  # remove command line from head and command prompt from tail
            data = re.sub(br'^\s+|\s+$', b'', data).splitlines(keepends=True)
            first = 1 if re.search(cmd, data[0]) else 0
            last = len(data)
            if re.search(self.command_prompt.rstrip(), data[-1]):
                last -= 1

            data = b''.join(data[first:last])

        return data

    def close(self):
        if self.tn:
            with contextlib.suppress(OSError):
                if self.exit_cmd:
                    self.tn.write(self.exit_cmd.encode() + b'\n')

                self.tn.close()
                self.tn = None

    def __del__(self):
        self.close()


def get_dhcp_leases(lease_data, mac_as_key=True, active=True):
    """! Get isc-dhcp-server IPv4 leases.

    @param mac_as_key: mac used as the key of returned dict if true, otherwise ip is.
    @param active: if true, return active and valid ip leases only.

    @return: a dict mapping from ip or mac to dict of lease parameters:
        ip, starts, ends, cltt, binding state, next binding state, abandoned, hardware, mac
    """

    def parse_time(s):
        if 'epoch' in s:
            epoch_time = float(s.split()[1])  # epoch  <seconds-since-epoch>
            res = datetime.datetime.utcfromtimestamp(epoch_time)
        else:
            *weekday, date_part, time_part = s.split()  # weekday year/month/day hour:minute:second
            year, mon, day = date_part.split('/')
            hour, minute, sec = time_part.split(':')
            res = datetime.datetime(*map(int, (year, mon, day, hour, minute, sec)))

        return res

    def lease_is_active(lease, utc_now):
        if lease.get('binding state') != 'active':
            return False

        start = lease.get('starts')
        if start and start > utc_now:
            return False

        end = lease.get('ends')
        if end and end < utc_now:
            return False

        return True

    regex_lease_block = re.compile(r"lease (?P<ip>\d+\.\d+\.\d+\.\d+) {(?P<config>[\s\S]+?)\n}")
    utc_now = datetime.datetime.utcnow()
    leases = {}
    for m in regex_lease_block.finditer(lease_data):
        block = m.groupdict()
        ip = block['ip']

        config = block['config']
        lease = {'ip': ip}
        mac = None
        for line in LineIter(config, single_line_comment='#'):
            if line[-1] == ';':
                line = line[:-1]

                key = None
                if line.startswith(('starts', 'ends', 'cltt')):
                    key, value = line.split(maxsplit=1)
                    if key == 'ends' and 'never' in value:
                        value = None
                    else:
                        value = parse_time(value)
                elif line.startswith(('binding state', 'next binding state')):
                    key, value = line.rsplit(maxsplit=1)
                elif line.startswith('abandoned'):
                    key, value = 'abandoned', None
                elif line.startswith('hardware'):
                    key, type, value = line.split()
                    if type == 'ethernet':
                        mac = value
                    else:
                        value = None
                    lease['mac'] = mac  # mac - general name for hardware

                if key:
                    lease[key] = value

        if 'abandoned' not in lease:
            if not active or lease_is_active(lease, utc_now):
                if mac_as_key:
                    if mac:
                        leases[mac] = lease
                else:
                    leases[ip] = lease

    return leases


@contextlib.contextmanager
def cd(path):
    """! A context manager which changes the working directory to the given
    path, and then changes it back to its previous value on exit.
    """
    prev_dir = os.getcwd()
    os.chdir(os.path.expanduser(path))
    try:
        yield os.getcwd()
    finally:
        os.chdir(prev_dir)


@contextlib.contextmanager
def cd_temp(suffix=None, prefix=None, dir=None, delete=False):
    """! A context manager which changes the working directory to a temporary
    directory, and then changes it back to its previous value on exit.
    """
    temp_dir = tempfile.mkdtemp(suffix, prefix, dir)

    prev_dir = os.getcwd()
    os.chdir(temp_dir)
    try:
        yield os.getcwd()
    finally:
        os.chdir(prev_dir)
        if delete:
            shutil.rmtree(temp_dir, ignore_errors=True)


def readvars(fh):
    """seeks to offset 0 and reads the given fh 

    Use with extreme caution!   *Note* you would not normally call this without getting 
    a read lock on fh

    @return dict(): keyword, value dictionary from file contents
    """
    d = {}
    fh.seek(0)
    for line in fh:
        line = line.strip()
        if line == '' or line.startswith('#'):
            continue
        with suppress(ValueError, json.decoder.JSONDecodeError):
            name, value = line.split('=', 1)
            d[name.strip()] =  json.loads(value.strip())
            continue
        break
    return d

            
