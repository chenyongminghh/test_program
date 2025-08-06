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

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
utilities_path = osp.join(testcode_path, 'utilities')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import CAM

def pcie_link_down(mcPort, mcSN):
    caseName = 'PCIE Link Down Test'
    pcie_tool = UTP.get('PCIE_TOOL', '')
    pcie_tool_path = osp.join(utilities_path, pcie_tool)
    overall='pcie-test'
    gen1 = False
    
    mc_dict = dict()
    if mcSN.startswith('54', 0, 2):
        mcPort = str(int(mcPort)//2)
        mc_dict[mcPort] = mcSN
        linkdown_res = CAM.x8_pcie_linkdown_test(mcPort, caseName, mc_dict, pcie_tool_path, '1', overall, gen1)
    else:
        mc_dict[mcPort] = mcSN
        linkdown_res = CAM.x4_pcie_linkdown_test(mcPort, caseName, mc_dict, pcie_tool_path, '1', overall, gen1)
    return linkdown_res

def check_cpm_count(mcPort, mcSN, debug_tool):
    cpm_count = CAM.get_cpm_count(mcPort)
    cpm_count = int(cpm_count) if cpm_count else 0
    logging.info('{}_dev{} cpm count is {}'.format(mcSN, mcPort, cpm_count))
    if cpm_count == 0:
        return False
    elif cpm_count < 40:
        if not CAM.change_core_voltage(mcPort, mcSN, 'Change Core Voltage to 0.74V', debug_tool, '74'):
            return False
        
        # Change core voltage to 0.74V success
        if not pcie_link_down(mcPort, mcSN):
            return False
        time.sleep(5)
        
        # Linkdown success and check core voltage
        if not CAM.check_core_voltage(mcPort, mcSN, debug_tool, '74'):
            return False
        
        # Check core voltage to 0.74V success
        return True
    else:
        return True

def mt_run_test(caseName, debug_tool):
    allPassed = True
    mcPorts = CAM.detected_mlu370()
    
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = CAM.get_sn(mcPort)
        if not check_cpm_count(mcPort, mcSN, debug_tool):
            allPassed = False
            failure_message = '{} Failed on Card{}'.format(caseName, mcPort)
            CAM.record_card_fail(mcPort, mcSN, caseName, failure_message)
    return allPassed

def main(args):
    case_name = 'mlu370 CPM Count Check'
    logging.info('{}'.format(case_name), section=True)
    
    debug_tool = UTP.get('DEBUG_TOOL', '')
    logging.info('DEBUG Tool {}'.format(debug_tool))
    debug_tool_path = osp.join(utilities_path, debug_tool)
    
    result = 'PASS' if mt_run_test(case_name, debug_tool_path) else 'FAIL'
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
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    sys.exit(main(args))
