#!/usr/bin/env python3

import os
import sys
import json
import time
import logging
import collections
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import CAM

UUTStatus = collections.namedtuple('UUTStatus', ('IP', 'Card', 'Operation', 'Start_time', 'Current_program', 'Test_time', 'Status'))
mlu370_test_log = 'mlu370_test.log'


def check_rx_status():
    log_fname = osp.join(logs_path, mlu370_test_log)
    with open(log_fname, mode='a') as test_log:
        test_log.write('###Serdes change to rx ready state Test Start on {}\n'.format(time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    
    all_ready = True
    for path in UTP.glob_file('/proc/driver/cambricon/mlus/*/mlumsg'):
        rtn_port_0 = UTP.run("grep 'serdes 0 change to rx ready state' {}".format(path), shell=True, check=False).strip()
        if not rtn_port_0:
            logging.info('Check {} Port0 Not Ready'.format(path))
        
        rtn_port_1 = UTP.run("grep 'serdes 1 change to rx ready state' {}".format(path), shell=True, check=False).strip()
        if not rtn_port_1:
            logging.info('Check {} Port1 Not Ready'.format(path))
        
        rtn_port_2 = UTP.run("grep 'serdes 2 change to rx ready state' {}".format(path), shell=True, check=False).strip()
        if not rtn_port_2:
            logging.info('Check {} Port2 Not Ready'.format(path))
        
        rtn_port_3 = UTP.run("grep 'serdes 3 change to rx ready state' {}".format(path), shell=True, check=False).strip()
        if not rtn_port_3:
            logging.info('Check {} Port3 Not Ready'.format(path))
        
        if not rtn_port_0 or not rtn_port_1 or not rtn_port_2 or not rtn_port_3:
            all_ready = False
    
        with open(log_fname, mode='a') as test_log:
            test_log.write('Path : {}\n'.format(path))
            test_log.write('Port0: {}\n'.format(rtn_port_0))
            test_log.write('Port1: {}\n'.format(rtn_port_1))
            test_log.write('Port2: {}\n'.format(rtn_port_2))
            test_log.write('Port3: {}\n'.format(rtn_port_3))
            test_log.flush()
            os.fsync(test_log.fileno())
    
    with open(log_fname, mode='a') as test_log:
        test_log.write('###Serdes change to rx ready state Test End on {}\n\n'.format(time.ctime()))
    
    return all_ready

def main():
    case_name = 'mlu370 Serdes change to rx ready state Test'
    logging.info('{}'.format(case_name), section=True)
    
    count_times = 40
    for count in range(count_times):
        logging.info("Count = {}".format(count))
        if check_rx_status():
            break
        elif count == count_times-1:
            break
        else:
            logging.info('waiting 60 seconds for changing to rx ready state ...')
            time.sleep(60)
    
    return
    
    
if __name__ == '__main__':
    sys.exit(main())
    
