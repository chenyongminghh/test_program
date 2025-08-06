#!/usr/bin/env python3

import os
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

def mt_run_DMA_IPU_Test(dvt_dir, ipu_cmd, ipu_dvt_name, ipu_loops, dma_dvt_name, dma_loops):
    high_loops, low_loops, inner_loops = ipu_loops
    p_lst = []
    q1 = mp.Queue()
    q2 = mp.Queue()
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.1)
        p1 = mp.Process(target=CAM.mlu370_new_power_one_card, args=(q1, mcPort, 'mlu370 DMA PITest-Fix-Maxpower', ipu_cmd, high_loops, low_loops, inner_loops, dvt_dir, ipu_dvt_name, 30))
        p1.start()
        p_lst.append(p1)
        
        time.sleep(0.1)
        p2 = mp.Process(target=CAM.mlu370_dvt_one_card, args=(q2, mcPort, 'mlu370 Fix-Maxpower PCIE-DMA', 'driver', dma_dvt_name, ['mlu370_pcie_PCIE_DRV_01'], dma_loops, dvt_dir, 30))
        p2.start()
        p_lst.append(p2)
    time.sleep(0.5)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for mcPort in range(mcPorts):
        res_ipu = q1.get()
        res_dma = q2.get()
        if not res_ipu or not res_dma:
            logging.info("Card{} res_ipu --> {}".format(str(mcPort), res_ipu))
            logging.info("Card{} res_dma --> {}".format(str(mcPort), res_dma))
            allPassed = False
    return allPassed

def main(args):
    case_name = 'mlu370 PITest Fix Maxpower and DMA Test'
    logging.info(case_name, section=True)
    
    dvt_dir = 'power-dma'
    ipu_dvt_name = 'fix-maxpower'
    dma_dvt_name = 'dma'
    
    board_type = CAM.get_mlu370_type('0')
    logging.info('Running {} type boards'.format(board_type))
    
    dma_loops = args.dma.strip() if args.dma else '1'
    power_loops = args.power.strip() if args.power else '1'
    
    cmd_dict = dict()
    cmd_dict['X8'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U4'
    cmd_dict['S4'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U6'
    cmd_dict['S8'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U6'
    cmd_dict['X9'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U6'
    cmd_dict['X9L'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U6'
    cmd_dict['X4'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U8'
    cmd_dict['EVBD'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U8'
    cmd_dict['M8'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U8'
    cmd_dict['D2'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U2'
    cmd_dict['X4K'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U8'
    cmd_dict['X4L'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U8'
    ipu_cmd = cmd_dict[board_type]
    
    ipu_loops = ['2500', '0', '0']
    dimz_loops = str(int(power_loops) * 100000)
    
    CAM.mlu370_dimz('fix_test', 'maxp_u1', dimz_loops)
    CAM.mlu370_dimz('fix_test', 'maxp_u4', dimz_loops)
    CAM.mlu370_dimz('fix_test', 'maxp_u8', dimz_loops)
    
    logging.info('Running PITest Fix Maxpower {} {} {} {} <dimz:{}>'.format(ipu_cmd, ipu_loops[0], ipu_loops[1], ipu_loops[2], dimz_loops))
    logging.info('Running DMA <{}> loops'.format(dma_loops))
    
    result = 'PASS' if mt_run_DMA_IPU_Test(dvt_dir, ipu_cmd, ipu_dvt_name, ipu_loops, dma_dvt_name, dma_loops) else 'FAIL'
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
    parser.add_argument('-d', '--dma', action='store', help='DMA loops')
    parser.add_argument('-p', '--power', action='store', help='Power loops')
    args = parser.parse_args()
    sys.exit(main(args))
