#!/usr/bin/env python3

import sys
import logging
import argparse
import collections
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')
sys.path.append(modules_path)
import UTP
import CAM

MonitorStatus = collections.namedtuple('TemperatureMonitorResult',
                                      ('slot', 'serial_number', 'total_times', 'fail_times', 'max_diff', 'ambient_temp', 'first_fail_times', 'status'))

def monitor_log_check(mcPort, mcSN, ambient_temp, allow_temp_diff, compares):
    # line = "20220126-162507 BA:532101300121 VER:v1.1.3 Power:33 ChipTemp:45 BoardTemp:43"
    monitor_log_file = osp.join(logs_path, "monitor_card{}_{}.log".format(mcPort, mcSN))
    if not osp.exists(monitor_log_file):
        logging.error('File Not Find <{}>'.format(osp.basename(monitor_log_file)))
        compares.append(MonitorStatus('Card{}'.format(mcPort), mcSN, '0', '0', '0', ambient_temp, '0', 'fail'))
        return compares
    
    slot_num = 'Card{}'.format(mcPort)
    total_times = 0
    temp_diff_list = []
    failure_times_list = []
    with open(monitor_log_file) as rf:
        lines = rf.readlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "ChipTemp:" not in line:
            continue
        chip_temp = line.split()[4].strip().split(':')[1]
        total_times += 1
        temp_diff = int(chip_temp) - int(ambient_temp)
        if temp_diff > allow_temp_diff:
            temp_diff_list.append(temp_diff)
            failure_times_list.append(total_times)
    
    fail_times = len(failure_times_list)
    max_temp_diff = max(temp_diff_list) if temp_diff_list else 0
    first_failure_times = failure_times_list[0] if failure_times_list else '0'
    check_result = 'fail' if failure_times_list else 'pass'
    
    logging.debug('{}, {}, {}, {}, {}, {}'.format(str(total_times), str(fail_times), str(max_temp_diff), str(ambient_temp), first_failure_times, check_result))
    compares.append(MonitorStatus(slot_num, mcSN, total_times, fail_times, max_temp_diff, ambient_temp, first_failure_times, check_result))
    return compares

def main(args):    
    case_name = 'mlu370 X4L Temperature Monitor Check'
    logging.info('{}'.format(case_name), section=True)
    
    ambient_temp = args.ambtemp if args.ambtemp in range(61) else 0
    allow_temp_diff = args.maxdiff if args.maxdiff in range(61) else 55
    
    compares = []
    port_sn_dict = dict()
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = CAM.get_sn(mcPort)
        port_sn_dict[mcPort] = mcSN
        monitor_log_check(mcPort, mcSN, ambient_temp, allow_temp_diff, compares)
    
    sn_port_dict = {value:key for key,value in port_sn_dict.items()}
    header = [x.replace('_', ' ').title() for x in MonitorStatus._fields]
    logging.info(compares, table={'header': header, 'name': 'mlu370 Temperature Monitor Results', 'str_is_str': True, 'max_col_width': 80})
    
    for x in compares:
        if x.status == 'fail':
            mc_serial_number = x.serial_number
            mc_port = sn_port_dict[mc_serial_number]
            failure_message = '{} Failed on Card{}'.format(case_name, mc_port)
            logging.error('{}'.format(failure_message))
            CAM.record_card_fail(mc_port, mc_serial_number, case_name, failure_message)
    
    errors = [x for x in compares if x.status == 'fail']
    result = 'PASS' if not errors else 'FAIL'
    
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
        raise Exception('There are some fail info detected')
    return
    
if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--ambtemp', action='store', type=int, help='Ambient Temp, Such as water temp')
    parser.add_argument('-d', '--maxdiff', action='store', type=int, help='Allow Max Diff Temp')
    args = parser.parse_args()
    sys.exit(main(args))
    