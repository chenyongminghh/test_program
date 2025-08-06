#!/usr/bin/env python3
"""
# This test case verifies that the system event log time is correct.
"""

import sys
import logging
import datetime
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
sys.path.append(modules_path)
import UTP
import IMM
import CAM

def main():
    case_name = 'BMC SEL Time Test'
    logging.info('{}'.format(case_name), section=True)
    
    tolerance = datetime.timedelta(seconds=185)  # allowable offset +/- seconds
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    all_passed = True
    for imm_num in range(imm_qty):
        logging.info('BMC <{}> SEL Time Test Start'.format(imm_num))
        current_time = datetime.datetime.now()
        system_event_time = imm.check_sel_time(imm_num)
        if abs(current_time - system_event_time) <= tolerance:
            logging.info('BMC <{}> System Event Log Time: {!s}'.format(imm_num, system_event_time))
            logging.info('BMC <{}> SEL Time Test Success'.format(imm_num))
        else:
            logging.error('BMC <{}> SEL Time Test Failed'.format(imm_num))
            all_passed = False
    
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
