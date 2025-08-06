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

def st_run_test(caseName, debug_tool, xdpe_version):
    allPassed = True
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = CAM.get_sn(mcPort)
        actual_ver = CAM.read_reg_value(mcPort, debug_tool, '0x00368034')
        logging.info('{} on Card{} : {}'.format(caseName, mcPort, actual_ver))
        if actual_ver != xdpe_version:
            allPassed = False
            failure_message = '{} Failed on Card{}'.format(caseName, mcPort)
            logging.error(failure_message)
            CAM.record_card_fail(mcPort, mcSN, caseName, failure_message)
    return allPassed

def main(args):
    case_name = 'mlu370 Check XDPE Version'
    logging.info('{}'.format(case_name), section=True)
    
    debug_tool = UTP.get('DEBUG_TOOL', '')
    logging.info('DEBUG Tool {}'.format(debug_tool))
    debug_tool_path = osp.join(utilities_path, debug_tool)
    
    if not args.version:
        logging.error('Please specify xdpe version')
        CAM.record_fail_case(case_name)
        raise Exception('Please specify xdpe version')
    xdpe_version = args.version.strip()
    
    result = 'PASS' if st_run_test(case_name, debug_tool_path, xdpe_version) else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('MFG_FAIL_MODE', None):
        logging.error('{} FAILED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case('mlu370 Check Core Voltage')
    else:
        CAM.record_fail_case('mlu370 Check Core Voltage')
        raise Exception('Some failure detected, please check the log.')
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', action='store', help='Please specify xdpe version')
    args = parser.parse_args()
    sys.exit(main(args))
