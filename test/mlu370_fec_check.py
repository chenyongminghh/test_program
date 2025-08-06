#!/usr/bin/env python3

import os
import sys
import json
import time
import logging
import argparse
import subprocess
import os.path as osp
from datetime import datetime
from collections import OrderedDict

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
utilities_path = osp.join(testcode_path, 'utilities')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import CAM

def read_fec_count(mcPort, mcSN, caseName, debug_tool):
    mcPort = str(mcPort)
    log_fname = osp.join(logs_path, '{}/{}'.format(CAM.format_dirname(mcPort, mcSN, 'voltage'), CAM.format_fname(mcPort, mcSN, dvt_name='cnmon_mlulink')))
    
    # sudo ./cnmon mlulink -c 0 -o
    test_cmd = [debug_tool, 'mlulink', '-c', mcPort, '-o']
    
    case_name_format = caseName.ljust(len(caseName))
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    
    start_time = datetime.now()
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('###{} End on {}\n\n'.format(caseName, time.ctime()))
    
    if proc.returncode:
        logging.error('{} Failed on Card{} with returncode {}'.format(case_name_format, mcPort, proc.returncode))
        return False
    return_context = ''
    return_context = proc.stdout.decode('utf-8')
    
    record = None
    record_list = OrderedDict()
    for line in return_context.splitlines():
        line = line.strip()
        if line.startswith('Link '):
            if record:
                k,v = record.split(':')
                record_list[k.strip()] = v.strip()
                record = None
            value = line.split(':')[0].strip()
            record = '{}: '.format('_'.join(value.split()))
            record1 = value.split()[0]+'_'+value.split()[1]
        elif 'err_replay' in line:
            key, value = line.split(':', 1)
            record = record + 'err_replay-{} '.format(value.strip())
        elif 'err_uncorrected' in line:
            key, value = line.split(':', 1)
            record = record + 'err_uncorrected-{} '.format(value.strip())
    if record:
        k,v = record.split(':')
        record_list[k.strip()] = v.strip()
    return record_list

def mt_run_test(caseName, debug_tool, load_dict):
    allPassed = True
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = CAM.get_sn(mcPort)
        
        card_result = True
        dev_key = '{}_dev{}'.format(mcSN, mcPort)
        rtn_dict = read_fec_count(mcPort, mcSN, caseName, debug_tool)
        for key in rtn_dict.keys():
            err_replay = rtn_dict[key].split()[0].split('-')[1]
            err_uncorrected = rtn_dict[key].split()[1].split('-')[1]
            if int(err_uncorrected) - int(load_dict[dev_key][key]) > 1:
                #card_result = False
                failure_message = '{}_dev{} {} FEC     InitValue:{} CurrentValue:{}'.format(mcSN, mcPort, key, load_dict[dev_key][key], err_uncorrected)
                logging.error('{}'.format(failure_message))
                CAM.record_card_warn(mcPort, mcSN, caseName, failure_message)
            else:
                logging.info('{}_dev{} {} FEC     InitValue:{} CurrentValue:{}'.format(mcSN, mcPort, key, load_dict[dev_key][key], err_uncorrected))
            
            if err_replay != '0':
                failure_message = '{}_dev{} {} Retrans InitValue:0 CurrentValue:{}'.format(mcSN, mcPort, key, err_replay)
                logging.info('{}'.format(failure_message))
                CAM.record_card_warn(mcPort, mcSN, caseName, failure_message)
            #else:
            #    logging.info('{}_dev{} {} Retrans InitValue:0 CurrentValue:{}'.format(mcSN, mcPort, key, err_replay))
        if not card_result:
            allPassed = False
            failure_message = 'Failed on Card{}'.format(mcPort)
            logging.error('{} {}'.format(caseName, failure_message))
            CAM.record_card_fail(mcPort, mcSN, caseName, failure_message)
    return allPassed

def main(args):
    case_name = 'mlu370 Mlulink Fec Check'
    logging.info('{}'.format(case_name), section=True)
    
    debug_tool = UTP.get('CNMON_TOOL', 'cnmon')
    logging.info('Cnmon Tool {}'.format(debug_tool))
    debug_tool_path = osp.join(utilities_path, debug_tool)
    
    json_file = osp.join(logs_path, 'fec.json')
    with open(json_file, 'r') as load_f:
        load_dict = json.load(load_f)
    
    result = 'PASS' if mt_run_test(case_name, debug_tool_path, load_dict) else 'FAIL'
    if result == 'PASS':
        logging.info('{} successfully'.format(case_name))
    elif UTP.get('MFG_FAIL_MODE', None):
        logging.error('{} FAILED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} failed'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        logging.info('{} failed'.format(case_name))
        CAM.record_fail_case(case_name)
        raise Exception('There are some fail info detected, please check the log.')
    
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    sys.exit(main(args))
