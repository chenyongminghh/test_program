#!/usr/bin/env python3

import os
import sys
import logging
import argparse
import collections
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')
sys.path.append(modules_path)
import UTP
import CAM

def main(args):    
    case_name = 'mlu370 X4L Temperature Monitor Start'
    logging.info('{}'.format(case_name), section=True)
    
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = CAM.get_sn(mcPort)
        monitor_log_file = osp.join(logs_path, "monitor_card{}_{}.log".format(mcPort, mcSN))
        if osp.exists(monitor_log_file):
            logging.info('Remove File <{}>'.format(osp.basename(monitor_log_file)))
            os.unlink(monitor_log_file)
    
    all_delete = True
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = CAM.get_sn(mcPort)
        monitor_log_file = osp.join(logs_path, "monitor_card{}_{}.log".format(mcPort, mcSN))
        if osp.exists(monitor_log_file):
            logging.info('Remove File <{}> Failed'.format(osp.basename(monitor_log_file)))
            all_delete = False
    
    result = 'PASS' if all_delete else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
        raise Exception('There are some fail info detected')
    return
    
if __name__=='__main__':
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    sys.exit(main(args))
    