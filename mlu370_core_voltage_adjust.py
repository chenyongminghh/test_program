#!/usr/bin/env python3

import os
import sys
import time
import logging
import argparse
import subprocess
import os.path as osp
import multiprocessing as mp
from datetime import datetime
from collections import OrderedDict

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
utilities_path = osp.join(testcode_path, 'utilities')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import CAM

def x8_pcie_linkdown_test(q, mcPort, caseName, mc_dict, test_tool, loops, overall='pcie-test', gen1=False, timeout=7200):
    mcPort = str(mcPort)
    mcSN = mc_dict[mcPort]
    case_name_format = caseName.ljust(len(caseName))
    
    if CAM.check_card_fail(mcPort, mcSN):
        logging.info('{} Skiped on Card{}'.format(case_name_format, mcPort))
        return q.put(True)
    
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    log_fname = osp.join(logs_path, '{}/{}'.format(CAM.format_dirname(mcPort, mcSN, overall), CAM.format_fname(mcPort, mcSN, dvt_name='linkdown')))
    
    start_time = datetime.now()
    test_cmd = [test_tool, '-i', mcPort, '-D', '370', '-t', '1', '-L', '5', '-b', '-l', loops, '-g', '4']
    if gen1:
        test_cmd = [test_tool, '-i', mcPort, '-D', '370', '-t', '1', '-L', '5', '-b', '-l', loops, '-g', '1']
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('###{} End  on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    
    if proc.returncode:
        failure_message = 'Failed on Card{} with returncode {}'.format(mcPort, proc.returncode)
        logging.error('{} {}'.format(case_name_format, failure_message))
        CAM.record_card_fail(mcPort, mcSN, caseName, failure_message)
        return q.put(False)
    logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    return q.put(True)

def linkdown(mcPort, mcSN):
    caseName = 'PCIE Link Down Test'
    pcie_tool = UTP.get('PCIE_TOOL', '')
    pcie_tool_path = osp.join(utilities_path, pcie_tool)
    gen1 = False
    overall='pcie-test'
    
    mcPort = str(int(mcPort)-1) if int(mcPort) % 2 == 1 else mcPort
    mc_dict = dict()
    mc_dict[mcPort] = mcSN
    q = mp.Queue()
    if mcSN.startswith('77') or mcSN.startswith('78'):
        p = mp.Process(target=x8_pcie_linkdown_test, args=(q, mcPort, caseName, mc_dict, pcie_tool_path, '1', overall, gen1))
    else:
        p = mp.Process(target=CAM.pcie_linkdown_test, args=(q, mcPort, caseName, mc_dict, pcie_tool_path, '1', overall, gen1))
    p.start()
    p.join()
    res = q.get()
    if not res:
        return False
    return True

def mt_run_test(caseName, debug_tool):
    allPassed = True
    mcPorts = CAM.detected_mlu370()
    
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = CAM.get_sn(mcPort)
        
        old_voltage = CAM.read_core_voltage(mcPort, debug_tool)
        if old_voltage == 0 or old_voltage not in [70, 74]:
            allPassed = False
            failure_message = 'Read Core Voltage {} Failed on Card{}'.format(old_voltage, mcPort)
            CAM.record_card_fail(mcPort, mcSN, caseName, failure_message)
            continue
        
        board_type = CAM.get_mlu370_type(mcPort)
        if old_voltage == 74 or old_voltage == 73:
            new_voltage = 75
        elif board_type in ['S4', 'S8']:
            new_voltage = 72
        elif board_type in ['X4', 'X4L', 'X9', 'X9L']:
            new_voltage = 74
        else:
            allPassed = False
            failure_message = 'Adjust Core Voltage {} Failed on Card{}'.format(old_voltage, mcPort)
            CAM.record_card_fail(mcPort, mcSN, caseName, failure_message)
            continue
        
        if not CAM.change_core_voltage(mcPort, mcSN, '{} to 0.{}V'.format(caseName, str(new_voltage)), debug_tool, str(new_voltage)):
            allPassed = False
            failure_message = 'Change Core Voltage Failed on Card{}'.format(mcPort)
            CAM.record_card_fail(mcPort, mcSN, caseName, failure_message)
            continue
        res_linkdown = linkdown(mcPort, mcSN)
        time.sleep(5)
        if not res_linkdown:
            allPassed = False
            failure_message = 'Linkdown Failed on Card{}'.format(mcPort)
            CAM.record_card_fail(mcPort, mcSN, caseName, failure_message)
            continue
        if new_voltage != CAM.read_core_voltage(mcPort, debug_tool):
            allPassed = False
            failure_message = 'Check Core Voltage Failed on Card{}'.format(mcPort)
            CAM.record_card_fail(mcPort, mcSN, caseName, failure_message)
    return allPassed

def main(args):
    case_name = 'mlu370 Core Voltage Adjust'
    logging.info('{}'.format(case_name), section=True)
    
    debug_tool = UTP.get('DEBUG_TOOL', '')
    logging.info('DEBUG Tool {}'.format(debug_tool))
    debug_tool_path = osp.join(utilities_path, debug_tool)
    
    result = 'PASS' if mt_run_test(case_name, debug_tool_path) else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case('mlu370 Change Core Voltage')
    else:
        CAM.record_fail_case('mlu370 Change Core Voltage')
        raise Exception('Some failure detected, please check the log.')
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    sys.exit(main(args))
