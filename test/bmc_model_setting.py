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
    case_name = 'BMC X1001 Model Setting'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    ipmi_cmd1 = "raw 0x3a 0x8b 0x56 0x50 0x44 0xaa"
    ipmi_cmd2 = "raw 0x3a 0x89 0x80 0x00 0x4d 0x4c 0x55 0x2d 0x58 0x31 0x30 0x30 0x31"
    
    all_passed = True
    for imm_num in range(imm_qty):
        logging.info('BMC<{}> Model Setting Start'.format(imm_num))
        proc1 = imm.run_ipmi(imm_num, ipmi_cmd1, proc=True)
        if proc1.returncode:
            all_passed = False
            logging.info('BMC<{}> Setting <{}> Failed with returncode <{}>'.format(imm_num, ipmi_cmd1, proc1.returncode))
            break
        logging.info('BMC<{}> Setting <{}> Success'.format(imm_num, ipmi_cmd1))
        time.sleep(3)
        
        proc2 = imm.run_ipmi(imm_num, ipmi_cmd2, proc=True)
        if proc2.returncode:
            all_passed = False
            logging.info('BMC<{}> Setting <{}> Failed with returncode <{}>'.format(imm_num, ipmi_cmd2, proc2.returncode))
            break
        logging.info('BMC<{}> Setting <{}> Success'.format(imm_num, ipmi_cmd2))
        time.sleep(3)
        
        logging.info('BMC<{}> Cold Reset Start'.format(imm_num))
        return_value = imm.bmc_cold_reset(imm_num)
        logging.info('BMC<{}> Cold Reset Return Value: {}'.format(imm_num, return_value))
        logging.info('BMC<{}> Waiting 60s for BMC rebooting'.format(imm_num))
        time.sleep(60)
        logging.info('BMC<{}> Model Setting Success'.format(imm_num))
    
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

