#!/usr/bin/env python3
"""
    This test case is used to set the system event log time on the UUT
"""

import sys
import logging
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
sys.path.append(modules_path)
import UTP
import IMM
import CAM

def main():
    case_name = 'BMC SEL Time Set'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    all_passed = True
    for imm_num in range(imm_qty):
        don_flag = 'sel_time_don_bmc{}'.format(imm_num)
        logging.info('BMC <{}> SEL Time Set Start'.format(imm_num))
        if UTP.get(don_flag, None):
            logging.info('BMC <{}> SEL Time Already set [SKIP]'.format(imm_num))
        else:
            imm.set_sel_time(imm_num)
            logging.info('BMC <{}> SEL Time Set Success.'.format(imm_num))
            UTP.set(don_flag, True)
    
    result = 'PASS' if all_passed else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.error('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        logging.error('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
        raise Exception('There are some fail info detected, please check the log.')
    

if __name__ == '__main__':
    sys.exit(main())
