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
    case_name = 'BMC FAN Speed Set'
    logging.info('{}'.format(case_name), section=True)
    
    imm_num = 0
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    speed = args.speed.strip() if args.speed else 'Auto'
    
    all_passed = True
    logging.info('BMC FAN Speed PWM Set to {}'.format(speed))
    for imm_num in range(imm_qty):
        if speed == 'Auto':
            res = imm.set_fan_speed(imm_num, speed='Auto')
        else:
            res = imm.set_fan_speed_mfg(imm_num, speed)
        if res:
            all_passed = False
            logging.error('BMC <{}> FAN Speed Set Failed'.format(imm_num))
        else:
            logging.info('BMC <{}> FAN Speed Set Success'.format(imm_num))
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
    parser.add_argument('--speed', action='store', help='BMC Fan Speed')
    args = parser.parse_args()
    sys.exit(main(args))
