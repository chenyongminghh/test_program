#!/usr/bin/python3.5

import os
import sys
import logging
import os.path as osp
import datetime
import time

file_path = osp.abspath(__file__)
tests_path = osp.dirname(osp.abspath(__file__))
testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import IMM
import CAM

def main():
    case_name = 'BMC Power Policy Setting'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    ipmi_cmd = "chassis policy always-on"
    
    all_passed = True
    for imm_num in range(imm_qty):
        logging.info('BMC<{}> Power Policy Setting Start'.format(imm_num))
        return_value = imm.run_ipmi(imm_num, ipmi_cmd)
        logging.info(return_value)
        if "Set chassis power restore policy to always-on" not in return_value:
            logging.info('BMC<{}> Power Policy Setting Failed'.format(imm_num))
            all_passed = False
        else:
            logging.info('BMC<{}> Power Policy Setting Success'.format(imm_num))
    
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
    sys.exit(main())

