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
    case_name = 'mlu370 DVT Resnet50 and Mobilnet Test'
    logging.info(case_name, section=True)
    
    board_type = CAM.get_mlu370_type('0')
    logging.info('Running {} type boards'.format(board_type))
    
    if board_type in ['EVBD', 'X4', 'M8', 'X4K', 'X4L']:
        test_list = ['mlu370_handng_resnet50_layer4_8u1', 'mlu370_handng_mobilenet_8u1']
    elif board_type in ['S4', 'S8', 'X9', 'X9L']:
        test_list = ['mlu370_handng_resnet50_layer4_6u1', 'mlu370_handng_mobilenet_6u1']
    elif board_type == 'X8':
        test_list = ['mlu370_handng_resnet50_layer4_4u1', 'mlu370_handng_mobilenet_4u1']
    elif board_type == 'D2':
        test_list = ['mlu370_handng_resnet50_layer4_2u1', 'mlu370_handng_mobilenet_2u1']
    else:
        test_list = ['mlu370_handng_resnet50_layer4_4u1', 'mlu370_handng_mobilenet_4u1']
    
    test_loops = args.loops.strip() if args.loops else '1'
    logging.info('Running {} <{}> loops'.format(test_list[0], test_loops))
    logging.info('Running {} <{}> loops'.format(test_list[1], test_loops))
    
    dvt_type = 'typicalnet'
    case_type = 'resnet50'
    dvt_dir = 'dvt-net'
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
    parser.add_argument('--loops', action='store', help='override default loops')
    args = parser.parse_args()
    sys.exit(main(args))
