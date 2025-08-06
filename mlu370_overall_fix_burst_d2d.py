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

def mt_run_DMA_IPU_Test(dvt_dir, ipu_cmd, ipu_dvt_name, ipu_loops, gdmac_cmd, d2d_dvt_name, d2d_loops):
    high_loops, low_loops, inner_loops = ipu_loops
    p_lst = []
    q1 = mp.Queue()
    q2 = mp.Queue()
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.1)
        p1 = mp.Process(target=CAM.mlu370_new_power_one_card, args=(q1, mcPort, 'mlu370 D2D PITest-Fix-Burst', ipu_cmd, high_loops, low_loops, inner_loops, dvt_dir, ipu_dvt_name, 27))
        p1.start()
        p_lst.append(p1)
        
        time.sleep(0.1)
        p2 = mp.Process(target=CAM.mlu370_new_gdmac_test, args=(q2, mcPort, 'mlu370 Fix-Burst D2D-GDMAC', gdmac_cmd, d2d_loops, dvt_dir, d2d_dvt_name, 27))
        p2.start()
        p_lst.append(p2)
    time.sleep(0.5)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for mcPort in range(mcPorts):
        res_ipu = q1.get()
        res_d2d = q2.get()
        if not res_ipu or not res_d2d:
            logging.info("Card{} res_ipu --> {}".format(str(mcPort), res_ipu))
            logging.info("Card{} res_d2d --> {}".format(str(mcPort), res_d2d))
            allPassed = False
    return allPassed

def st_run_DMA_IPU_Test(dvt_dir, ipu_cmd, ipu_dvt_name, ipu_loops, gdmac_cmd, d2d_dvt_name, d2d_loops):
    high_loops, low_loops, inner_loops = ipu_loops
    p_lst = []
    q1 = mp.Queue()
    q2 = mp.Queue()
    
    allPassed = True
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.1)
        p1 = mp.Process(target=CAM.mlu370_new_power_one_card, args=(q1, mcPort, 'mlu370 D2D PITest-Fix-Burst', ipu_cmd, high_loops, low_loops, inner_loops, dvt_dir, ipu_dvt_name, 27))
        p1.start()
        p_lst.append(p1)
        
        time.sleep(0.1)
        p2 = mp.Process(target=CAM.mlu370_new_gdmac_test, args=(q2, mcPort, 'mlu370 Fix-Burst D2D-GDMAC', gdmac_cmd, d2d_loops, dvt_dir, d2d_dvt_name, 27))
        p2.start()
        p_lst.append(p2)
    
        time.sleep(0.5)
        [ p.join() for p in p_lst]
        
        res_ipu = q1.get()
        res_d2d = q2.get()
        if not res_ipu or not res_d2d:
            logging.info("Card{} res_ipu --> {}".format(str(mcPort), res_ipu))
            logging.info("Card{} res_d2d --> {}".format(str(mcPort), res_d2d))
            allPassed = False
    return allPassed

def main(args):
    case_name = 'mlu370 PITest Fix Burst and D2D Test'
    logging.info(case_name, section=True)
    
    dvt_dir = 'power-d2d'
    ipu_dvt_name = 'fix-ehpi-burst'
    d2d_dvt_name = 'gdmac'
    
    board_type = CAM.get_mlu370_type('0')
    logging.info('Running mlu370-{} type boards'.format(board_type))
    
    d2d_loops = args.d2d.strip() if args.d2d else '1'
    power_loops = args.power.strip() if args.power else '1'
    gdmac_cmd = 'mlu370_pcie_gdma_d2d'
    
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
    ipu_cmd = cmd_dict[board_type]
    
    high_loops = args.high.strip() if args.high else '1000'
    low_loops = args.low.strip() if args.low else '3320'
    inner_loops = args.inner.strip() if args.inner else '5'
    ipu_loops = [str(high_loops), str(low_loops), str(inner_loops)]
    dimz_loops = str(int(power_loops) * 100000)
    
    CAM.mlu370_dimz('fix_test', 'ehpi_burst_30MHz_u1', dimz_loops)
    CAM.mlu370_dimz('fix_test', 'ehpi_burst_30MHz_u4', dimz_loops)
    CAM.mlu370_dimz('fix_test', 'ehpi_burst_30MHz_u8', dimz_loops)
        
    logging.info('Running PITest Fix Burst {} {} {} {} <dimz:{}>'.format(ipu_cmd, ipu_loops[0], ipu_loops[1], ipu_loops[2], dimz_loops))
    logging.info('Running D2D-GDMAC <{}> {} loops'.format(gdmac_cmd, d2d_loops))
    
    if UTP.get('MFG_MODE', None) or args.mfg:
        logging.info('Running with factory serial mode')
        result = 'PASS' if st_run_DMA_IPU_Test(dvt_dir, ipu_cmd, ipu_dvt_name, ipu_loops, gdmac_cmd, d2d_dvt_name, d2d_loops) else 'FAIL'
    else:
        result = 'PASS' if mt_run_DMA_IPU_Test(dvt_dir, ipu_cmd, ipu_dvt_name, ipu_loops, gdmac_cmd, d2d_dvt_name, d2d_loops) else 'FAIL'
    
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
    parser.add_argument('-d', '--d2d', action='store', help='D2D-GDMAC loops')
    parser.add_argument('-p', '--power', action='store', help='Power loops')
    parser.add_argument('--mfg', action='store_true', help='Host PC Mode')
    args = parser.parse_args()
    sys.exit(main(args))
