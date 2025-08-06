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
    case_name = 'mlu370 DVT IO Cross Test'
    logging.info(case_name, section=True)
    
    board_type = CAM.get_mlu370_type('0')
    logging.info('Running {} type boards'.format(board_type))
    
    if board_type in ['EVBD', 'X4', 'M8', 'X4K', 'X4L']:
        test_list = ['mlu370_io_IO_INST_CROSS_RW_8U1']
    elif board_type in ['S4', 'S8', 'X9', 'X9L']:
        test_list = ['mlu370_io_IO_INST_CROSS_RW_6U1']
    elif board_type == 'X8':
        test_list = ['mlu370_io_IO_INST_CROSS_RW_4U1']
    elif board_type == 'D2':
        test_list = ['mlu370_io_IO_INST_CROSS_RW_2U1']
    else:
        test_list = ['mlu370_io_IO_INST_CROSS_RW_4U1']
    
    test_loops = args.loops.strip() if args.loops else '1'
    logging.info('Running {} <{}> loops'.format(test_list[0], test_loops))
    
    dvt_type = 'io'
    case_type = 'io-cross'
    dvt_dir = 'dvt-io'
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
