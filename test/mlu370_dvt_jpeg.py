#!/usr/bin/env python3

import sys
import time
import logging
import argparse
import os.path as osp
import multiprocessing as mp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
sys.path.append(modules_path)
import UTP
import CAM

def main(args):
    case_name = 'mlu370 DVT JPEG Test'
    logging.info(case_name, section=True)
    
    test_list = CAM.get_dvt_list('jpeg')
    logging.info('Running <{}> JPEG test cases'.format(len(test_list)))
    
    test_loops = args.loops.strip() if args.loops else '1'
    logging.info('Running DVT JPEG Test <{}> loops'.format(test_loops))
    
    dvt_type = 'jpeg'
    case_type = 'jpeg'
    dvt_dir = 'dvt-video'
    result = 'PASS' if CAM.new_mt_run_dvt_Test(case_name, dvt_type, case_type, test_list, test_loops, dvt_dir) else 'FAIL'
    
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('MFG_FAIL_MODE', None):
        logging.error('{} FAILED'.format(case_name))
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
    parser.add_argument('-l', '--loops', action='store', help='Test Loops')
    args = parser.parse_args()
    sys.exit(main(args))
