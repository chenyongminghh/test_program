#!/usr/bin/env python3

import os
import sys
import time
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

def get_nvme_list():
    nvme_list = []
    proc = UTP.runproc_rt('ls /dev/nvme*n1', shell=True, stderr=subprocess.STDOUT, check=False)
    return_context = proc.stdout.decode('utf-8').strip()
    nvme_list = return_context.split('\n')
    return nvme_list

def nvme_format(devName):
    cmdlist = ['./nvme', '--format', devName]
    log_fname = osp.join(logs_path, '{}.log'.format(devName.split('/')[-1]))
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Format Test Start on {}\n'.format(devName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
        test_log.write('TEST_CMD={}\n'.format(' '.join(cmdlist)))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(cmdlist, log_stdout=log_fname, stderr=subprocess.STDOUT, cwd=utilities_path)
    with open(log_fname, mode='a') as test_log:
        test_log.write('\n')
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('###{} Test End on {}\n\n'.format(devName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
    if proc.returncode:
        logging.error('{} format Failed with returncode {}'.format(devName, proc.returncode))
        return False
    else:
        logging.info('{} format success'.format(devName))
        return True
    

def main(args):
    case_name = 'mlu370 DVT NVME Format Test'
    logging.info(case_name, section=True)
    
    nvme_list = get_nvme_list()
    if len(nvme_list) != 4:
        logging.info('NVME Qty Check Failed')
        CAM.record_fail_case(case_name)
        raise Exception('NVME Qty Check FAILED')
    logging.info('NVME Devices:{}'.format(nvme_list))
    
    result = 'PASS'
    for nvme in nvme_list:
        if not nvme_format(nvme):
            result = 'FAIL'
        
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
        raise Exception('There are some card boot failed.')
    return
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', action='store', help='read, write, randread, randwrite')
    parser.add_argument('--time', action='store', help='stress test time')
    parser.add_argument('--loops', action='store', help='loops')
    args = parser.parse_args()
    sys.exit(main(args))
    