#!/usr/bin/env python3

import os
import sys
import time
import json
import logging
import argparse
import subprocess
import os.path as osp
import multiprocessing as mp
from datetime import datetime

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
request_path = osp.join(testcode_path, 'request')
modules_path = osp.join(testcode_path, 'modules')
utilities_path = osp.join(testcode_path, 'utilities')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import CAM

def control_pdu(pdu_ip, delay_on_seconds):
    control_result = True
    log_fname = osp.join(logs_path, 'pwrctl.log')
    test_cmd = ['./pwrctl.py', pdu_ip, '11', delay_on_seconds, '-v']
    
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###PDUC {} Start on {}\n'.format(pdu_ip, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False, cwd=utilities_path)
    end_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('###PDUC {} End  on {}\n\n'.format(pdu_ip, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    
    if proc.returncode:
        logging.error('{} Failed with returncode {}'.format(' '.join(test_cmd), proc.returncode))
        control_result = False
    else:
        return_context = proc.stdout.decode('utf-8')
        if "Success" not in return_context:
            logging.error('{} Failed with not inclue <Success>'.format(' '.join(test_cmd)))
            control_result = False
    return control_result

def get_pdu_dict(host_ip):
    pdu_ip_dict = dict()
    username = CAM.get_system_username()
    new_pducfg = '/home/{}/spider_test/utilities/pducfg.json'.format(username)
    local_pducfg = osp.join(utilities_path, 'pducfg.json')
    if osp.exists(new_pducfg):
        UTP.run(['cp', '-rf', new_pducfg, local_pducfg], log_stdout=logging.DEBUG)
    
    if not osp.exists(local_pducfg):
        logging.error('File <pducfg.json> not exists')
        return False
    
    with open(local_pducfg, 'r') as load_f:
        var_dict = json.load(load_f)
    pdu_ip_dict = var_dict.get(host_ip, 'NotFound')
    if pdu_ip_dict == 'NotFound':
        logging.error('NotFound <{}> PDU Info in pducfg.json'.format(host_ip))
        return False
    return pdu_ip_dict

def main(argv):
    case_name = 'mlu370 PDU AC Control'
    logging.info(case_name, section=True)
    
    host_ip = CAM.get_host_ip()
    if not host_ip:
        logging.error('Host IP did not detected')
        CAM.record_fail_case(case_name)
        raise Exception('Host IP did not detected')
    
    pdu_ip_dict = get_pdu_dict(host_ip)
    if not pdu_ip_dict:
        CAM.record_fail_case(case_name)
        raise Exception('Get PDU Info Failed')
    
    host_pdu_ip = pdu_ip_dict.get('HOSTPDU')
    spider_0_pdu_ip = pdu_ip_dict.get('PDU_SPIDER0')
    
    logging.info('PDUC AC Control {} --> [{}, {}] '.format(host_ip, host_pdu_ip, spider_0_pdu_ip))
    res_host = control_pdu(host_pdu_ip, '120,120')
    if res_host:
        logging.info('PDU:<{:^16s}> AC success and will on after 120 seconds'.format(host_pdu_ip))
    else:
        logging.error('PDU:<{:^16s}> AC Failed'.format(host_pdu_ip))
        CAM.record_fail_case(case_name)
        raise Exception('AC Control PDU Failed')
    
    res_spider_0 = control_pdu(spider_0_pdu_ip, '50,50')
    if res_spider_0:
        logging.info('PDU:<{:^16s}> AC success and will on after 50 seconds'.format(spider_0_pdu_ip))
    else:
        logging.error('PDU:<{:^16s}> AC Failed'.format(spider_0_pdu_ip))
        CAM.record_fail_case(case_name)
        UTP.run('touch /home/{}/quit.now'.format(CAM.get_system_username()), shell=True, log_stdout=logging.INFO)
        raise Exception('AC Control PDU Failed')
    
    time.sleep(600)
    CAM.record_fail_case(case_name)
    raise Exception('mlu370 PDU AC Control Failed')
    return

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    sys.exit(main(args))
