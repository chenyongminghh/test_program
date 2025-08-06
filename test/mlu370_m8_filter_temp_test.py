#!/usr/bin/env python3

import os
import sys
import time
import signal
import logging
import argparse
import subprocess
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
utilities_path = osp.join(testcode_path, 'utilities')
logs_path = osp.join(testcode_path, 'logs')
sys.path.append(modules_path)
import UTP
import CAM

def run_nos_test():
    test_result = True
    pfa_job = None
    try:
        # Run Monitor
        pfa_command = ['python3', 'tests/bmc_monitor_temp.py']
        pfa_job = UTP.runpopen(pfa_command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=testcode_path)
        logging.info('Starting monitor temperature')
        logging.info('Monitor PID={}'.format(pfa_job.pid))
        
        # Run Maxpower
        power_command = ['python3', 'tests/mlu370_power_fix_maxpower.py', '--dimz', '100']
        nos = UTP.runproc(power_command, cwd=testcode_path, log_stdout=logging.DEBUG)
        if nos.returncode:
            test_result = False
            logging.error('Maxpower Test Failed with returncode <{}>'.format(nos.returncode))
        else:
            logging.info('Maxpower Test Passed')
    except:
        test_result = False
    finally:
        if pfa_job:
            kill_process(pfa_job.pid)
            try:
                logging.info("Waiting <30> seconds while PFA completes...")
                pfa_job.wait(timeout=30)
            except subprocess.TimeoutExpired:
                logging.info("Waiting another <30> seconds while PFA completes...")
                pfa_job.wait(timeout=30)
    
    return test_result
    
def kill_process(pid):
    parent_pid = '{}'.format(pid)
    logging.info('Killing PID {}'.format(parent_pid))
    os.kill(int(parent_pid),signal.SIGTERM)

def kill_child_process(pid):
    parent_pid = '{}'.format(pid)
    ps_command = UTP.runproc(['ps','-o','pid','--ppid',parent_pid,'--noheaders'],scope='uut')
    child_pid = '{}'.format(int(ps_command.stdout))
    logging.info('Killing child PID {} from Parent PID {}'.format(child_pid,parent_pid))
    os.kill(int(child_pid),signal.SIGTERM)

def main(args):
    case_name = 'mlu370 M8 Temperature Filter Test'
    logging.info('{}'.format(case_name), section=True)
    
    all_passed = run_nos_test()
    
    result = 'PASS' if all_passed else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        CAM.record_fail_case(case_name)
        raise Exception('Some failure detected, please check the log.')
    return
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dimz', action='store', help='Dimz loops')
    args = parser.parse_args()
    sys.exit(main(args))

