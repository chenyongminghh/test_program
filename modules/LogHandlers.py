#!/usr/local/bin/python35
import os
import sys
import os.path as osp
import re
import time
import logging
import traceback

from Logging import *

from fcntl import flock,LOCK_EX,LOCK_UN,LOCK_SH,LOCK_NB


ERROR_LOG='error.log'
ERRORS_LOG='errors.log'
TEST_LOG='test.log'
TESTER_LOG='tester.log'
RAWTEST_LOG='rawtester.log'
ONFAIL_LOG = 'onfail.log'  # logging when running in fail block of sequence
LOGDATA_UTP='logdata.utp'

class _FileLock:
    """ Lock a file
    """
    def __init__(self, fh):
        self.fh = fh

    def __enter__(self):
        flock(self.fh.fileno(), LOCK_EX)
        return self.fh

    def __exit__(self, etype, evalue, tb):
        flock(self.fh.fileno(), LOCK_UN)
        return False



## A regex for checking for whitespace
WHITE_SPACE_RE = re.compile(r'\s')

def format_message(record):
    if record.args:
        if isinstance(record.args, dict):
            message = record.msg.format(record.args)
        else:
            message = record.msg.format(*record.args)
    else:
        message = record.msg

    if isinstance(message, (str, bytes)):
        return message
    else:
        return str(message)


class STDLogHandler(logging.Handler):
    def __init__(self, owner, scope,  cwd, *bares, **keywords):
        super().__init__(*bares, **keywords)
        assert not WHITE_SPACE_RE.search(owner), \
            'Parameter owner cannot contain any whitespace'
        self.owner = owner
        self.cwd = cwd
        self.scope = scope

    def create_general_header(self, levelno, record):
        return '{} {:5s} {} {}'.format(
            self.owner,
            record.scope if 'scope' in record.__dict__ else self.scope,
            time.strftime(DATE_TIME_FORMAT,time.localtime(record.created)),
            record.tag.strip() if hasattr(record, 'tag') else log_level_to_name[levelno].strip())

    def create_sparse_header(self, levelno, record):
        return '{} {}'.format(
            time.strftime(DATE_TIME_FORMAT, time.localtime(record.created)),
            record.tag.strip() if hasattr(record, 'tag') else log_level_to_name[levelno].strip())

    def emit(self, record):
        ''' Takes the logger record and does something with it

        In this case it will first print it to stdout if the level is below
        ERROR or stderr for ERROR and above.
        '''
        # This checks for level equal or above ERROR and prints to stderr,
        # stdout otherwise
        header = self.create_sparse_header(record.levelno, record)

        for line in format_message(record).splitlines():
            print(header, line, file=sys.stdout, flush=True)

        # This checks for exception, always print to stderr
        if record.exc_info:
            header = self.create_general_header(EXC_LEVEL, record)
            if isinstance(record.exc_info, list):
                lines = record.exc_info
            else:
                lines = "".join(traceback.format_exception(*record.exc_info)).splitlines()

            for line in lines:
                print(header, line, file=sys.stdout, flush=True)




class ErrorLogHandler(STDLogHandler):
    ''' Write to error.log and errors.log

    Writes the same thing to both.   It is up to the caller
    to erase the error.log between calls.
    '''
    def __init__(self, *bares, **kw):
        super().__init__(*bares, **kw)
        # Ensure that ERRORS_LOG remains first for full header output
        self.error_logs = [osp.join(self.cwd, ERRORS_LOG),
                           osp.join(self.cwd, ERROR_LOG)]

    def emit(self, record):
        if record.levelno < logging.ERROR or getattr(record, 'exec_mode', None) == 'FAIL':
            return

        # On the first pass, we will use a verbose header since we are
        ## writing to the raw error log
        header_function = self.create_general_header
        for name in self.error_logs:
            header = header_function(record.levelno, record)
            with open(name, 'a') as fh:
                with _FileLock(fh):
                    fh.seek(0, 2) # goto end of file
                    for line in format_message(record).splitlines():
                        fh.write('{} {}\n'.format(header, line))

                    # This checks for exception, always print to stderr
                    if record.exc_info:
                        header = header_function(EXC_LEVEL, record)
                        if isinstance(record.exc_info, list):
                            lines = record.exc_info
                        else:
                            lines = "".join(traceback.format_exception(*record.exc_info)).splitlines()

                        for line in lines:
                            fh.write('{} {}\n'.format(header, line))
                    fh.flush()
            # After the first pass, switch to the sparse header
            header_function = self.create_sparse_header


class TestLogHandler(STDLogHandler):
    ''' Write to test.log and tester.log

    Writes the same thing to both.   It is up to the caller
    to erase the test.log between calls.
    '''
    def __init__(self, *bares, **keywords):
        super().__init__(*bares, **keywords)
        # Ensure that RAWTEST_LOG remains first for full header output
        self.test_logs = [open(osp.join(self.cwd, RAWTEST_LOG), 'a'),
                          open(osp.join(self.cwd, TESTER_LOG), 'a'),
                          open(osp.join(self.cwd, TEST_LOG), 'a')]

        # logging all to ONFAIL_LOG when running in fail block of sequence
        self.onfail_logs = [self.test_logs[0],
                            open(osp.join(self.cwd, ONFAIL_LOG), 'a')]

    def emit(self, record):
        # On the first pass, we will use a verbose header since we are
        ## writing to the raw test log
        header_function = self.create_general_header
        for fh in self.onfail_logs if getattr(record, 'exec_mode', None) == 'FAIL' else \
                self.test_logs:
            header = header_function(record.levelno, record)
            with _FileLock(fh):
                fh.seek(0, 2) # goto end of file
                for line in format_message(record).splitlines():
                    fh.write('{} {}\n'.format(header, line))

                # This checks for exception, always print to stderr
                if record.exc_info:
                    header = header_function(EXC_LEVEL, record)
                    if isinstance(record.exc_info, list):
                        lines = record.exc_info
                    else:
                        lines = "".join(traceback.format_exception(*record.exc_info)).splitlines()

                    for line in lines:
                        fh.write('{} {}\n'.format(header, line))
                fh.flush()
            # After the first pass, switch to the sparse header
            header_function = self.create_sparse_header


class MBLogHandler(STDLogHandler):
    ''' Write any/all recoreds to mb.log

    Write all records to mb.log.
    '''
    def __init__(self, *bares, **kw):
        super().__init__(*bares, **kw)
        self.mb_file = osp.abspath(osp.join(self.cwd, 'mb.log'))

    def emit(self, record):
        header = self.create_general_header(record.levelno, record)
        with open(self.mb_file, 'a') as fh:
            with _FileLock(fh):
                for line in format_message(record).splitlines():
                    fh.write('{} {}\n'.format(header, line))

                # This checks for exception, always print to stderr
                if record.exc_info:
                    header_e = self.create_general_header(EXC_LEVEL, record)
                    if isinstance(record.exc_info, list):
                        lines = record.exc_info
                    else:
                        lines = "".join(traceback.format_exception(*record.exc_info)).splitlines()

                    for line in lines:
                        fh.write('{} {}\n'.format(header_e, line))
                fh.flush()
                os.fsync(fh.fileno())


class LogDataHandler(logging.Handler):
    ''' Handle writing to logdata.utp

    The format of logdata.utp does not follow the standard format.
    It looks like:
    151106-06:50:12~SEQS~sequence_name.bl2
    151106-06:50:12~OPS~avt
    151106-06:50:20~ATTNS~led-screen
    151106-06:50:21~ATTNE~led-screen
    151106-06:50:22~OPE~avt~FAIL
    151106-06:50:22~SEQE~sequence_name.bl2~FAIL
    '''
    def __init__(self, cwd):
        super().__init__()
        self.cwd = cwd
        self.logdata_utp = osp.join(cwd, LOGDATA_UTP)

    def create_general_header(self, levelno, record):
        return '{}~{}'.format(
            time.strftime(DATE_TIME_FORMAT, time.localtime(record.created)),
            record.tag.strip() if hasattr(record, 'tag') else log_level_to_name[levelno].strip())

    def emit(self, record):
        if record.levelno not in (SEQS_LEVEL, SEQE_LEVEL, OPS_LEVEL, OPE_LEVEL,
                                  ATTNS_LEVEL, ATTNE_LEVEL, DATA_LEVEL, IT_LEVEL):
            return

        for a in record.args:
            assert '\n' not in a, \
                'DATA field {!r} cannot have a newline embedded'.format(a)

        header = self.create_general_header(record.levelno, record)
        with open(self.logdata_utp, 'a') as fh:
            with _FileLock(fh):
                fh.write('{}~{}\n'.format(header, record.msg))


def hook_logging():
    _logger = logging.getLogger()

    # Need to remove any handlers that got auto-added
    for handler in list(_logger.handlers):
        _logger.removeHandler(handler)

    # Always add the STD loggers
    _logger.addHandler(STDLogHandler(owner=osp.basename(sys.argv[0]), cwd='.', scope='local'))
    _logger.addHandler(ErrorLogHandler(owner=osp.basename(sys.argv[0]), cwd='.', scope='local'))
    _logger.addHandler(TestLogHandler(owner=osp.basename(sys.argv[0]), cwd='.', scope='local'))
    _logger.addHandler(LogDataHandler(cwd='.'))
