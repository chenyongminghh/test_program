#!/usr/bin/env python3

import os
import sys
import time
import logging
import argparse
import subprocess
import os.path as osp
from datetime import datetime

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
utilities_path = osp.join(testcode_path, 'utilities')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import CAM

def check_link_ecc_count(mcPort, mcSN, caseName, test_tool):
    dvt_name = 'linkecc'
    log_fname = osp.join(logs_path, '{}/{}'.format(CAM.format_dirname(mcPort, mcSN, 'voltage'), CAM.format_fname(mcPort, mcSN, dvt_name)))
    logging.info('{} Start  on Card{} <{}>'.format(caseName, mcPort, mcSN))
    
    # ./MLU370_Debug_Tool_x86_ecc_print_3e28ae -i x -f 2
    test_cmd = [test_tool, '-i', mcPort, '-f', '2']
    
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d %H:%M:%S")))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('###{} End  on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    if proc.returncode:
        logging.error('{} Failed on Card{} with returncode {}'.format(caseName, mcPort, proc.returncode))
        return False
    return_context = ''
    return_context = proc.stdout.decode('utf-8')
    if "ERROR" in return_context:
        logging.error('{} Failed on Card{}'.format(caseName, mcPort))
        return False
    logging.info('{} Passed on Card{}'.format(caseName, mcPort))
    return True

def main(args):
    case_name = 'mlu370 Check Linkecc'
    logging.info('{}'.format(case_name), section=True)
    
    debug_tool = UTP.get('DEBUG_TOOL', '')
    logging.info('DEBUG Tool {}'.format(debug_tool))
    debug_tool_path = osp.join(utilities_path, debug_tool)
    linkecc_tool_path = osp.join(utilities_path, 'MLU370_Debug_Tool_x86_ecc_print_3e28ae')
    
    test_result = True
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = CAM.get_sn(mcPort)
        if not check_link_ecc_count(mcPort, mcSN, case_name, linkecc_tool_path):
            test_result = False
            CAM.record_card_fail(mcPort, mcSN, case_name, "Linkecc Check Failed")
        
    result = 'PASS' if test_result else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('MFG_FAIL_MODE', None):
        logging.error('{} FAILED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        CAM.record_fail_case(case_name)
        raise Exception('Some failure detected, please check the log.')
    return
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    sys.exit(main(args))
