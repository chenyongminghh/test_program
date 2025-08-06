#!/usr/bin/env python3

import os
import sys
import time
import logging
import argparse
import os.path as osp

file_path = osp.abspath(__file__)
tests_path = osp.dirname(osp.abspath(__file__))
testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import IMM
import CAM

def main(args):
    case_name = 'BMC Fan Mode Set'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    pid_mode = True if args.pid else False
    
    all_passed = True
    logging.info('BMC FAN Mode Set to {}'.format('PID' if args.pid else 'Table'))
    for imm_num in range(imm_qty):
        res = imm.bmc_fan_mode_set(imm_num, pid=pid_mode)
        if not res:
            all_passed = False
            logging.error('BMC <{}> FAN Mode Set Failed'.format(imm_num))
        else:
            logging.info('BMC <{}> FAN Mode Set Success'.format(imm_num))
            logging.info('Wait 10 seconds')
            time.sleep(10)
    
    result = 'PASS' if all_passed else 'FAIL'
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
    parser.add_argument('--pid', action='store_true', help='BMC PID Fan Mode')
    parser.add_argument('--table', action='store_true', help='BMC Table Fan Mode')
    args = parser.parse_args()
    sys.exit(main(args))