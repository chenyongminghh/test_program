#!/usr/bin/env python3

import sys
import time
import logging
import argparse
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
sys.path.append(modules_path)
import UTP
import IMM
import CAM

def main(args):
    case_name = 'Temperature Monitor BMC FAN Speed Set'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    imm_num = 0
    all_passed = True
    mcSN = CAM.get_sn('0')
    speed = '60' if mcSN.startswith('58')  else '60'
    logging.info('BMC FAN Speed PWM Set to {}'.format(speed))
    for imm_num in range(imm_qty):
        res = imm.set_fan_speed_mfg(imm_num, speed)
        if res:
            all_passed = False
            logging.info('BMC <{}> FAN Speed Set Failed'.format(imm_num))
        else:
            logging.info('BMC <{}> FAN Speed Set Passed'.format(imm_num))
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
    args = parser.parse_args()
    sys.exit(main(args))
