#!/usr/bin/env python3
""" Check the SEL list. 
    
"""
import sys
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
    case_name = 'BMC SEL List Clear'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    all_passed = True
    for imm_num in range(imm_qty):
        logging.info('BMC <{}> SEL Clear'.format(imm_num))
        if imm.clear_sel_log(imm_num):
            logging.info('BMC <{}> SEL Clear PASSED.'.format(imm_num))
        else:
            logging.error('BMC <{}> SEL Clear FAILED.'.format(imm_num))
            all_passed = False
    
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
