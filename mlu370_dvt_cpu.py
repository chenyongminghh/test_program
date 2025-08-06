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
import CAM

def main(args):
    case_name = 'mlu370 DVT CPU Test'
    logging.info(case_name, section=True)
    
    test_loops = args.loops.strip() if args.loops else '1'
    logging.info('Running DVT BSP Test <{}> loops'.format(test_loops))
    
    result = 'PASS' if CAM.mlu370_bsp_test(case_name, test_loops) else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
        raise Exception('There are some card boot failed.')
    return

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--loops', action='store', help='Test Loops')
    args = parser.parse_args()
    sys.exit(main(args))
