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
    port_list = ['0', '1', '2', '3'] if CAM.get_mlu370_type('0') in ['X8', 'X9', 'X9L', 'M8'] else ['2', '3']
    all_ready = True
    for path in UTP.glob_file('/proc/driver/cambricon/mlus/*/mlumsg'):
        with open(log_fname, mode='a') as test_log:
            test_log.write('Path : {}\n'.format(path))
            test_log.flush()
            os.fsync(test_log.fileno())
        for port in port_list:
            rtn_port = UTP.run("grep 'serdes {} change to rx ready state' {}".format(port, path), shell=True, check=False).strip()
            if not rtn_port:
                all_ready = False
                logging.info('Check {} Port{} Not Ready'.format(path, port))
            with open(log_fname, mode='a') as test_log:
                test_log.write('Port{}: {}\n'.format(port, rtn_port))
                test_log.flush()
                os.fsync(test_log.fileno())
    with open(log_fname, mode='a') as test_log:
        test_log.write('###Serdes change to rx ready state Test End on {}\n\n'.format(time.ctime()))
    return all_ready

def main():
    case_name = 'mlu370 Serdes Check Rx Ready State'
    logging.info('{}'.format(case_name), section=True)
    
    count_times = 6
    for count in range(count_times):
        logging.info("The {} times checking ...".format(str(count+1)))
        if check_rx_status():
            logging.info('{} PASSED'.format(case_name))
            break
        elif count == count_times-1:
            logging.info('{} FAILED'.format(case_name))
            CAM.record_fail_case(case_name)
            raise Exception('Check Rx Ready FAILED')
        else:
            logging.info('waiting 60 seconds for changing to rx ready state ...')
            time.sleep(60)
    return
    
    
if __name__ == '__main__':
    sys.exit(main())
    
