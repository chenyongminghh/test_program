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
    case_name = 'mlu370 DVT Driver DMA Test'
    logging.info(case_name, section=True)
    
    test_list = ['mlu370_pcie_PCIE_DRV_01', 'mlu370_pcie_PCIE_DRV_03_01', 'mlu370_pcie_PCIE_DRV_04_01', 'mlu370_pcie_PCIE_DRV_05_01']
    logging.info('Running Driver-PCIE-DMA <{}> test cases'.format(len(test_list)))
    
    test_loops = args.loops.strip() if args.loops else '1'
    logging.info('Running DVT Driver-PCIE-DMA Test <{}> loops'.format(test_loops))
    
    CAM.remove_drv_flag()
    
    dvt_type = 'driver'
    case_type = 'dma'
    dvt_dir = 'dvt-driver'
    result = 'PASS' if CAM.new_mt_run_dvt_Test(case_name, dvt_type, case_type, test_list, test_loops, dvt_dir) else 'FAIL'
    
    CAM.create_drv_flag()
    
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
