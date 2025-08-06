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

def get_m0_boot_status(q, mcPort, caseName, debug_tool, support_empty):
    mcPort = str(mcPort)
    mcSN = CAM.get_sn(mcPort)
    log_fname = osp.join(logs_path, '{}/{}'.format(CAM.format_dirname(mcPort, mcSN, 'pcie-test'), CAM.format_fname(mcPort, mcSN, dvt_name='bootcheck')))
    logging.info('{} Start  on Card{} <{}>'.format(caseName, mcPort, mcSN))
    
    boot_status = False
    isse_m0_version, d2d_m0_version, ddr_m0_version = CAM.get_image_ver(mcPort)
    if isse_m0_version == '00.0.0' and d2d_m0_version == '00.0.0' and ddr_m0_version == '00.0.0' and support_empty:
        boot_status = True
        logging.info('{} Passed on Card{} [{}/{}/{} MFG Init]'.format(caseName, mcPort, isse_m0_version, d2d_m0_version, ddr_m0_version))
        return q.put(boot_status)
    
    # ./MLU370_Debug_Tool -i 0 -r -a 0x36800c
    test_cmd = [debug_tool, '-i', mcPort, '-r', '-a', '0x36800c']
    
    start_time = datetime.now()
    for sleep_time in range(10):
        with open(log_fname, mode='a') as test_log:
            test_log.write('###{} Start on {}\n'.format(caseName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
            test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
            test_log.flush()
            os.fsync(test_log.fileno())
        proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
        with open(log_fname, mode='a') as test_log:
            test_log.write('TEST_RTN={}\n'.format(proc.returncode))
            test_log.write('###{} End  on {}\n\n'.format(caseName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
        if proc.returncode:
            logging.error('{} Failed on Card{} with returncode {}'.format(caseName, mcPort, proc.returncode))
            break
        return_context = proc.stdout.decode('utf-8')
        for line in return_context.split('\n'):
            line = line.strip()
            if "value of addr 36800c" in line and line.endswith('2200'):
                boot_status = True
        if boot_status:
            break
        time.sleep(1)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    if boot_status:
        logging.info('{} Passed on Card{} [{} sec]'.format(caseName, mcPort, total_seconds))
    else:
        logging.info('{} Failed on Card{} [{} sec]'.format(caseName, mcPort, total_seconds))
        failure_message = '{} Failed on Card{}'.format(caseName, mcPort)
        CAM.record_card_fail(mcPort, mcSN, caseName, failure_message)
    return q.put(boot_status)
    
def mt_run_test(caseName, debug_tool, support_empty):
    p_lst = []
    q = mp.Queue()
    mcPorts = CAM.detected_mlu370()
    
    for mcPort in range(mcPorts):
        time.sleep(0.1)
        p = mp.Process(target=get_m0_boot_status, args=(q, mcPort, caseName, debug_tool, support_empty))
        p.start()
        p_lst.append(p)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for mcPort in range(mcPorts):
        res = q.get()
        if not res:
            logging.info("Card{} res --> {}".format(str(mcPort), res))
            allPassed = False
    return allPassed

def main(args):
    case_name = 'mlu370 Check M0 Boot Status'
    logging.info('{}'.format(case_name), section=True)
    
    debug_tool = UTP.get('DEBUG_TOOL', '')
    logging.info('DEBUG Tool {}'.format(debug_tool))
    debug_tool_path = osp.join(utilities_path, debug_tool)
    
    support_empty = True if args.empty else False
    
    result = 'PASS' if mt_run_test(case_name, debug_tool_path, support_empty) else 'FAIL'
    if result == 'PASS':
        logging.info('{} successfully'.format(case_name))
    elif UTP.get('MFG_FAIL_MODE', None):
        logging.error('{} FAILED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} failed'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        CAM.record_fail_case(case_name)
        raise Exception('Some failure detected, please check the log.')
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--empty', action='store_true', help='Maybe M0 empty')
    args = parser.parse_args()
    sys.exit(main(args))
