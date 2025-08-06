#!/usr/bin/env python3

import os
import sys
import time
import logging
import argparse
import os.path as osp
import multiprocessing as mp


testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
utilities_path = osp.join(testcode_path, 'utilities')
modules_path = osp.join(testcode_path, 'modules')

sys.path.append(modules_path)
import UTP
import CAM

def mt_run_DDR_Test(dvt_dir, ddr_tool, ddr_loops):
    p_lst = []
    q = mp.Queue()
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.1)
        p = mp.Process(target=CAM.mlu370_ddr_power_one_card, args=(q, mcPort, 'mlu370 DDR Maxpower Start', ddr_tool, ddr_loops, dvt_dir, 27, '18'))
        p.start()
        p_lst.append(p)
    time.sleep(0.5)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for mcPort in range(mcPorts):
        res_ddr = q.get()
        if not res_ddr:
            logging.info("Card{} res_ddr --> {}".format(str(mcPort), res_ddr))
            allPassed = False
    return allPassed

def main(args):
    case_name = 'mlu370 DDR Maxpower Starting Test'
    logging.info(case_name, section=True)
    
    dvt_dir = 'power-ddr'
    ddr_tool = UTP.get('STRESS_DDR', '')    
    ddr_tool_path = osp.join(utilities_path, ddr_tool)
    logging.info('Stress DDR tool {}'.format(ddr_tool))
    
    test_loops = args.loops.strip() if args.loops else '1'
    logging.info('Running DDRStress <{}> loops'.format(test_loops))
    
    result = 'PASS' if mt_run_DDR_Test(dvt_dir, ddr_tool_path, test_loops) else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('MFG_FAIL_MODE', None):
        logging.error('{} FAILED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.error('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        logging.error('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
        raise Exception('There are some fail info detected, please check logs file')
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--loops', action='store', help='override default loops')
    args = parser.parse_args()
    sys.exit(main(args))
