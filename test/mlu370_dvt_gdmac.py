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

def mt_run_dvt_test(caseName, gdmac_cmd, test_loops):
    p_lst = []
    q = mp.Queue()
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.5)
        p = mp.Process(target=CAM.mlu370_new_gdmac_test, args=(q, mcPort, caseName, gdmac_cmd, test_loops, 'dvt-gdmac', 'gdmac'))
        p.start()
        p_lst.append(p)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for mcPort in range(mcPorts):
        res_dvt = q.get()
        if not res_dvt:
            logging.info("Card{} res_dvt --> {}".format(str(mcPort), res_dvt))
            allPassed = False
    return allPassed

def st_run_dvt_test(caseName, gdmac_cmd, test_loops):
    p_lst = []
    q = mp.Queue()
    
    allPassed = True
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.5)
        p = mp.Process(target=CAM.mlu370_new_gdmac_test, args=(q, mcPort, caseName, gdmac_cmd, test_loops, 'dvt-gdmac', 'gdmac'))
        p.start()
        p_lst.append(p)
        [ p.join() for p in p_lst]
        
        res_dvt = q.get()
        if not res_dvt:
            logging.info("Card{} res_dvt --> {}".format(str(mcPort), res_dvt))
            allPassed = False
    return allPassed

def main(args):
    case_name = 'mlu370 DVT D2D-GDMAC Test'
    logging.info(case_name, section=True)
    
    gdmac_cmd = 'mlu370_pcie_gdma_d2d'
    test_loops = args.loops.strip() if args.loops else '1'
    logging.info('Running {} <{}> loops'.format(gdmac_cmd, test_loops))
    
    if UTP.get('MFG_MODE', None):
        logging.info('Running with factory serial mode')
        result = 'PASS' if st_run_dvt_test(case_name, gdmac_cmd, test_loops) else 'FAIL'
    else:
        result = 'PASS' if mt_run_dvt_test(case_name, gdmac_cmd, test_loops) else 'FAIL'
    
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
    parser.add_argument('--mfg', action='store_true', help='Host PC Mode')
    args = parser.parse_args()
    sys.exit(main(args))
