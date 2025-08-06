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

die0_sys0 = ['0x08370208', '0x08371010', '0x08372010', '0x08371020', '0x08371024', '0x08372020', '0x08372024']
die0_sys1 = ['0x003D0208', '0x003D1010', '0x003D2010', '0x003D1020', '0x003D1024', '0x003D2020', '0x003D2024']
die1_sys0 = ['0x18370208', '0x18371010', '0x18372010', '0x18371020', '0x18371024', '0x18372020', '0x18372024']
die1_sys1 = ['0x103D0208', '0x103D1010', '0x103D2010', '0x103D1020', '0x103D1024', '0x103D2020', '0x103D2024']
addr_list = die0_sys0 + die0_sys1 + die1_sys0 + die1_sys1

def crc_collect_one_card(mcPort, mcSN, debug_tool):
    caseName = 'mlu370 CRC Collect'
    mcPort = str(mcPort)
    log_fname = osp.join(logs_path, '{}/{}'.format(CAM.format_dirname(mcPort, mcSN, 'crc-collect'), CAM.format_fname(mcPort, mcSN, 'crcdata')))
    
    check_result = True
    logging.info('{} Start  on Card{} <{}>'.format(caseName, mcPort, mcSN))
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    
    start_time = datetime.now()
    for addr in addr_list:
        test_cmd = [debug_tool, '-i', mcPort, '-r', '-a', addr]
        proc = UTP.runproc_rt(test_cmd, log_stdout=logging.DEBUG, stderr=subprocess.STDOUT, check=False)
        if proc.returncode:
            check_result = False
            logging.error('{} Failed on Card{} with returncode {}'.format(caseName, mcPort, proc.returncode))
            return check_result
        return_context = ''
        return_context = proc.stdout.decode('utf-8')
        crc_data = return_context.split('\n')[2].strip()
        logging.info(crc_data)
        with open(log_fname, mode='a') as test_log:
            test_log.write('{}\n'.format(crc_data))
        if '0x00000000' not in crc_data:
            check_result = False
            failure_message = '{} Card{} {} {}'.format(time.strftime('%Y%m%d-%H%M%S',time.localtime()), mcPort, mcSN, crc_data)
            CAM.record_fail_case(failure_message)
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} End   on {}\n\n'.format(caseName, time.ctime()))
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    
    if check_result:
        logging.info('{} Passed on Card{} [{} sec]'.format(caseName, mcPort, total_seconds))
    else:
        logging.error('{} Failed on Card{}'.format(caseName, mcPort))
    return check_result

def check_link_ecc_count(mcPort, test_tool):
    dvt_name = 'linkecc'
    caseName = 'mlu370 Linkecc Check'
    mcSN = CAM.get_sn(mcPort)
    log_fname = osp.join(logs_path, '{}/{}'.format(CAM.format_dirname(mcPort, mcSN, 'voltage'), CAM.format_fname(mcPort, mcSN, dvt_name)))
    logging.info('{} Start  on Card{} <{}>'.format(caseName, mcPort, mcSN))
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    
    # ./MLU370_Debug_Tool_x86_ecc_print_3e28ae -i x -f 2
    test_cmd = [test_tool, '-i', mcPort, '-f', '2']
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('###{} End  on {}\n\n'.format(caseName, time.ctime()))
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
    case_name = 'mlu370 CRC Collect and Linkecc Check'
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
        if not crc_collect_one_card(mcPort, mcSN, debug_tool_path):
            test_result = False
            CAM.record_card_fail(mcPort, mcSN, case_name, "CRC Collect Failed")
        if not check_link_ecc_count(mcPort, linkecc_tool_path):
            test_result = False
            CAM.record_card_fail(mcPort, mcSN, case_name, "Linkecc Check Failed")
        
    result = 'PASS' if test_result else 'FAIL'
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
    args = parser.parse_args()
    sys.exit(main(args))
