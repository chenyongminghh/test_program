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

def mt_run_test(caseName, debug_tool, core_voltage):
    allPassed = True
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = CAM.get_sn(mcPort)
        if not CAM.change_core_voltage(mcPort, mcSN, caseName, debug_tool, core_voltage):
            allPassed = False
            failure_message = '{} Failed on Card{}'.format(caseName, mcPort)
            CAM.record_card_fail(mcPort, mcSN, 'mlu370 Change Core Voltage', failure_message)
    return allPassed

def main(args):
    core_voltage = args.voltage.strip() if args.voltage else '70'
    case_name = 'Change Core Voltage to 0.{}V'.format(core_voltage)
    logging.info('{}'.format(case_name), section=True)
    
    debug_tool = UTP.get('DEBUG_TOOL', '')
    logging.info('DEBUG Tool {}'.format(debug_tool))
    debug_tool_path = osp.join(utilities_path, debug_tool)
    
    result = 'PASS' if mt_run_test(case_name, debug_tool_path, core_voltage) else 'FAIL'
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
    parser.add_argument('--voltage', action='store', choices=['65', '66', '67', '68', '69', '70', '72', '74', '80', '81', '85', '86'], help='Board Core Voltage')
    args = parser.parse_args()
    sys.exit(main(args))
