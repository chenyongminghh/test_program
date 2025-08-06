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

die0_sys0 = ['0x08371020', '0x08371024', '0x08372020', '0x08372024']
die0_sys1 = ['0x003D1020', '0x003D1024', '0x003D2020', '0x003D2024']
die1_sys0 = ['0x18371020', '0x18371024', '0x18372020', '0x18372024']
die1_sys1 = ['0x103D1020', '0x103D1024', '0x103D2020', '0x103D2024']
addr_list = die0_sys0 + die0_sys1 + die1_sys0 + die1_sys1

def crc_collect_one_card(mcPort, mcSN, caseName, debug_tool):
    dvt_name = 'crcdata'
    log_fname = osp.join(logs_path, '{}/{}'.format(CAM.format_dirname(mcPort, mcSN, 'crc-collect'), CAM.format_fname(mcPort, mcSN, dvt_name)))
    
    check_result = True
    logging.info('{} Start  on Card{} <{}>'.format(caseName, mcPort, mcSN))
    
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d %H:%M:%S")))
        test_log.flush()
        os.fsync(test_log.fileno())
    for addr in addr_list:
        test_cmd = [debug_tool, '-i', mcPort, '-r', '-a', addr]
        proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
        if proc.returncode:
            check_result = False
            failure_message = 'Card{} {} Failed with returncode {}'.format(mcPort, mcSN, proc.returncode)
            logging.error(failure_message)
            CAM.record_card_fail(mcPort, mcSN, caseName, failure_message)
            break
        return_context = ''
        return_context = proc.stdout.decode('utf-8')
        crc_data = return_context.split('\n')[2].strip()
        crc_value = crc_data.split()[-1].strip()
        if crc_value != '0x00000000':
            check_result = False
            crc_msg = 'Card{} {} CRCDATA {}--{}--{}'.format(mcPort, mcSN, addr, crc_value, int(crc_value, 16))
            logging.error(crc_msg)
            failure_message = '{} {}'.format(time.strftime('%Y%m%d-%H%M%S',time.localtime()), crc_msg)
            failure_message = 'Card{} {} {} Failed'.format(mcPort, mcSN, crc_data)
            CAM.record_card_fail(mcPort, mcSN, caseName, failure_message)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} End   on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    if check_result:
        logging.info('{} Passed on Card{} [{} sec]'.format(caseName, mcPort, total_seconds))
    else:
        logging.error('{} Failed on Card{}'.format(caseName, mcPort))
    return check_result

def main(args):
    case_name = 'mlu370 Check CRC State'
    logging.info('{}'.format(case_name), section=True)
    
    debug_tool = UTP.get('DEBUG_TOOL', '')
    logging.info('DEBUG Tool {}'.format(debug_tool))
    debug_tool_path = osp.join(utilities_path, debug_tool)
    
    test_result = True
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = CAM.get_sn(mcPort)
        if not crc_collect_one_card(mcPort, mcSN, case_name, debug_tool_path):
            test_result = False
        
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
