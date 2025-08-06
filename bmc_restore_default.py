#!/usr/bin/env python3

import sys
import time
import logging
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import IMM
import UTP
import CAM

def main():
    case_name = 'BMC Restore Factory Default'
    logging.info(case_name, section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    all_passed = True
    for imm_num in range(imm_qty):
        logging.info('BMC <{}> Restore Factory Default Start'.format(imm_num))
        if imm.restore_default(imm_num):
            logging.info('BMC <{}> Restore Factory Default Success'.format(imm_num))
        else:
            logging.error('BMC <{}> Restore Factory Default Failed'.format(imm_num))
            all_passed = False
    
    result = 'PASS' if all_passed else 'FAIL'
    if result == 'PASS':
        time.sleep(30)
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.error('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        logging.error('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
        raise Exception('There are some fail info detected, please check the tester.log')
    
    return
    

if __name__ == '__main__':
    sys.exit(main())
