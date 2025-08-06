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
    case_name = 'mlu370 PITest Fix Burst Test'
    logging.info(case_name, section=True)
    
    board_type = CAM.get_mlu370_type('0')
    logging.info('Running {} type boards'.format(board_type))
    
    high_loops = args.high.strip() if args.high else '1000'
    low_loops = args.low.strip() if args.low else '3320'
    inner_loops = args.inner.strip() if args.inner else '5'
    dimz_loops = args.dimz.strip() if args.dimz else '100000'
    
    cmd_dict = dict()
    cmd_dict['S4'] = 'mlu370_ipu_IPU_INST_EHPI_FIX_BURST_U6'
    cmd_dict['S8'] = 'mlu370_ipu_IPU_INST_EHPI_FIX_BURST_U6'
    cmd_dict['X9'] = 'mlu370_ipu_IPU_INST_EHPI_FIX_BURST_U6'
    cmd_dict['X9L'] = 'mlu370_ipu_IPU_INST_EHPI_FIX_BURST_U6'
    cmd_dict['X4'] = 'mlu370_ipu_IPU_INST_EHPI_FIX_BURST_U8'
    cmd_dict['X8'] = 'mlu370_ipu_IPU_INST_EHPI_FIX_BURST_U4'
    cmd_dict['EVBD'] = 'mlu370_ipu_IPU_INST_EHPI_FIX_BURST_U8'
    cmd_dict['M8'] = 'mlu370_ipu_IPU_INST_EHPI_FIX_BURST_U8'
    cmd_dict['D2'] = 'mlu370_ipu_IPU_INST_EHPI_FIX_BURST_U2'
    cmd_dict['X4K'] = 'mlu370_ipu_IPU_INST_EHPI_FIX_BURST_U8'
    cmd_dict['X4L'] = 'mlu370_ipu_IPU_INST_EHPI_FIX_BURST_U8'
    
    dvt_dir = 'dvt-power'
    dvt_name = 'fix_ehpi_burst'
    ipu_cmd = cmd_dict[board_type]
    CAM.mlu370_dimz('fix_test', 'ehpi_burst_30MHz_u1', dimz_loops)
    CAM.mlu370_dimz('fix_test', 'ehpi_burst_30MHz_u4', dimz_loops)
    CAM.mlu370_dimz('fix_test', 'ehpi_burst_30MHz_u8', dimz_loops)
    
    logging.info('Running {} {} {} {} <dimz:{}>'.format(ipu_cmd, high_loops, low_loops, inner_loops, dimz_loops))
    
    result = 'PASS' if CAM.mt_run_power_Test(case_name, ipu_cmd, high_loops, low_loops, inner_loops, dvt_dir, dvt_name) else 'FAIL'
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
    parser.add_argument('--high', action='store', help='High loops')
    parser.add_argument('--low', action='store', help='Low loops')
    parser.add_argument('--inner', action='store', help='Inner loops')
    parser.add_argument('--dimz', action='store', help='Dimz loops')
    args = parser.parse_args()
    sys.exit(main(args))
