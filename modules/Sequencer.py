#!/usr/local/bin/python35
import os
import os.path as osp
import re
import sys
import time
from datetime import datetime
import json
import shutil
import signal
import tempfile
import traceback
import subprocess
import importlib
import logging
import select
from functools import wraps
from contextlib import suppress

import UTP
import CodeLink
import Misc

# SequenceNodeType
SEQUENCE_NODE_ROOT,\
SEQUENCE_NODE_OPSTART,\
SEQUENCE_NODE_OPSTOP,\
SEQUENCE_NODE_TRUE_BRANCH,\
SEQUENCE_NODE_FALSE_BRANCH,\
SEQUENCE_NODE_PRE_BLOCK,\
SEQUENCE_NODE_POST_BLOCK,\
SEQUENCE_NODE_REGRESS_BLOCK,\
SEQUENCE_NODE_NORMAL_BLOCK,\
SEQUENCE_NODE_FAIL_BLOCK,\
SEQUENCE_NODE_EXEC,\
SEQUENCE_NODE_EXECMT,\
SEQUENCE_NODE_EXIT,\
SEQUENCE_NODE_BREAK,\
SEQUENCE_NODE_IMPORT,\
SEQUENCE_NODE_IFFILE,\
SEQUENCE_NODE_IFNOTFILE,\
SEQUENCE_NODE_IFRC,\
SEQUENCE_NODE_IFVAR,\
SEQUENCE_NODE_IFENV,\
SEQUENCE_NODE_ELSE,\
SEQUENCE_NODE_REPEAT,\
SEQUENCE_NODE_SETLOCAL,\
SEQUENCE_NODE_SETVAR,\
SEQUENCE_NODE_SEARCH,\
SEQUENCE_NODE_START_MARKER,\
SEQUENCE_NODE_ONFAIL,\
SEQUENCE_NODE_ONRC = list(range(28))

# SequenceNodeState
SEQUENCE_NODE_PASSED,\
SEQUENCE_NODE_FAILED,\
SEQUENCE_NODE_RUNNING,\
SEQUENCE_NODE_QUIT = list(range(4))

# SequenceState
SEQUENCE_STATE_PASSED,\
SEQUENCE_STATE_FAILED,\
SEQUENCE_STATE_RUNNING,\
SEQUENCE_STATE_READY,\
SEQUENCE_STATE_INVALID,\
SEQUENCE_STATE_UNINITIALIZED = list(range(6))

# SequenceMode
SEQUENCE_MODE_NORMAL,\
SEQUENCE_MODE_RESUME,\
SEQUENCE_MODE_REGRESS,\
SEQUENCE_MODE_POST_REGRESS = list(range(4))

# SequenceActionType
SEQUENCE_ACTION_CONTINUE,\
SEQUENCE_ACTION_RESTART,\
SEQUENCE_ACTION_EXIT,\
SEQUENCE_ACTION_BREAK,\
SEQUENCE_ACTION_FAIL,\
SEQUENCE_ACTION_QUIT = list(range(6))


FORMATTED_LOG_RE = re.compile(r'^\S+ \d{6}-\d{2}:\d{2}:\d{2} ')


class ITACClient:
    """! Class of iTAC client, communicate with iTAC.MES.Suite - Test System Adapter (TSA)

    @Remark: LCFC MES will also utilize this class for communicating.
    """

    def __init__(self, itac_client=None, verbose=True):
        site = Misc.get_site()
        self.is_mes = site and site.upper() in ('LCFC',)

        if not itac_client:
            itac_client = UTP.find_file('mes_client.py' if self.is_mes else 'itac_client.py',
                                        args=UTP.UTILITY_ARGS)

        self.args = [itac_client,
                     '--serial_number', UTP.get('UWIP_SN'),
                     '--work_order', UTP.get('MONUMBER')
                     ]
        if verbose:
            self.args.append('--verbose')

    def run_cmd(self, op, args_extra):
        """! Execute iTAC/MES command.
        """
        flag_file = 'GroupMap.flg' if self.is_mes else 'itac.flg'
        if not osp.exists(osp.join(UTP.SITE_DIR, flag_file)):
            logging.info('Skip to execute iTAC/MES command ({} not exists)'.format(flag_file))
            return
        elif UTP.get('disable_sfcs', None):
            logging.info('Detected disable_sfcs variable active, skipping iTAC/MES command')
            return

        op = op.lower()
        args = self.args + ['--station', op] + args_extra
        logging.info('Executing iTAC/MES command: {}'.format(args))
        proc = UTP.runproc(args, scope='l1', cwd=UTP.OUR_RT_DIR, universal_newlines=True)

        output = proc.stdout
        if not self.is_mes:
            with open('itac_trace.log', 'a') as itac_log:
                itac_log.write(output)

        # Strip off the date and time header information from the itac_client output logging
        clean_output = re.sub(r'^[-0-9]{10} [:0-9]{8}[,0-9]{0,4} ', '', output, flags=re.MULTILINE)
        if proc.returncode == 0:
            logging.debug(clean_output)
        else:
            logging.error(clean_output)

        proc.stdout = clean_output
        return proc

    def op_start(self, op):
        proc = self.run_cmd(op, ['--begin_test'])
        if proc and proc.returncode != 0:
            raise RuntimeFail(ItemType.itac, 'iTAC/MES OpStart operation was unsuccessful')

    def op_stop(self, op, rc=0):
        op = op.lower()
        args_extra = ['--complete_test']
        if rc:  # if OP fail
            # This will be implemented with TPY changes, currently a no-op
            return
        else:
            if op not in ['avt', 'flashchk', 'pcycle', 'runin', 'fvt', 'mergetest', 'opttest']:
                args_extra.append('--freeze_unit')
            elif op in ['fvt', 'mergetest', 'teardown']:
                if osp.exists('logdata.utp.multi'):
                    args_extra.extend(['--pew_data', 'logdata.utp.multi'])
                else:
                    args_extra.extend(['--pew_data', 'logdata.utp'])

        proc = self.run_cmd(op, args_extra)
        if proc and proc.returncode != 0:
            raise RuntimeFail(ItemType.itac, 'iTAC/MES OpStop operation was unsuccessful')

    def get_attr(self, name, op='avt'):
        proc = self.run_cmd(op, ['--get_attributes', name])
        if proc:
            if proc.returncode != 0:
                raise RuntimeFail(ItemType.itac, 'iTAC/MES GetAttr - {} was unsuccessful'.format(name))

            attrs = {}
            for line in proc.stdout.splitlines():
                line = line.strip()
                if line[0] == '(' and line[-1] == ')':
                    try:
                        attr = eval(line)  # ('MACKIT1', '23S08979869BCA7')
                        if isinstance(attr, tuple) and len(attr) == 2:
                            attrs[attr[0]] = attr[1]
                    except Exception:
                        pass

            return attrs


def SequenceNodeStateToString(state):
    state_to_name = {   0: 'Passed',
                        1: 'Failed',
                        2: 'Running...',
                        3: 'Quit!',
                        }
    return state_to_name.get(state)

def SequenceActionToString(action):
    # SequenceActionType
    action_to_name = {  0: 'CONTINUE',
                        1: 'EXIT',
                        2: 'BREAK',
                        3: 'FAIL',
                        }
    return action_to_name.get(action)

class SequenceRunResult(object):
    def __init__(self, rc, next_action):
        self.rc = rc
        self.next_action = next_action

    def __str__(self):
        return 'SequenceRunResult({}, {})'.format(self.rc, self.next_action)

class SequenceParseError(object):
    def __init__(self, line, description):
        self.line = line
        self.description = description

class SequenceExpressionInfo(object):
    def __init__(self):
        self.tag = ''
        self.content = ''
        self.comment = ''
        self.line = -1
        self.valid = True


def runStatus(fn):
    ''' This decorator is exclusively meant to wrap the run function of a child of the SequenceNode class.
    Any other usage of this is strictly prohibited!

    The purpose of this function is to handle setting and updating each node's status (Running, Pass, Fail)
    and then update the sequence json structure on the file system
    '''
    @wraps(fn)
    def runWrapper(self, *args, **kwargs):
        # Set status for this node to running and update sequence.json...
        self.status = SEQUENCE_NODE_RUNNING
        export_json(self.sequence)

        # Allow the node to run
        rtn = fn(self, *args, **kwargs)

        # Set status according to SequenceRunResult (returned from all Run functions)
        if rtn.next_action in (SEQUENCE_ACTION_CONTINUE, SEQUENCE_ACTION_BREAK):
            self.status = SEQUENCE_NODE_PASSED
        elif rtn.next_action == SEQUENCE_ACTION_FAIL:
            self.status = SEQUENCE_NODE_FAILED
        elif rtn.next_action == SEQUENCE_ACTION_QUIT:
            self.status = SEQUENCE_NODE_QUIT
        # SEQUENCE_ACTION_EXIT not handled ... I'm not sure we should allow the exit statement ?

        # Update sequence.json file once again
        export_json(self.sequence)
        return rtn
    return runWrapper


class SequenceNode(object):
    TRAIT_LOOP = 0
    def __init__(self, sequence, parent, type=None):
        self.sequence = sequence
        self.parent = parent
        self.status = None
        self.type = type
        self.line_start = -1
        self.line_end = -1
        self.comment = ''
        self.valid = True
        self.traits = []
        self.children = []
    @runStatus
    def run(self):
        return SequenceRunResult(0, SEQUENCE_ACTION_CONTINUE)
    def should_run(self):
        return True
    def contains(self, line_number):
        return self.line_start == line_number
    def has_trait(self, trait):
        return trait in self.traits

class SequenceSetStatNode(SequenceNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_SETVAR)
        self.name = None
        self.expression = None
    @runStatus
    def run(self):
        try:
            exec(self.expression, self.sequence.import_namespace, UTP.global_vars())
        except NameError as error:
            logging.error('[Sequence] Invalid reference in setvar expression: {0.expression!r} Error: {1}'\
                              .format(self, error))
            return SequenceRunResult(1, SEQUENCE_ACTION_FAIL)
        except:
            logging.exception('[Sequence] Error evaluating setvar expression {0.expression!r}:'.format(self))
            return SequenceRunResult(1, SEQUENCE_ACTION_FAIL)
        else:
            return SequenceRunResult(0, SEQUENCE_ACTION_CONTINUE)

class SequenceSearchNode(SequenceNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_SEARCH)

class SequenceOnFailNode(SequenceNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_ONFAIL)
    @runStatus
    def run(self):
        return SequenceRunResult(0, SEQUENCE_ACTION_CONTINUE)

class SequenceOnRCNode(SequenceNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_ONRC)
    @runStatus
    def run(self):
        return SequenceRunResult(0, SEQUENCE_ACTION_CONTINUE)

class SequenceExecNode(SequenceNode):
    def __init__(self, sequence, parent, type=None):
        if type is None:
            type = SEQUENCE_NODE_EXEC
        super().__init__(sequence, parent, type=type)

    @runStatus
    def run(self):
        words = self.command.split()
        program_name = ''
        program_opts = ''

        # First and foremost we want to ensure code links are current
        #try:
        #    CodeLink.update_code_links(UTP.get('MT'), UTP.get('MODEL'))
        #except:
        #    logging.exception('[SequenceExecNode] Code Setup failed. ' +\
        #                      'Failing sequence execution')
        #    return SequenceRunResult(3, SEQUENCE_ACTION_FAIL)

        if len(words):
            program_name = words[0]
            program_opts = ' '.join(words[1:])

        result = None
        # Run pre-blocks
        for pre_block in self.sequence.pre_blocks:
            if pre_block.should_run():
                result = pre_block.run()
                if result.next_action != SEQUENCE_ACTION_CONTINUE:
                    return result

        # The GUI will use step, pgmname, etc. for progress
        UTP.set('step', self.line_start)
        UTP.set('step_desc', self.comment)
        UTP.set('pgmname', program_name)
        UTP.set('pgmoptions', program_opts)
        UTP.set('current_pgm_start', time.time())

        # Run Step
        rc = self.execute()
        self.sequence.last_rc = rc

        # See what we should do next
        if os.path.exists('quit.now'):
            # The control file quit.now will cause the process to immediately stop
            # (first allowing test case to complete)
            action = SEQUENCE_ACTION_QUIT
            logging.warn('[SequenceExecNode] Found control file quit.now, exiting')
            os.unlink('quit.now')
            # This counts as signaling the sequence to end
            self.sequence.signaled = True
        elif rc in self.sequence.rc_actions:
            action = self.sequence.rc_actions[rc]
            logging.info('[SequenceExecNode] Return code matches an onrc condition: {!r}'.format(
                SequenceActionToString(action)))
        elif rc == 0:
            # Continue on a good return code
            action = SEQUENCE_ACTION_CONTINUE
        elif self.sequence.state == SEQUENCE_STATE_FAILED:
            # If we're running in a failed state already, just keep going
            action = SEQUENCE_ACTION_CONTINUE
        else:
            # Fail on a bad return code (unless onfail set to CONTINUE)
            self.sequence.fail_lines.append(self.line_start)
            self.sequence.failed_step = self.line_start
            self.sequence.failed_program = program_name
            self.sequence.failed_program_opts = program_opts
            action = SEQUENCE_ACTION_FAIL
            logging.warn('[SequenceExecNode] Return code is non-zero, failing')
            if self.sequence.onfail_mode == SEQUENCE_ACTION_CONTINUE:
                self.sequence.state = SEQUENCE_STATE_FAILED
                # We will intercept this failure, run any fail blocks, then continue
                if self.sequence.mode != SEQUENCE_MODE_REGRESS:
                    UTP.set('regress_step', self.line_start)
                UTP.set('fail_pgmname', program_name)
                UTP.set('fail_pgmoptions', program_opts)
                UTP.set('fail_step', self.line_start)

                if not self.sequence.signaled and self.sequence.fail_blocks:
                    # Run fail blocks
                    UTP.set('exec_mode', 'FAIL')
                    logging.info('[Sequence] Running fail blocks')
                    logging.info('-'*80)
                    for fail_block in self.sequence.fail_blocks:
                        if fail_block.should_run():
                            fail_block.run()
                    UTP.set('exec_mode', 'NORMAL')

                # Restore failing step, program info, and test log
                UTP.set('step', self.line_start)
                UTP.set('pgmname', program_name)
                UTP.set('pgmoptions', program_opts)
                logging.warn('[SequenceExecNode] Continuing sequence since onfail mode is CONTINUE')
                action = SEQUENCE_ACTION_CONTINUE
                self.sequence.state = SEQUENCE_STATE_RUNNING

        if action == SEQUENCE_ACTION_CONTINUE:
            # Run post blocks
            for post_block in self.sequence.post_blocks:
                if post_block.should_run():
                    result = post_block.run()
                    if result.next_action != SEQUENCE_ACTION_CONTINUE:
                        return result

        return SequenceRunResult(rc, action)

    def execute(self):
        command = self.sequence.substitute_variables(self.command)

        # Reset theses files before a command is run
        if UTP.get('exec_mode', None) != 'FAIL':  # not running in fail block of sequence
            with open('test.log', 'w'):
                pass
            with open('error.log', 'w'):
                pass

        # For test logging
        os.environ['SEQ_LINE'] = str(self.line_start)
        os.environ['TEST_CASE'] = self.command

        logging.info('[SequenceExecNode] Executing line {0.line_start}: <{1}>'\
                     .format(self, command))
        rc = 88

        # Use subprocess to execute the command
        # The os.setsid() used as preexec_fn will run after fork() and
        # before exec()
        # Capture the test output with pipes.  The normal test case
        # that uses UTP.py does not present a problem.   Any errors will
        # be logged properly.   The problem is other commands (os,
        # third party) and test cases that never get to the point
        # of running (not found, etc).   In this case it would
        # be nice to capture the stdout/err and log some error messages
        # in the standard logs.   We also need to put the test's
        # output in debug.log.
        # Assume:
        # When this program runs its stdout/err will be redirected
        # to debug.log.   Therefore any logging messages will also
        # end up in debug.log.
        # To avoid  double records we will just print to
        # stdout any testcase output IF it looks
        # like a properly formatted log output.  OTHERWISE
        # we will call the logging.error() or logging.info()
        # to do a proper log of the output so it shows up in
        # the standard places.
        os.environ['PYTHONPATH'] = 'platform/modules'
        proc = subprocess.Popen(command, shell=True,
                                stderr=subprocess.PIPE,
                                bufsize=0,
                                preexec_fn=os.setsid)
        process_id = proc.pid
        if process_id < 0:
            logging.error('[SequenceExecNode] Error forking to executed command')
            rc = 102
            os.environ['TEST_CASE'] = ''
        else:
            UTP.log_test_start(self.command)
            self.sequence.child_pid = process_id
            try:
                rc = proc.wait()  # this should not block because
                                  # stdout/err now closed

                if rc < 0:
                    logging.error('[SequenceExecNode] Error waiting for command: {}'.format(rc))
                    rc = -1

            except KeyboardInterrupt:
                logging.error('[SequenceExecNode] Received Keyboard Interrupt - Terminating Process')
                # proc.terminate() # This will only terminate shell, not its children - use process group
                os.killpg(process_id, signal.SIGINT)
                # Do this or wait()? rc = -1
                rc = proc.wait()
            finally:
                err_output = proc.stderr.read()
                if err_output:
                    logging.error(err_output.decode())

                UTP.log_test_end('PASS' if rc == 0 else 'FAIL', self.command)

                os.environ['TEST_CASE'] = ''

            self.sequence.child_pid = -1

        if rc == -1:
            logging.error('[SequenceExecNode] Error executing command: <{}> rc: {}'.format(command, rc))

        return rc

class SequenceExecMTNode(SequenceExecNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_EXECMT)

    @runStatus
    def run(self):
        current_mt = self.sequence.get_variable('MT')
        # If this system's MT is in the MT list of the execmt call, then execute normally
        if current_mt in self.mtlist:
            return super().run()
        else:
            logging.info("[SequenceExecMTNode] System MT {} not in execmt MT list: {}".format(
                current_mt, self.mtlist))
            return SequenceRunResult(0, SEQUENCE_ACTION_CONTINUE)

class SequenceExitNode(SequenceNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_EXIT)
    @runStatus
    def run(self):
        return SequenceRunResult(0, SEQUENCE_ACTION_EXIT)

class SequenceBreakNode(SequenceNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_BREAK)
    @runStatus
    def run(self):
        return SequenceRunResult(0, SEQUENCE_ACTION_BREAK)

class SequenceStartMarkerNode(SequenceNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_START_MARKER)
    @runStatus
    def run(self):
        return SequenceRunResult(0, SEQUENCE_ACTION_CONTINUE)

class SequenceBranchNode(SequenceNode):
    def __init__(self, sequence, parent, type):
        super().__init__(sequence, parent, type)
        self.children.append(SequenceStartMarkerNode(self.sequence, self))

    @runStatus
    def run(self):
        result = SequenceRunResult(0, SEQUENCE_ACTION_CONTINUE)
        self.sequence.branch_stack.append(self)

        for child in self.children:
            if result.next_action != SEQUENCE_ACTION_CONTINUE:
                break
            if self.sequence.mode == SEQUENCE_MODE_REGRESS:
                if child.line_start == self.sequence.regress_step:
                    self.sequence.mode = SEQUENCE_MODE_POST_REGRESS
            if child.should_run():
                result = child.run()

        self.sequence.branch_stack.pop()
        if self.sequence.state != SEQUENCE_STATE_FAILED and result.next_action == SEQUENCE_ACTION_FAIL:
            self.sequence.fail_lines.append(self.line_start)

        return result

    def should_run(self):
        return True

    def contains(self, line_number):
        if self.line_start == line_number:
            return True
        for child in self.children:
            if child.contains(line_number):
                return True
        return False

class SequenceOpStartNode(SequenceBranchNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_OPSTART)

    def should_run(self):
        if self.sequence.mode == SEQUENCE_MODE_RESUME:
            if self.sequence.previous_operation == self.operation:
                # Resume here
                return True
            else:
                # Skipping past this OP, but previously passed
                self.status = SEQUENCE_NODE_PASSED
                export_json(self.sequence)
                return False
        else:
            return  self.sequence.mode == SEQUENCE_MODE_NORMAL or \
                    self.sequence.mode == SEQUENCE_MODE_POST_REGRESS

    @runStatus
    def run(self):
        if self.sequence.mode == SEQUENCE_MODE_RESUME:
            # For a resume, set mode back to NORMAL (so remaining OPs are not skipped)
            logging.info('[SequenceOpStartNode] Resuming Operation {}'.format(self.operation))
            self.sequence.mode = SEQUENCE_MODE_NORMAL
        else:
            # For normal OP starts, set our Current OP pointer and restart passcount
            UTP.set('op_passcount', 1)
            UTP.set('current_op', self.operation)
            logging.info('[SequenceOpStartNode] Starting Operation {}'.format(self.operation))

        # For test logging
        os.environ['CURRENT_OP'] = self.operation
        os.environ['OP_PASSCOUNT'] = str(UTP.get('op_passcount', 1))

        time_start = '.{}_start'.format(self.operation.lower())
        run_time_var = '{}_TIME'.format(self.operation.upper())
        if UTP.get(time_start, None) is None:
            # Do Start OP stuff only once
            logging.info('[SequenceOpStartNode] Performing first-time OP Start Tasks')

            # Check to ensure we are not in a DEBUG directory -- no floor control hooks if we are
            if UTP.LocalLocation(UTP.our_media_path(), 'local').variables('variables').get('DEBUG_NAME'):
                logging.info('[SequenceOpStartNode] OP Start Tasks aborted due to DEBUG_NAME being set')
            elif self.sequence.onfail_mode not in (None, SEQUENCE_ACTION_FAIL):
                # Also don't hook floor control if the onfail mode is something other than FAIL
                logging.info('[SequenceOpStartNode] OP Start Tasks aborted due to non-default ONFAIL mode')
            elif UTP.get('disable_sfcs', None):
                # Allow the process (or the user) to disable SFCS interaction, like for sub work units
                logging.info('[SequenceOpStartNode] OP Start Tasks aborted due to disable_sfcs being set')
            else:
                # Site Specific operations can go here
                #self.do_site_opstart_tasks()
                pass

            UTP.set(time_start, time.time())
            UTP.log_operation_start(self.operation)

        result = super().run()
        if result.next_action == SEQUENCE_ACTION_CONTINUE and UTP.get(run_time_var, None) is None:
            # Log stop OP stuff and RUNTIME only once
            logging.info('[SequenceOpStartNode] Performing first-time OP Stop Tasks')

            # Check to ensure we are not in a DEBUG directory -- no floor control hooks if we are
            if UTP.LocalLocation(UTP.our_media_path(), 'local').variables('variables').get('DEBUG_NAME'):
                logging.info('[SequenceOpStartNode] OP Stop Tasks aborted due to DEBUG_NAME being set')
            elif self.sequence.onfail_mode not in (None, SEQUENCE_ACTION_FAIL):
                # Also don't hook floor control if the onfail mode is something other than FAIL
                logging.info('[SequenceOpStartNode] OP Stop Tasks aborted due to non-default ONFAIL mode')
            elif UTP.get('disable_sfcs', None):
                # Allow the process (or the user) to disable SFCS interaction, like for sub work units
                logging.info('[SequenceOpStartNode] OP Stop Tasks aborted due to disable_sfcs being set')
            else:
                # Site-specific post-operation steps
                #self.do_site_opstop_tasks()
                pass

            # Calculate total runtime of OP (in HH:MM:SS format)
            cycle_time = datetime.fromtimestamp(time.time()) - datetime.fromtimestamp(UTP.get(time_start))
            mins, secs = divmod(cycle_time.seconds, 60)
            hrs, mins = divmod(mins, 60)
            # Adjust hours for the number of days elapsed (if applicable)
            hrs += (cycle_time.days * 24)
            pretty_runtime = '{:02d}:{:02d}:{:02d}'.format(hrs, mins, secs)
            UTP.set(run_time_var, pretty_runtime)
            UTP.log_data(run_time_var, pretty_runtime, 'PRIVDATA')
            UTP.log_operation_end('PASS', self.operation)

        return result

    def do_site_opstart_tasks(self):
        return ITACClient().op_start(self.operation)

        # If Flex provides any special hooks, we would call them here

    def do_site_opstop_tasks(self):
        return ITACClient().op_stop(self.operation)

        # If Flex provides any special hooks, we would call them here


class SequenceOpStopNode(SequenceNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_OPSTOP)

    def should_run(self):
        return  self.sequence.mode == SEQUENCE_MODE_NORMAL or \
                self.sequence.mode == SEQUENCE_MODE_POST_REGRESS

    @runStatus
    def run(self):
        # Do cleanup stuff
        logging.info('[SequenceOpStopNode] Stopping Operation {}'.format(self.operation))
        return SequenceRunResult(0, SEQUENCE_ACTION_CONTINUE)

class SequenceBlockNode(SequenceBranchNode):
    def __init__(self, sequence, parent, type):
        super().__init__(sequence, parent, type)
    def specifiers_match(self, id):
        if isinstance(id, list):
            sorted_ids = sorted(id)
        else:
            sorted_ids = [id]
        filtered_ids = [val for val in sorted_ids if val in self.specifiers]
        return bool(len(filtered_ids))

class SequenceNormalBlockNode(SequenceBlockNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_NORMAL_BLOCK)
    def should_run(self):
        return  self.sequence.mode == SEQUENCE_MODE_NORMAL or \
                self.sequence.mode == SEQUENCE_MODE_POST_REGRESS

class SequenceFailBlockNode(SequenceBlockNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_FAIL_BLOCK)
    def should_run(self):
        return self.sequence.state == SEQUENCE_STATE_FAILED and (self.specifiers_match('ALL') \
            or self.specifiers_match(self.sequence.fail_lines))

class SequenceRegressBlockNode(SequenceBlockNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_REGRESS_BLOCK)
    def should_run(self):
        return (self.sequence.mode == SEQUENCE_MODE_REGRESS or self.sequence.mode == SEQUENCE_MODE_POST_REGRESS) \
            and (self.specifiers_match('ALL') or self.specifiers_match(self.sequence.regress_type))

class SequencePrePostBlockNode(SequenceBlockNode):
    def __init__(self, sequence, parent, type):
        super().__init__(sequence, parent, type)
    def should_run(self):
        return  not self.sequence.branch_stack_contains(SEQUENCE_NODE_PRE_BLOCK) \
            and not self.sequence.branch_stack_contains(SEQUENCE_NODE_POST_BLOCK) \
            and (self.specifiers_match('ALL') or self.specifiers_match(self.sequence.branch_stack[-1].line_start))

class SequenceRepeatNode(SequenceBranchNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_REPEAT)
        self.iterations = 0
        self.traits.append(self.TRAIT_LOOP)
    @runStatus
    def run(self):
        if UTP.get('exec_mode', None) == 'RESUME':
            # Resume into the previous Repeat Count using passcount
            start = UTP.get('op_passcount')
            if start > self.iterations:
                logging.info('[SequenceRepeatNode] REPEAT Block has expired')
            else:
                logging.info('[SequenceRepeatNode] Resuming REPEAT Block at loop {}'.format(start))
            # Generate a "result" from our previous pass that we are resuming from
            ## This ensures that on our final resume loop, that we can Continue without a reference error
            result = SequenceRunResult(0, SEQUENCE_ACTION_CONTINUE)
        else:
            start = 1
        for count in range(start, self.iterations + 1):
            logging.info('[SequenceRepeatNode] Repeat loop {} out of {}'.format(count, self.iterations))
            result = super().run()
            if result.next_action != SEQUENCE_ACTION_CONTINUE:
                break
        if result.next_action == SEQUENCE_ACTION_BREAK:
            return SequenceRunResult(0, SEQUENCE_ACTION_CONTINUE)
        return result

class SequenceVariableCondition(object):
    def __init__(self, condition, sequence):
        self.condition = condition
        self.sequence = sequence

    def test(self):
        try:
            return eval(self.condition, self.sequence.import_namespace, UTP.global_vars())
        except NameError as err:
            raise RuntimeFail(ItemType.seq,
                              '[SequenceVariableCondition] Condition contains undefined variable: {err}', err=err)

class SequenceEnvironmentCondition(object):
    def __init__(self, condition, sequence):
        self.condition = condition
        self.sequence = sequence

    def test(self):
        try:
            return eval(self.condition, self.sequence.import_namespace, os.environ)
        except NameError as err:
            raise RuntimeFail(ItemType.seq,
                              '[SequenceEnvironmentCondition] Condition contains undefined variable: {err}', err=err)

class SequenceConditionalNode(SequenceNode):
    def __init__(self, sequence, parent, type):
        super().__init__(sequence, parent, type)
        self.true_branch = SequenceBranchNode(sequence, self, SEQUENCE_NODE_TRUE_BRANCH)
        self.false_branch = SequenceBranchNode(sequence, self, SEQUENCE_NODE_FALSE_BRANCH)
    @runStatus
    def run(self):
        is_true = False
        try:
            is_true = self.condition_met()
        except Exception as err:
            logging.error('[Sequence] Error evaluating condition: {}: {}'.format(err.__class__.__name__,
                                                                                err.args[0]))
            return SequenceRunResult(1, SEQUENCE_ACTION_FAIL)

        if is_true:
            result = self.true_branch.run()
        else:
            result = self.false_branch.run()
        return result
    def contains(self, line_number):
        if self.line_start == line_number:
            return True
        return self.true_branch.contains(line_number) or self.false_branch.contains(line_number)

class SequenceIfFileNode(SequenceConditionalNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_IFFILE)
    def condition_met(self):
        return os.path.isfile(self.filepath)

class SequenceIfNotFileNode(SequenceConditionalNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_IFNOTFILE)
    def condition_met(self):
        return not os.path.isfile(self.filepath)

class SequenceIfRCNode(SequenceConditionalNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_IFRC)
        self.rc_condition = 0
    def condition_met(self):
        return self.sequence.last_rc == self.rc_condition

class SequenceIfVarNode(SequenceConditionalNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_IFVAR)
    def condition_met(self):
        return self.condition.test()

class SequenceIfEnvNode(SequenceConditionalNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_IFENV)
    def condition_met(self):
        return self.condition.test()

class SequenceElseNode(SequenceNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_ELSE)

class SequenceImportNode(SequenceNode):
    def __init__(self, sequence, parent):
        super().__init__(sequence, parent, type=SEQUENCE_NODE_IMPORT)
    @runStatus
    def run(self):
        logging.info('[SequenceImportNode] Adding {} to sequence Namespace'.format(self.filename))
        self.sequence.import_namespace[self.filename] = importlib.import_module(self.filename)
        return SequenceRunResult(0, SEQUENCE_ACTION_CONTINUE)


class SequenceParser(object):
    def __init__(self):
        self.in_doublequote = False
        self.line_number = 0
        self.sequence = None
        self.cur_branch = None
        self.tagged_lines = 0
        self.parse_errors = []

    def parse(self, inp_str, sequence, starting_node=None):
        self.sequence = sequence
        if starting_node is None:
            starting_node = SequenceBranchNode(self, None, SEQUENCE_NODE_ROOT)
            self.cur_branch = self.sequence.main_branch
            self.sequence.node_map.clear()
            self.sequence.rc_actions.clear()
            self.sequence.search_paths = []
            self.sequence.parse_errors = []
            self.sequence.fail_blocks = []
            self.sequence.pre_blocks = []
            self.sequence.post_blocks = []
            self.sequence.test_ops = []
        else:
            self.cur_branch = starting_node

        lexer = SequenceLexer(inp_str)
        while lexer.is_more():
            expression_info = lexer.next_expression()
            self.line_number = expression_info.line
            self.parse_errors += lexer.parse_errors
            lexer.parse_errors = []
            self.parse_expression(expression_info)

        # Check for final line (in case there is no trailing newline)
        expression_info = lexer.next_expression()
        self.line_number = expression_info.line
        self.parse_errors += lexer.parse_errors
        lexer.parse_errors = []
        self.parse_expression(expression_info)

        # If we aren't at the root, we have missing :end tags
        while self.cur_branch.parent is not None:
            if isinstance(self.cur_branch, SequenceOpStartNode):
                e = SequenceParseError(self.cur_branch.line_start, 'missing opstop tag')
            else:
                e = SequenceParseError(self.cur_branch.line_start, 'missing end tag')
            self.parse_errors.append(e)
            self.move_up_level()

        return not bool(len(self.parse_errors))

    def parse_expression(self, expression_info):
        if not expression_info.valid:
            return False
        if expression_info.tag == '':
            return True

        # We want to keep a tally of the number of "tagged" lines in the Sequence
        # this should give us an approximation of total "test steps"
        self.tagged_lines += 1

        # Process specific tag type
        if expression_info.tag == 'search':     return self.parse_search_expression(expression_info)
        elif expression_info.tag == 'exec':     return self.parse_exec_expression(expression_info)
        elif expression_info.tag == 'execmt':   return self.parse_execmt_expression(expression_info)
        elif expression_info.tag == 'iffile':   return self.parse_iffile_expression(expression_info)
        elif expression_info.tag == 'ifnotfile':return self.parse_ifnotfile_expression(expression_info)
        elif expression_info.tag == 'ifrc':     return self.parse_ifrc_expression(expression_info)
        elif expression_info.tag == 'ifvar':    return self.parse_ifvar_expression(expression_info)
        elif expression_info.tag == 'ifenv':    return self.parse_ifenv_expression(expression_info)
        elif expression_info.tag == 'onfail':   return self.parse_onfail_expression(expression_info)
        elif expression_info.tag == 'onrc':     return self.parse_onrc_expression(expression_info)
        elif expression_info.tag == 'block':    return self.parse_block_expression(expression_info)
        elif expression_info.tag == 'repeat':   return self.parse_repeat_expression(expression_info)
        elif expression_info.tag == 'exit':     return self.parse_exit_expression(expression_info)
        elif expression_info.tag == 'break':    return self.parse_break_expression(expression_info)
        elif expression_info.tag == 'else':     return self.parse_else_expression(expression_info)
        elif expression_info.tag == 'end':      return self.parse_end_expression(expression_info)
        elif expression_info.tag == 'opstart':  return self.parse_opstart_expression(expression_info)
        elif expression_info.tag == 'opstop':   return self.parse_opstop_expression(expression_info)
        elif expression_info.tag == 'setvar':   return self.parse_setvar_expression(expression_info)
        elif expression_info.tag == 'import':   return self.parse_import_expression(expression_info)
        else:
            e = SequenceParseError(self.line_number, 'unknown tag found: {}'.format(expression_info.tag))
            self.parse_errors.append(e)
            return False

    def move_up_level(self):
        conditional_node = isinstance(self.cur_branch.parent, SequenceConditionalNode)
        if self.cur_branch.parent is not None and not conditional_node:
            # If the current node is nested and not a conditional node
            #  step up one level to node's parent
            self.cur_branch.line_end = self.line_number
            self.cur_branch = self.cur_branch.parent
            return True
        elif self.cur_branch.parent is not None and conditional_node and self.cur_branch.parent.parent is not None:
            # If the current node is nested and is a conditional node
            #  step up two levels (from a conditional branch to the conditional node to the node's parent)
            self.cur_branch.line_end = self.line_number
            self.cur_branch.parent.line_end = self.line_number
            self.cur_branch = self.cur_branch.parent.parent
            return True
        else:
            return False

    def append_node(self, node):
        # Add node as child of current branch
        self.cur_branch.children.append(node)

        # Add node to the line-node map
        if node.line_start in self.sequence.node_map:
            msg = "Duplicate line number ({}): found previously on line {}. This is literally impossible. I can't believe you've done this"
            msg = msg.format(node.line_start, self.sequence.node_map[node.line_start].line_start)
            e = SequenceParseError(self.line_number, msg)
            self.parse_errors.append(e)
            node.valid = False
        else:
            self.sequence.node_map[node.line_start] = node

    def branch_has_trait(self, trait):
        node = self.cur_branch
        if node is None:
            return False

        while node is not None:
            if node.has_trait(trait):
                return True
            node = node.parent
        return False

    def parse_search_expression(self, expression_info):
        ''' A valid search expression is of the form:
            search path
            '''

        valid = True
        # Make sure the path is there
        if not expression_info.content:
            e = SequenceParseError(self.line_number, 'missing directory path after search tag')
            self.parse_errors.append(e)
            valid = False

        self.sequence.search_paths.append(expression_info.content)

        # Build node and add to current branch
        n = SequenceSearchNode(self.sequence, self.cur_branch)
        n.path = expression_info.content
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.line_end = self.line_number
        n.valid = valid
        self.append_node(n)

        return valid

    def parse_onfail_expression(self, expression_info):
        ''' A valid onfail expression is of the form:
              onfail {RESTART|CONTINUE|FAIL}
            NOTE: "onfail FAIL" is normal operation
            '''

        valid = True
        action = SEQUENCE_ACTION_FAIL
        # Split on whitespace
        words = expression_info.content.split()

        # Parse the action
        if not len(words):
            e = SequenceParseError(self.line_number, 'missing instruction after onfail tag')
            self.parse_errors.append(e)
            valid = False

        elif len(words) == 1:
            word = words[0].upper()

            if word == 'CONTINUE':
                action = SEQUENCE_ACTION_CONTINUE
            elif word == 'RESTART':
                action = SEQUENCE_ACTION_RESTART
            elif word != 'FAIL':
                e = SequenceParseError(self.line_number, 'invalid action specified: {}'.format(word))
                self.parse_errors.append(e)
                valid = False
        else:
            e = SequenceParseError(self.line_number, 'too many arguments after tag: expected 1')
            self.parse_errors.append(e)
            valid = False

        if valid:
            if self.sequence.onfail_mode is None:
                # The onfail action isn't already assigned
                self.sequence.onfail_mode = action
            else:
                e = SequenceParseError(self.line_number, 'the onfail action has already been assigned')
                self.parse_errors.append(e)
                valid = False

        # Build node and add to current branch
        n = SequenceOnFailNode(self.sequence, self.cur_branch)
        n.action = action
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.line_end = self.line_number
        n.valid = valid
        self.append_node(n)
        return valid

    def parse_onrc_expression(self, expression_info):
        ''' A valid onrc expression is of the form:
            onrc integer {CONTINUE|EXIT}
            '''

        valid = True
        # Split on whitespace
        words = expression_info.content.split()

        # Parse the return code integer
        rc_integer = None
        if not len(words):
            e = SequenceParseError(self.line_number, 'missing return code after onrc tag')
            self.parse_errors.append(e)
            return False
        else:
            word = words[0]

            # Validate integer
            if not word.isdigit():
                e = SequenceParseError(self.line_number, 'invalid integer after onrc tag: {}'.format(word))
                self.parse_errors.append(e)
                valid = False
            else:
                rc_integer = int(word)

        # Parse the action
        if len(words) < 2:
            e = SequenceParseError(self.line_number, 'missing action after return code')
            self.parse_errors.append(e)
            valid = False
        elif len(words) == 2:
            word = words[1].upper()

            if word == 'CONTINUE':
                action = SEQUENCE_ACTION_CONTINUE
            elif word == 'EXIT':
                action = SEQUENCE_ACTION_EXIT
            else:
                e = SequenceParseError(self.line_number, 'invalid action specified: {}'.format(word))
                self.parse_errors.append(e)
                valid = False
        else:
            e = SequenceParseError(self.line_number, 'too many arguments after tag: expected 2')
            self.parse_errors.append(e)
            valid = False

        if valid:
            if rc_integer not in self.sequence.rc_actions:
                # The return code isn't already assigned
                self.sequence.rc_actions[rc_integer] = action
            else:
                e = SequenceParseError(self.line_number, 'the return code has already been assigned an action')
                self.parse_errors.append(e)
                valid = False

        # Build node and add to current branch
        n = SequenceOnRCNode(self.sequence, self.cur_branch)
        n.rc = rc_integer
        n.action = action
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.line_end = self.line_number
        n.valid = valid
        self.append_node(n)
        return valid

    def parse_exec_expression(self, expression_info):
        ''' A valid exec expression is of the form:
            exec command
            '''

        valid = True
        # Make sure command is there
        if not expression_info.content:
            e = SequenceParseError(self.line_number, 'empty exec expression')
            self.parse_errors.append(e)
            valid = False

        # Build node and add to current branch
        n = SequenceExecNode(self.sequence, self.cur_branch)
        n.command = expression_info.content
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.line_end = self.line_number
        n.valid = valid
        self.append_node(n)
        return valid

    def parse_execmt_expression(self, expression_info):
        ''' A valid execmt expression is of the form:
            execmt 1234,6789 command
            This special exec node will only run on the MTs specified (in this example on 1234 or 6789)
            '''

        valid = True
        # Make sure command is there
        if not expression_info.content or len(expression_info.content.split()) < 2:
            e = SequenceParseError(self.line_number, 'empty execmt expression or missing MT list')
            self.parse_errors.append(e)
            valid = False

        # Build node and add to current branch
        n = SequenceExecMTNode(self.sequence, self.cur_branch)
        n.mtlist, n.command = expression_info.content.split(None, 1)
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.line_end = self.line_number
        n.valid = valid
        self.append_node(n)
        return valid

    def parse_exit_expression(self, expression_info):
        ''' A valid exit expression is of the form:
            exit command
            '''

        valid = True
        # Make sure nothing is following tag
        if expression_info.content:
            e = SequenceParseError(self.line_number, 'unexpected test after exit tag: {}'.format(
                expression_info.content))
            self.parse_errors.append(e)
            valid = False

        # Build node and add to current branch
        n = SequenceExitNode(self.sequence, self.cur_branch)
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.line_end = self.line_number
        n.valid = valid
        self.append_node(n)
        return valid

    def parse_break_expression(self, expression_info):
        ''' A valid break expression is of the form:
            break
            '''

        valid = True
        # Make sure nothing is following tag
        if expression_info.content:
            e = SequenceParseError(self.line_number, 'unexpected text after break tag: {}'.format(
                expression_info.content))
            self.parse_errors.append(e)
            valid = False

        if not self.branch_has_trait(SequenceNode.TRAIT_LOOP):
            # If we aren't inside of a loop
            e = SequenceParseError(self.line_number, 'break tag found outside of a loop {}'.format(
                expression_info.content))
            self.parse_errors.append(e)
            valid = False

        # Build node and add to current branch
        n = SequenceBreakNode(self.sequence, self.cur_branch)
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.line_end = self.line_number
        n.valid = valid
        self.append_node(n)
        return valid

    def parse_iffile_expression(self, expression_info):
        ''' A valid iffile expression is of the form:
            iffile filepath
            '''

        valid = True
        # Parse the filepath to evaluate
        if not expression_info.content:
            e = SequenceParseError(self.line_number, 'missing filepath after iffile tag')
            self.parse_errors.append(e)
            valid = False

        n = SequenceIfFileNode(self.sequence, self.cur_branch)
        n.filepath = expression_info.content
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.true_branch.line_start = self.line_number
        n.valid = valid
        self.append_node(n)
        self.cur_branch = n.true_branch
        return valid

    def parse_ifnotfile_expression(self, expression_info):
        ''' A valid ifnotfile expression is of the form:
            ifnotfile filepath
            '''

        valid = True
        # Parse the filepath to evaluate
        if not expression_info.content:
            e = SequenceParseError(self.line_number, 'missing filepath after ifnotfile tag')
            self.parse_errors.append(e)
            valid = False

        n = SequenceIfNotFileNode(self.sequence, self.cur_branch)
        n.filepath = expression_info.content
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.true_branch.line_start = self.line_number
        n.valid = valid
        self.append_node(n)
        self.cur_branch = n.true_branch
        return valid

    def parse_ifrc_expression(self, expression_info):
        ''' A valid ifrc expression is of the form:
            ifrc integer
            '''

        valid = True
        # Parse the return code integer
        rc_condition = None
        if not expression_info.content:
            e = SequenceParseError(self.line_number, 'missing integer after ifrc tag')
            self.parse_errors.append(e)
            valid = False
        else:
            # Validate integer
            if not expression_info.content.isdigit():
                e = SequenceParseError(self.line_number, 'invalid integer after ifrc tag: {}'.format(
                    expression_info.content))
                self.parse_errors.append(e)
                valid = False
            else:
                rc_condition = int(expression_info.content)

        n = SequenceIfRCNode(self.sequence, self.cur_branch)
        n.rc_condition = rc_condition
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.true_branch.line_start = self.line_number
        n.valid = valid
        self.append_node(n)
        self.cur_branch = n.true_branch
        return valid

    def parse_ifvar_expression(self, expression_info):
        ''' A valid ifvar expression is of the form:
              ifvar [some python expression]
            The namespace used to evaluate the python expression is taken from
            the UTP variables file (UTP.global_vars()) such that any valid python
            expression is also valid here, as long as it is contained on a single line
            '''

        # Parse the condition
        condition = None
        if not expression_info.content:
            e = SequenceParseError(self.line_number, 'missing condition after ifvar tag')
            self.parse_errors.append(e)
        else:
            with suppress(NameError):
                eval(expression_info.content)
            condition = expression_info.content

        n = SequenceIfVarNode(self.sequence, self.cur_branch)
        n.condition = SequenceVariableCondition(condition, self.sequence)
        n.content = expression_info.content
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.true_branch.line_start = self.line_number
        self.append_node(n)
        self.cur_branch = n.true_branch
        return bool(condition)

    def parse_ifenv_expression(self, expression_info):
        ''' A valid ifenv expression is of the form:
              ifenv [some python expression]
            The namespace used to evaluate the python expression is taken from
            the environment variables (os.environ) such that any valid python
            expression is also valid here, as long as it is contained on a single line
            '''

        # Parse the condition
        condition = None
        if not expression_info.content:
            e = SequenceParseError(self.line_number, 'missing condition after ifenv tag')
            self.parse_errors.append(e)
        else:
            with suppress(NameError):
                eval(expression_info.content)
            condition = expression_info.content

        n = SequenceIfEnvNode(self.sequence, self.cur_branch)
        n.condition = SequenceEnvironmentCondition(condition, self.sequence)
        n.content = expression_info.content
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.true_branch.line_start = self.line_number
        self.append_node(n)
        self.cur_branch = n.true_branch
        return bool(condition)

    def parse_block_expression(self, expression_info):
        ''' A valid block expression is of the form:
            block <parameters>
            with parameters:
                MODE=(NORMAL|REGRESS|FAIL|PRE|POST)
                TYPE=TYPE
            '''

        # Split on whitespace
        words = expression_info.content.split()
        specifiers = []
        valid = True

        # Make sure not too many parameters
        if len(words) > 2:
            e = SequenceParseError(self.line_number, 'too many parameters after block tag: expected 2 or less')
            self.parse_errors.append(e)
            valid = False

        # Parse parameters
        node_type = SEQUENCE_NODE_NORMAL_BLOCK
        mode_regex = re.compile('(?:MODE|mode)\s*=\s*(\S+)')
        type_regex = re.compile('(?:TYPE|type)\s*=\s*(\S+)')
        for word in words:
            if mode_regex.match(word):
                mode_str = mode_regex.findall(word)[0].upper()
                if mode_str == 'NORMAL':
                    node_type = SEQUENCE_NODE_NORMAL_BLOCK
                elif mode_str == 'REGRESS':
                    node_type = SEQUENCE_NODE_REGRESS_BLOCK
                elif mode_str == 'FAIL':
                    node_type = SEQUENCE_NODE_FAIL_BLOCK
                elif mode_str == 'PRE':
                    node_type = SEQUENCE_NODE_PRE_BLOCK
                elif mode_str == 'POST':
                    node_type = SEQUENCE_NODE_POST_BLOCK
                else:
                    e = SequenceParseError(self.line_number, 'invalid mode specified: {}'.format(mode_str))
                    self.parse_errors.append(e)
                    valid = False
            elif type_regex.match(word):
                specifiers = type_regex.findall(word)[0].upper().split(',')
            else:
                valid = False
        else:
            if node_type == SEQUENCE_NODE_NORMAL_BLOCK and len(words):
                e = SequenceParseError(self.line_number, 'unrecognized parameters for block: {}'.format(expression_info.content))
                self.parse_errors.append(e)
                valid = False

        # Build node and add to current branch
        if node_type == SEQUENCE_NODE_REGRESS_BLOCK:
            n = SequenceRegressBlockNode(self.sequence, self.cur_branch)
        elif node_type == SEQUENCE_NODE_FAIL_BLOCK:
            fb = SequenceFailBlockNode(self.sequence, self.cur_branch)
            self.sequence.fail_blocks.append(fb)
            n = fb
        elif node_type == SEQUENCE_NODE_PRE_BLOCK:
            fb = SequencePrePostBlockNode(self.sequence, self.cur_branch, node_type)
            self.sequence.pre_blocks.append(fb)
            n = fb
        elif node_type == SEQUENCE_NODE_POST_BLOCK:
            fb = SequencePrePostBlockNode(self.sequence, self.cur_branch, node_type)
            self.sequence.post_blocks.append(fb)
            n = fb
        else:
            n = SequenceNormalBlockNode(self.sequence, self.cur_branch)

        if 'ALL' in specifiers:
            # If ALL was specified, ignore the rest
            n.specifiers = ['ALL']
        else:
            n.specifiers = specifiers
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.valid = valid
        self.append_node(n)

        # This node is now the current branch
        self.cur_branch = n
        return valid

    def parse_repeat_expression(self, expression_info):
        ''' A valid repeat expression is of the form:
            repeat iterations
            '''

        valid = True
        # Make sure repeat count is there
        if not expression_info.content:
            e = SequenceParseError(self.line_number, 'missing count after repeat tag')
            self.parse_errors.append(e)
            valid = False

        # Validate repeat count
        repeat_count = expression_info.content
        if valid and not (repeat_count.isdigit() or self.sequence.get_variable(repeat_count)):
            e = SequenceParseError(self.line_number,
                'invalid integer or non-existant variable after repeat tag: {}'.format(
                    expression_info.content))
            self.parse_errors.append(e)
            valid = False

        count = 0
        if valid:
            if repeat_count.isdigit():
                count = int(expression_info.content)
            else:
                try:
                    count = int(self.sequence.get_variable(repeat_count))
                except ValueError:
                    e = SequenceParseError(self.line_number,
                        'invalid variable value (should be int) after repeat tag: {}={}'.format(
                            repeat_count, self.sequence.get_variable(repeat_count)))
                    self.parse_errors.append(e)
                    valid = False

        # Build node and add to current branch
        n = SequenceRepeatNode(self.sequence, self.cur_branch)
        n.iterations = count
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.valid = valid
        self.append_node(n)

        # This node is now the current branch
        self.cur_branch = n
        return valid

    def parse_else_expression(self, expression_info):
        valid = True
        # Make sure nothing is following tag
        if expression_info.content:
            e = SequenceParseError(self.line_number,
                'unexpected text after else tag: {}'.format(expression_info.content))
            self.parse_errors.append(e)
            valid = False

        n = self.cur_branch.parent
        if n is not None and isinstance(n, SequenceConditionalNode):
            # If we are in a conditional block, move from true branch ("if") to false branch ("else")
            self.cur_branch = n.false_branch
            n.comment = expression_info.comment
            n.false_branch.line_start = self.line_number
            n.true_branch.line_end = self.line_number

            # Now make a dummy Else Node for our node_map to not skip any lines
            dummy = SequenceElseNode(self.sequence, n.parent)
            dummy.line_start = self.line_number
            self.append_node(dummy)
        else:
            # An else tag found not directly inside of a conditional block is an error
            e = SequenceParseError(self.line_number, 'an else tag was found outside of a conditional block')
            self.parse_errors.append(e)
            valid = False

        return valid

    def parse_opstart_expression(self, expression_info):
        ''' A valid opstart expression is of the form:
            opstart operation
            '''

        valid = True
        # Make sure operation name is there
        if not expression_info.content:
            e = SequenceParseError(self.line_number, 'missing operation name after opstart tag')
            self.parse_errors.append(e)
            valid = False

        operation = expression_info.content
        if len(operation.split()) > 1:
            e = SequenceParseError(self.line_number,
                'invalid operation name after opstart tag: {}'.format(operation))
            self.parse_errors.append(e)
            valid = False

        self.sequence.test_ops.append(operation)
        n = SequenceOpStartNode(self.sequence, self.cur_branch)
        n.operation = operation
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.valid = valid
        self.append_node(n)

        # This node is now the current branch
        self.cur_branch = n
        return valid

    def parse_opstop_expression(self, expression_info):
        ''' A valid opstop expression is of the form:
            opstop
            '''

        valid = True
        # Make sure nothing is following tag
        if expression_info.content:
            e = SequenceParseError(self.line_number, 'unexpected text after opstop tag: {}'.format(
                expression_info.content))
            self.parse_errors.append(e)
            valid = False

        if isinstance(self.cur_branch, SequenceOpStartNode):
            current_operation = self.cur_branch.operation
        else:
            current_operation = None

        if not isinstance(self.cur_branch, SequenceOpStartNode) or not self.move_up_level():
            # There were no open nested levels left, or we landed in a non opstart branch (broken nesting)
            e = SequenceParseError(self.line_number, 'an opstop tag was found without a matching opstart tag')
            self.parse_errors.append(e)
            valid = False

        # Now add the opstop node to perform operation cleanup actions
        n = SequenceOpStopNode(self.sequence, self.cur_branch)
        n.operation = current_operation
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.line_end = self.line_number
        n.valid = valid
        self.append_node(n)

        return valid

    def parse_end_expression(self, expression_info):
        valid = True
        # Make sure nothing is following tag
        if expression_info.content:
            e = SequenceParseError(self.line_number, 'unexpected text after end tag: {}'.format(
                expression_info.content))
            self.parse_errors.append(e)
            valid = False

        if isinstance(self.cur_branch, SequenceOpStartNode):
            # There is a missing opstop tag somewhere
            e = SequenceParseError(self.line_number, 'an end tag was found instead of a matching opstop tag')
            self.parse_errors.append(e)
            valid = False
        # Try moving up one nested level
        if not self.move_up_level():
            # There were no open nested levels left
            e = SequenceParseError(self.line_number, 'an end tag was found without a matching starting tag')
            self.parse_errors.append(e)
            valid = False

        return valid

    def parse_setvar_expression(self, expression_info):
        ''' A valid setvar expression is of the form:
              setvar name [pythonic assignment expression]
            Note that the assignment expression can reference other UTP global variables, as well as support
            python objects like None, True, False in addition to numbers and strings.
            '''

        valid = True
        # Split on first whitespace only
        words = expression_info.content.split(None, 1)
        word_regex = re.compile('\S+')

        # Parse the name
        word = name = expression = ''
        if len(words) < 1:
            e = SequenceParseError(self.line_number, 'missing variable name after setvar tag')
            self.parse_errors.append(e)
            return False
        else:
            word = words[0]
            # Validate name
            if not word_regex.match(word):
                e = SequenceParseError(self.line_number, 'invalid variable after setvar tag: {}'.format(word))
                self.parse_errors.append(e)
                valid = False
            else:
                name = word

        # Parse the value
        if len(words) < 2:
            e = SequenceParseError(self.line_number, 'missing value after variable name')
            self.parse_errors.append(e)
            valid = False
        elif '=' not in words[1].split()[0]:
            e = SequenceParseError(self.line_number, 'missing assignment operator (=, +=, etc) after var name')
            self.parse_errors.append(e)
            valid = False
        else:
            # Do not exec until runtime (for the case of referencing UTP globals)
            expression = expression_info.content
            try:
                # This flushes out syntax errors at parse time and ignores variables names not yet created
                with suppress(NameError):
                    # The empty dict ensures we don't affect the current namespace
                    exec(expression, {})
            except SyntaxError as error:
                e = SequenceParseError(self.line_number,
                                       'invalid assignment expression: {}. Error: {}'.format(
                                           expression, error))
                self.parse_errors.append(e)
                valid = False

        # Build node and add to current branch
        n = SequenceSetStatNode(self.sequence, self.cur_branch)
        n.name = name
        n.expression = expression
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.line_end = self.line_number
        n.valid = valid
        self.append_node(n)
        return valid

    def parse_import_expression(self, expression_info):
        ''' A valid exec expression is of the form:
            import filename
            '''

        valid = True
        # Make sure filename is there
        if not expression_info.content:
            e = SequenceParseError(self.line_number, 'empty import expression')
            self.parse_errors.append(e)
            valid = False

        # Build node and add to current branch
        n = SequenceImportNode(self.sequence, self.cur_branch)
        n.filename = expression_info.content
        n.comment = expression_info.comment
        n.line_start = self.line_number
        n.line_end = self.line_number
        n.valid = valid
        self.append_node(n)
        return valid


class SequenceLexer(object):
    def __init__(self, inp_str):
        self.inp_str = inp_str
        self.parse_errors = []
        self.inp_lines = inp_str.split('\n')
        self.last_line = len(self.inp_lines)
        self.line = 1
        self.determine_context()

    @property
    def cur_line(self):
        return self.inp_lines[self.line-1].strip()

    def reset(inp_str=None):
        if inp_str is not None:
            self.inp_str = inp_str
            self.inp_lines = inp_str.split('\n')
            self.last_line = len(self.inp_lines)
        self.line = 1
        self.determine_context()

    def next_expression(self):
        ''' A valid expression is of the form:
              tag content
            Only the tag is required in a general expression. (Specific tag types have addt'l req's).
            '''

        expression_info = SequenceExpressionInfo()
        expression_info.line = self.line
        content_start = None

        # Parse the ID and tag if the line isn't a comment
        if self.cur_line and self.cur_line[0] != '#':
            if ':' in self.cur_line.split()[0]:
                # This is a relic of the legacy Sequence format, inform user
                expression_info.valid = False
                self.parse_errors.append(SequenceParseError(self.line,
                    'IDs are no longer supported and sequence tags do not need a leading colon'))
            else:
                expression_info.tag = self.cur_line.split()[0].strip()
                content_start = self.cur_line.index(expression_info.tag) + len(expression_info.tag)

        # Check for comment at end of line
        comment_start = None
        if '#' in self.cur_line:
            # Found pound sign(s) - find one that's not inside quotes
            pound_idx = self.cur_line.find('#')
            while pound_idx != -1:
                if self.determine_context(pound_idx):
                    pound_idx = self.cur_line.find('#', pound_idx + 1)
                else:
                    break
            if pound_idx != -1:
                # Found a comment designator outside of quotes
                comment_start = pound_idx
        if comment_start is not None:
            expression_info.comment = self.cur_line[comment_start + 1:].strip()
        else:
            expression_info.comment = ''

        # Parse content
        expression_info.content = self.cur_line[content_start:comment_start].strip()
        self.advance()

        # Debug output
        # logging.debug('[{}] [{}] [{}] [{}]'.format(expression_info.line, expression_info.tag,
            # expression_info.content, expression_info.comment))

        return expression_info

    def advance(self):
        if self.line != self.last_line:
            self.line += 1
            self.determine_context()
            return True
        else:
            return False

    def determine_context(self, idx=None):
        ''' This function checks the validity of quotes on the current line.
        Optionally accepts an index parameter, which will return True if the specified index
        is inside of a quote block.
        '''

        quotes = self.cur_line.count('"')
        if quotes%2:
            self.parse_errors.append(SequenceParseError(self.line, 'missing matching \'"\''))
            return False
        if idx is not None and quotes:
            # Determine if this index is inside quotes
            quote_idx = 0
            while quote_idx != -1:
                quote1 = self.cur_line.find('"', quote_idx)
                if quote1 == -1:
                    break
                quote2 = self.cur_line.find('"', quote1 + 1)
                quote_idx = quote2 + 1
                if idx < quote1:
                    return False
                elif quote1 <= idx <= quote2:
                    return True
        return False

    def is_more(self):
        return self.line != self.last_line


class SequenceEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, SequenceExecNode):
            return dict(command=obj.command, comment=obj.comment,
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequenceSetStatNode):
            return dict(comment='Set Variable {0.expression!r}'.format(obj),
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequenceOpStartNode):
            return dict(comment='OpStart {0.operation}'.format(obj),
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequenceNormalBlockNode):
            return dict(comment='NORMAL Block',
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequenceFailBlockNode):
            return dict(comment='FAIL Block',
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequenceRegressBlockNode):
            return dict(comment='REGRESS Block',
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequencePrePostBlockNode):
            return dict(comment='PRE/POST Block',
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequenceRepeatNode):
            return dict(comment='Repeat {0.iterations}'.format(obj),
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequenceIfFileNode):
            return dict(comment='if file {0.filepath}'.format(obj),
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequenceIfNotFileNode):
            return dict(comment='if not file {0.filepath}'.format(obj),
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequenceIfRCNode):
            return dict(comment='if previous RC={0.rc_condition}'.format(obj),
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequenceIfVarNode):
            return dict(comment='if var {0.content}'.format(obj),
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequenceIfEnvNode):
            return dict(comment='if env {0.content}'.format(obj),
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequenceElseNode):
            return dict(comment='else',
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, (SequenceSearchNode, SequenceOnFailNode, SequenceOnRCNode,
            SequenceExitNode, SequenceBreakNode, SequenceImportNode, SequenceOpStopNode)):
            return None  # Ignored sequence tags
        elif isinstance(obj, SequenceBranchNode):
            return dict(comment='Unhandled Branch!',
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, SequenceNode):
            return dict(comment=obj.comment,
                parent=obj.parent.line_start, status=SequenceNodeStateToString(obj.status))
        elif isinstance(obj, Sequence):
            return obj.node_map

        return json.JSONEncoder.default(self, obj)


class Sequence(object):
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.main_branch = SequenceBranchNode(self, None, SEQUENCE_NODE_ROOT)
        self.node_map = {}
        self.import_namespace = {}
        self.rc_actions = {}
        self.onfail_mode = None
        self.fail_lines = []
        self.branch_stack = []
        self.search_paths = []
        self.parse_errors = []
        self.fail_blocks = []
        self.pre_blocks = []
        self.post_blocks = []
        self.test_ops = []
        self.state = SEQUENCE_STATE_UNINITIALIZED
        self.mode = SEQUENCE_MODE_NORMAL
        self.last_rc = 0
        self.test_steps = 0
        self.signaled = False
        self.child_pid = -1
        self.failed_program = None
        self.failed_program_opts = None
        self.failed_step = None
        self.previous_operation = None

    def __iter__(self):
        ''' Making this class iterable allows us to step over each line in the sequence file
            as opposed to running the sequence and encountering a logic branch that forces us
            down a path of execution - thereby avoiding needing to parse the file again to
            understand the contents of the sequence (eg, generating a json.seq representation)
        '''

        for line_num in sorted(self.node_map):
            yield self.node_map[line_num]

    def get_node_by_line(self, line_number):
        return self.node_map.get(line_number)

    def get_containing_block(self, node):
        if node is None:
            return None

        parent_block = None
        parent = node

        # Find outermost block containing the given node
        while parent is not None:
            parent = parent.parent
            # Check if the parent is a block
            if isinstance(parent, SequenceBlockNode):
                # If parent is a block
                parent_block = parent

        return parent_block

    def parse_file(self, filename, starting_node=None):
        try:
            infile = UTP.open_file(filename, args=UTP.SEQUENCE_ARGS)

        except IOError:
            logging.error('[Sequence] Error opening {}'.format(filename))
            return False

        return self.parse_string(infile.read(), starting_node)

    def parse_string(self, in_str, starting_node=None):
        parser = SequenceParser()
        valid = parser.parse(in_str, self, starting_node)
        self.parse_errors = parser.parse_errors
        self.test_steps = parser.tagged_lines

        if valid:
            self.state = SEQUENCE_STATE_READY
            export_json(self)
        else:
            self.state = SEQUENCE_STATE_INVALID
        return valid

    def print_errors(self):
        for error in self.parse_errors:
            logging.error('[Sequence] ERROR on line {0.line}: {0.description}'.format(error))

    def run(self):
        try:
            # Check if error blocked flag was set in iTAC?
            #itac_attr = ITACClient().get_attr('ERROR_BLOCKED')
            #if itac_attr and itac_attr.get('ERROR_BLOCKED'):
            #    raise RuntimeFail(ItemType.process, 'ERROR_BLOCKED flag was set in iTAC, please submit error detail first')

            if self.state != SEQUENCE_STATE_READY:
                raise RuntimeFail(ItemType.seq, '[Sequence] The loaded sequence is invalid and cannot be run')
            # Set up the environment
            for search_path in self.search_paths:
                search_path = self.substitute_env_variables(search_path)
                if not search_path:
                    continue
                rc = self.add_to_path(search_path)

            # Clear fail state
            self.fail_lines = []
            # Determine sequence mode
            regress = self.get_variable('regress')
            if regress == 'YES':
                self.mode = SEQUENCE_MODE_REGRESS
            else:
                self.mode = SEQUENCE_MODE_NORMAL

            # Set Regress type
            if self.mode == SEQUENCE_MODE_REGRESS:
                self.regress_type = self.get_variable('regress_type')
                self.regress_step = self.get_variable('regress_step')
                logging.info(
                    '[Sequence] Regressing to step <{0.regress_step}> with regress type <{0.regress_type}>'.format(
                        self))

                if self.regress_step:
                    if not self.main_branch.contains(self.regress_step):
                        raise RuntimeFail(ItemType.seq, '[Sequence] Regress step <{regress_step}> is not found in the sequence', regress_step=self.regress_step)

                    # Change regress_step to the outermost block containing the step, if there is one
                    outermost_block = self.get_containing_block(self.get_node_by_line(self.regress_step))
                    if outermost_block is not None:
                        logging.info('[Sequence] Regress step <{}> is contained in block <{}>'.format(
                            self.regress_step, outermost_block.line_start))
                        logging.info('[Sequence] Reassigning regress step to <{}>'.format(
                            outermost_block.line_start))
                        self.regress_step = outermost_block.line_start
                else:
                    logging.info(
                        '[Sequence] Regress step is blank, will resume normal mode at first non-regression step')
                    self.mode = SEQUENCE_MODE_POST_REGRESS
            else:
                self.regress_type = ''
                self.regress_step = ''

            self.previous_operation = self.get_variable('current_op')
            if self.mode == SEQUENCE_MODE_NORMAL and self.previous_operation is not None \
                and self.previous_operation in self.test_ops:
                # This is a "resume" - Update passcount (reset for fails, else increment)
                if self.get_variable('prcstat') == 'FAILED':
                    UTP.set('op_passcount', 1)
                else:
                    logging.info('self.previous_operation={}'.format(self.previous_operation))
                    logging.info('self.test_ops={}'.format(self.test_ops))
                    logging.info('op_passcount={}'.format(UTP.get('op_passcount')))
                    UTP.increment('op_passcount')
                    logging.info('op_passcount={}'.format(UTP.get('op_passcount')))

                # This mode will resume right into the OP that was running
                self.mode = SEQUENCE_MODE_RESUME
                UTP.set('exec_mode', 'RESUME')
            else:
                UTP.set('op_passcount', 1)
                UTP.set('exec_mode', 'NORMAL')

            # This super loop will only ever occur on failures with onfail mode set to REPEAT
            while True:
                UTP.set('prcstat', 'RUNNING')
                UTP.delete('regress')
                self.state = SEQUENCE_STATE_RUNNING

                result = self.main_branch.run()
                if result.next_action in [SEQUENCE_ACTION_FAIL, SEQUENCE_ACTION_QUIT]:
                    self.state = SEQUENCE_STATE_FAILED

                    if len(self.fail_lines) and self.mode != SEQUENCE_MODE_REGRESS:
                        UTP.set('regress_step', self.fail_lines[-1])
                    UTP.set('fail_pgmname', self.failed_program)
                    UTP.set('fail_pgmoptions', self.failed_program_opts)
                    UTP.set('fail_step', self.failed_step)

                    if not self.signaled and self.fail_blocks:
                        # Run fail blocks
                        UTP.set('exec_mode', 'FAIL')
                        logging.info('[Sequence] Running fail blocks')
                        logging.info('-'*80)
                        for fail_block in self.fail_blocks:
                            if fail_block.should_run():
                                fail_block.run()
                        UTP.set('exec_mode', 'NORMAL')

                    # Restore failing step, program info and test log
                    UTP.set('step', self.failed_step)
                    UTP.set('pgmname', self.failed_program)
                    UTP.set('pgmoptions', self.failed_program_opts)
                    UTP.set('prcstat', 'FAILED')

                    if self.onfail_mode == SEQUENCE_ACTION_RESTART and result.next_action == SEQUENCE_ACTION_FAIL:
                        # Special condition where we want to restart sequence, so move to next iter of super loop
                        logging.warn('[Sequence] Restarting sequence since onfail mode is RESTART')
                        UTP.set('op_passcount', 1)
                    else:
                        return 1

                elif self.mode == SEQUENCE_MODE_REGRESS:
                    # If we got the end of the sequence but we're still in regression mode, fail
                    raise RuntimeFail(ItemType.seq, '[Sequence] Sequence ended without exiting regression mode')
                else:
                    self.state = SEQUENCE_STATE_PASSED
                    UTP.set('prcstat', 'PASSED')
                    return 0
        except:
            logging.error(traceback.format_exc())
            self.state = SEQUENCE_STATE_FAILED
            UTP.set('prcstat', 'FAILED')
            UTP.set('step', 'ERR')
            UTP.set('pgmname', 'CALL_TE')
            return 101

    def get_variable(self, name, rethrow=False):
        result = None
        try:
            result = UTP.get(name)
        except (UTP.UTPVariableNotSet, KeyError):
            if rethrow:
                raise
        except:
            if rethrow:
                raise
            logging.exception('[Sequence] Error getting variable <{}>'\
                              .format(name))

        if result is None:
            logging.debug('[Sequence] variable <{}> is referenced but not set'
                         .format(name))
        return result

    def set_variable(self, name, value, rethrow=False):
        rc = 0
        try:
            UTP.set(name, value)
        except:
            rc = -1
            if rethrow:
                raise
            logging.exception('[Sequence] Error getting variable <{}>:'\
                              .format(name))

        return rc

    def substitute_variables(self, inp_str):
        # Replace %{VARIABLE_NAME} with corresponding variable value
        variable_placeholder = re.compile('%\{\s*(\S+)\s*\}')

        for variable in variable_placeholder.findall(inp_str):
            # Coerce this value to a str since we are subbing into other strings (sequence exec lines)
            value = str(self.get_variable(variable))
            if value is None:
                logging.debug('[Sequence] The variable <{}> is referenced but not set'.format(variable))
                value = ''
            inp_str = variable_placeholder.sub(value, inp_str, 1)

        return inp_str

    def substitute_env_variables(self, inp_str):
        # Replace ${VARIABLE_NAME} with corresponding env variable value
        variable_placeholder = re.compile('[$]\{\s*(\S+)\s*\}')

        for variable in variable_placeholder.findall(inp_str):
            value = os.environ.get(variable)
            if value is None:
                logging.debug('[Sequence] The ENV variable <{}> is referenced but not set'.format(variable))
                value = ''
            inp_str = variable_placeholder.sub(value, inp_str, 1)

        return inp_str

    def add_to_path(self, name):
        try:
            file_info = os.stat(name)
        except OSError:
            logging.error('[Sequence] Error getting file info. Check if <{}> exists'.format(name))
            return -1
        if os.path.isdir(name):
            logging.debug('[Sequence] Adding "{}" to the PATH'.format(name))
            os.environ['PATH'] = os.environ.get('PATH') + os.pathsep + name
        else:
            # This is a file containing search paths to add
            logging.info('[Sequence] Reading search path table: {}'.format(name))
            sp_file = open(name)
            for each_line in sp_file:
                # Chomp off any comments (designated by #)
                self.add_to_path(each_line.split('#', 1)[0].strip())
            sp_file.close()
        return 0

    def branch_stack_contains(self, type):
        for branch in self.branch_stack:
            if isinstance(type, str):
                if branch.contains(type):
                    return True
            else:
                if branch.type == type:
                    return True
        return False


def export_json(parsed_sequence):
    if not isinstance(parsed_sequence, Sequence):
        raise RuntimeFail(ItemType.seq, 'Expecting a Sequence Object for export_json function call')

    tempfd, temp_path = tempfile.mkstemp(text=True, dir='.')
    with os.fdopen(tempfd, 'w') as tempfh:
        # Write our json file out to a temp file
        json.dump(parsed_sequence, tempfh, cls=SequenceEncoder, indent=4, sort_keys=True)
    # Finally replace sequence.json with our temp file for an atomic update
    os.replace(temp_path, 'sequence.json')
    os.chmod('sequence.json', 0o666)


def main():
    test_sequence = Sequence(True)
    logging.info('Parsing Sequence {}'.format(sys.argv[1]))
    if not test_sequence.parse_file(sys.argv[1]):
        test_sequence.print_errors()
    elif len(sys.argv) > 2 and sys.argv[2] == '--run':
        test_sequence.run()


if __name__ == '__main__':
    main()
