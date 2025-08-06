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

def mt_run_dvt_Test(caseName, dvt_type, case_type, case_list, dvt_loops, dvt_dir):
    p_lst = []
    q = mp.Queue()
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.1)
        p = mp.Process(target=CAM.mlu370_cnnl_one_card, args=(q, mcPort, caseName, dvt_type, case_type, case_list, dvt_loops, dvt_dir))
        p.start()
        p_lst.append(p)
    time.sleep(0.5)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for mcPort in range(mcPorts):
        res = q.get()
        if not res:
            logging.error("Card{} res --> {}".format(mcPort, res))
            allPassed = False
    return allPassed

def main(args):
    case_name = 'mlu370 DVT CNNL Test'
    logging.info(case_name, section=True)
    
    test_list = CAM.get_dvt_list('cnnl')
    logging.info('Running <{}> CNNL test cases'.format(len(test_list)))
    
    test_loops = args.loops.strip() if args.loops else '1'
    logging.info('Running DVT CNNL Test <{}> loops'.format(test_loops))
    
    dvt_type = 'cnnl'
    case_type = 'cnnl'
    dvt_dir = 'dvt-ng'
    result = 'PASS' if mt_run_dvt_Test(case_name, dvt_type, case_type, test_list, test_loops, dvt_dir) else 'FAIL'
    
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
