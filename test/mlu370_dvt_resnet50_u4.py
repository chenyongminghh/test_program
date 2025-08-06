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

def mt_run_resnet_test(caseName, resnet_cmd, loops, dimz, dvt_dir, dvt_name):
    p_lst = []
    q = mp.Queue()
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.1)
        p = mp.Process(target=CAM.mlu370_resnet_u4_one_card, args=(q, mcPort, caseName, resnet_cmd, loops, dimz, dvt_dir, dvt_name))
        p.start()
        p_lst.append(p)
    time.sleep(0.5)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for mcPort in range(mcPorts):
        res = q.get()
        if not res:
            logging.info("Card{} res --> {}".format(str(mcPort), res))
            allPassed = False
    return allPassed

def main(args):
    case_name = 'mlu370 DVT Resnet50 U4 Test'
    logging.info(case_name, section=True)
    
    board_type = CAM.get_mlu370_type('0')
    logging.info('Running {} type boards'.format(board_type))
    
    loops = args.loops.strip() if args.loops else '1'
    dimz = args.dimz.strip() if args.dimz else '1'
    
    cmd_dict = dict()
    cmd_dict['S4'] = 'mlu370_handng_resnet50_u4'
    cmd_dict['S8'] = 'mlu370_handng_resnet50_u4'
    cmd_dict['X9'] = 'mlu370_handng_resnet50_u4'
    cmd_dict['X9L'] = 'mlu370_handng_resnet50_u4'
    cmd_dict['X8'] = 'mlu370_handng_resnet50_u4'
    cmd_dict['X4'] = 'mlu370_handng_resnet50_2u4'
    cmd_dict['EVBD'] = 'mlu370_handng_resnet50_2u4'
    cmd_dict['M8'] = 'mlu370_handng_resnet50_2u4'
    cmd_dict['X4K'] = 'mlu370_handng_resnet50_2u4'
    cmd_dict['X4L'] = 'mlu370_handng_resnet50_2u4'
    
    dvt_dir = 'dvt-net'
    dvt_name = 'resnet50-u4'
    resnet_cmd = cmd_dict[board_type]
    logging.info('Running {} {} {}'.format(resnet_cmd, loops, dimz))
    
    result = 'PASS' if mt_run_resnet_test(case_name, resnet_cmd, loops, dimz, dvt_dir, dvt_name) else 'FAIL'
    
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
    parser.add_argument('--dimz', action='store', help='override dimz loops')
    args = parser.parse_args()
    sys.exit(main(args))
