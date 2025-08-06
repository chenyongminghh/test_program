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

def mt_run_NCS_IPU_Test(dvt_dir, ipu_cmd, ipu_dvt_name, ipu_loops, ncs_loops):
    high_loops, low_loops, inner_loops = ipu_loops
    p_lst = []
    q1 = mp.Queue()
    q2 = mp.Queue()
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.1)
        p1 = mp.Process(target=CAM.mlu370_new_power_one_card, args=(q1, mcPort, 'mlu370 NCS PITest-Fix-Maxpower', ipu_cmd, high_loops, low_loops, inner_loops, dvt_dir, ipu_dvt_name, 30))
        p1.start()
        p_lst.append(p1)
        
        time.sleep(0.1)
        p2 = mp.Process(target=CAM.mlu370_x8_ncs_one_card, args=(q2, mcPort, 'mlu370 Fix-Maxpower Driver-NCS', ncs_loops, dvt_dir, 30))
        p2.start()
        p_lst.append(p2)
    time.sleep(0.5)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for mcPort in range(mcPorts):
        res_ipu = q1.get()
        res_ncs = q2.get()
        if not res_ipu or not res_ncs:
            logging.info("Card{} res_ipu --> {}".format(str(mcPort), res_ipu))
            logging.info("Card{} res_ncs --> {}".format(str(mcPort), res_ncs))
            allPassed = False
    return allPassed

def st_run_NCS_IPU_Test(dvt_dir, ipu_cmd, ipu_dvt_name, ipu_loops, ncs_loops):
    high_loops, low_loops, inner_loops = ipu_loops
    p_lst = []
    q1 = mp.Queue()
    q2 = mp.Queue()
    
    allPassed = True
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.1)
        p1 = mp.Process(target=CAM.mlu370_new_power_one_card, args=(q1, mcPort, 'mlu370 NCS PITest-Fix-Maxpower', ipu_cmd, high_loops, low_loops, inner_loops, dvt_dir, ipu_dvt_name, 30))
        p1.start()
        p_lst.append(p1)
        
        time.sleep(0.1)
        p2 = mp.Process(target=CAM.mlu370_x8_ncs_one_card, args=(q2, mcPort, 'mlu370 Fix-Maxpower Driver-NCS', ncs_loops, dvt_dir, 30))
        p2.start()
        p_lst.append(p2)
    
        time.sleep(0.5)
        [ p.join() for p in p_lst]
        
        res_ipu = q1.get()
        res_ncs = q2.get()
        if not res_ipu or not res_ncs:
            logging.info("Card{} res_ipu --> {}".format(str(mcPort), res_ipu))
            logging.info("Card{} res_ncs --> {}".format(str(mcPort), res_ncs))
            allPassed = False
    return allPassed

def get_driver_version():
    driver_version = 0
    output = UTP.run("cat /proc/driver/cambricon/mlus/*/information |grep 'Driver Version:' ", shell=True, check=False)
    for line in output.splitlines():
        driver_version = line.split(':')[1].strip()
    return driver_version


def main(args):
    case_name = 'mlu370 PITest Fix Maxpower and NCS Test'
    logging.info(case_name, section=True)
    
    dvt_dir = 'power-ncs'
    ipu_dvt_name = 'fix-maxpower'
    
    board_type = CAM.get_mlu370_type('0')
    logging.info('Running mlu370-{} type boards'.format(board_type))
    
    ncs_loops = args.ncs.strip() if args.ncs else '1'
    power_loops = args.power.strip() if args.power else '1'
    
    cmd_dict = dict()
    cmd_dict['X8'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U4'
    cmd_dict['X9'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U6'
    cmd_dict['X9L'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U6'
    cmd_dict['X4'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U8'
    cmd_dict['EVBD'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U8'
    cmd_dict['M8'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U8'
    cmd_dict['X4K'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U8'
    cmd_dict['X4L'] = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U8'
    ipu_cmd = cmd_dict[board_type]
    
    ipu_loops = ['2500', '0', '0']
    current_driver_version = get_driver_version()
    if current_driver_version in ["v4.20.20", "v4.20.24"]:
        logging.info('Current driver version {}'.format(current_driver_version))
        dimz_loops = "65535"
    else:
        dimz_loops = str(int(power_loops) * 100000)
    
    CAM.mlu370_dimz('fix_test', 'maxp_u1', dimz_loops)
    CAM.mlu370_dimz('fix_test', 'maxp_u4', dimz_loops)
    CAM.mlu370_dimz('fix_test', 'maxp_u8', dimz_loops)
    
    logging.info('Running PITest Fix Maxpower {} {} {} {} <dimz:{}>'.format(ipu_cmd, ipu_loops[0], ipu_loops[1], ipu_loops[2], dimz_loops))
    logging.info('Running Driver-NCS {} loops'.format(ncs_loops))
    
    if args.mfg:
        logging.info('Running with factory serial mode')
        result = 'PASS' if st_run_NCS_IPU_Test(dvt_dir, ipu_cmd, ipu_dvt_name, ipu_loops, ncs_loops) else 'FAIL'
    else:
        result = 'PASS' if mt_run_NCS_IPU_Test(dvt_dir, ipu_cmd, ipu_dvt_name, ipu_loops, ncs_loops) else 'FAIL'
    
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
    parser.add_argument('-n', '--ncs', action='store', help='NCS loops')
    parser.add_argument('-p', '--power', action='store', help='Power loops')
    parser.add_argument('--mfg', action='store_true', help='Host PC Mode')
    args = parser.parse_args()
    sys.exit(main(args))
