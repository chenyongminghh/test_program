#!/usr/bin/env python3
""" Check the SEL list. 
    
"""
import sys
import logging
import argparse
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
tables_path = osp.join(testcode_path, 'tables')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import IMM
import UTP
import CAM

def main(args):
    case_name = 'BMC SEL List Test'
    logging.info('{}'.format(case_name), section=True)
    
    sel_elist_ignore_file = osp.join(tables_path, "IGNORE.ESEL")
    if args.skippsu:
        sel_elist_ignore_file = osp.join(tables_path, "IGNORE-PSU.ESEL")
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    ignore_list = imm.get_sel_ignore_elist(ignore_file = sel_elist_ignore_file)
    
    all_passed = True
    for imm_num in range(imm_qty):
        logging.info('BMC <{}> SEL Test'.format(imm_num))
        if imm.bmc_sel_elist_check(imm_num, ignore_list):
            logging.info('BMC <{}> SEL Test PASSED.'.format(imm_num))
        else:
            logging.error('BMC <{}> SEL Test FAILED.'.format(imm_num))
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--skippsu', action='store_true', help='Skip PSU Voltage Record')
    args = parser.parse_args()
    sys.exit(main(args))
