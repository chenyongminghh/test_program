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
    log_fname = osp.join(logs_path, '{}/{}'.format(CAM.format_dirname(mcPort, mcSN, 'voltage'), CAM.format_fname(mcPort, mcSN, dvt_name='soc_voltage')))
    
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
    record_list = dict()
    for line in return_context.splitlines():
        line = line.strip()
        if line.startswith('Link '):
            if record:
                k,v = record.split(':')
                record_list[k.strip()] = v.strip()
                record = None
            value = line.split(':')[0].strip()
            record = '{}:'.format('_'.join(value.split()))
        elif 'err_uncorrected' in line:
            key, value = line.split(':', 1)
            record = record + value.strip()
    
    if record:
        k,v = record.split(':')
        record_list[k.strip()] = v.strip()
    
    return record_list
    print(record_list)

def mt_run_test(caseName, debug_tool):
    total_info = dict()
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = CAM.get_sn(mcPort)
        
        dev_key = '{}_dev{}'.format(mcSN, mcPort)
        rtn_dict = read_fec_count(mcPort, mcSN, caseName, debug_tool)
        total_info[dev_key] = rtn_dict
    
    for k,v in total_info.items():
        logging.info('{} {}'.format(k, v))
    
    json_file = osp.join(logs_path, 'fec.json')
    with open(json_file, 'w') as f:
        json.dump(total_info, f)

def main(args):
    case_name = 'mlu370 Mlulink Fec Record'
    logging.info('{}'.format(case_name), section=True)
    
    debug_tool = UTP.get('CNMON_TOOL', 'cnmon')
    logging.info('Cnmon Tool {}'.format(debug_tool))
    debug_tool_path = osp.join(utilities_path, debug_tool)
    mt_run_test(case_name, debug_tool_path)
    logging.info('{} Complete'.format(case_name))
    
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    sys.exit(main(args))
