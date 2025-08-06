#!/usr/bin/env python3

import os
import sys
import time
import logging
import argparse
import subprocess
import os.path as osp
import multiprocessing as mp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import IMM
import CAM

def get_ipmi_sensors_list(imm_num=0, ipmi_sensors_list={}):
    """! Get sensors output
    @return Dictionary of sensor names and values, all as strings
    """
    imm = IMM.IMM()
    #logging.info('Force generation of new ipmi sensor files.')
    sensor_log = osp.join(logs_path, 'ipmi_sensors_{}.log'.format(imm_num))
    if osp.exists(sensor_log):
        os.unlink(sensor_log)
    
    #logging.info('Get BMC <{}> sensor data.'.format(imm_num))
    sensor_data = imm.get_ipmi_sensors_list(imm_num)
    #logging.info('Log BMC <{}> sensor data to {}'.format(imm_num, sensor_log))
    with open(sensor_log, mode='w') as fh:
        fh.write(sensor_data)
    
    with open(sensor_log) as sensor_file:
        for sensor_data_line in sensor_file:
            if '|' not in sensor_data_line:
                continue
            sname, svalue = sensor_data_line.strip().split('|')[:2]
            ipmi_sensors_list[ sname.strip().lower() ] = svalue.strip()
    
    return ipmi_sensors_list

def check_psu_pout(imm_num, psu_pout):
    sensors_dict = get_ipmi_sensors_list(imm_num)
    logging.info('{} --> {}'.format(psu_pout, sensors_dict.get(psu_pout.lower())))
    return sensors_dict.get(psu_pout.lower())

def main(args):
    case_name = 'BMC PSU State Setting'
    logging.info('{}'.format(case_name), section=True)
    
    psu0_state = args.psu0.strip() if args.psu0 else 'on'
    psu1_state = args.psu1.strip() if args.psu1 else 'on'
    logging.info('Setting PSU0 <{}> and PSU1 <{}>'.format(psu0_state, psu1_state))
    
    if psu0_state == psu1_state == 'off':
        logging.error('Cannot setting PSU0 off and PSU1 off')
        CAM.record_fail_case(case_name)
        raise Exception('Cannot setting PSU0 off and PSU1 off')
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    all_passed = True
    psu0_raw = '0xa1' if psu0_state == 'on' else '0xa0'
    psu1_raw = '0xa1' if psu1_state == 'on' else '0xa0'
    for imm_num in range(imm_qty):
        logging.info('BMC <{}> setting start'.format(imm_num))
        imm.set_psu_status(imm_num, psu0=psu0_raw, psu1=psu1_raw)
        time.sleep(5)
        
        if psu0_state == 'off':
            if check_psu_pout(imm_num, 'PSU0_POUT') == '0.000':
                logging.info('BMC <{}> setting PSU0 off Success'.format(imm_num))
            else:
                logging.error('BMC <{}> setting PSU0 off Failed'.format(imm_num))
                all_passed = False
        else:
            if check_psu_pout(imm_num, 'PSU0_POUT') == '0.000':
                logging.error('BMC <{}> setting PSU0 on Failed'.format(imm_num))
                all_passed = False
            else:
                logging.info('BMC <{}> setting PSU0 on Success'.format(imm_num))
        
        if psu1_state == 'off':
            if check_psu_pout(imm_num, 'PSU1_POUT') == '0.000':
                logging.info('BMC <{}> setting PSU1 off Success'.format(imm_num))
            else:
                logging.error('BMC <{}> setting PSU1 off Failed'.format(imm_num))
                all_passed = False
        else:
            if check_psu_pout(imm_num, 'PSU1_POUT') == '0.000':
                logging.error('BMC <{}> setting PSU1 on Failed'.format(imm_num))
                all_passed = False
            else:
                logging.info('BMC <{}> setting PSU1 on Success'.format(imm_num))
    
    result = 'PASS' if all_passed else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        CAM.record_fail_case(case_name)
        raise Exception('Some failure detected, please check the log.')
    return

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--psu0', action='store', choices=['on', 'off'], help='PSU0 State')
    parser.add_argument('--psu1', action='store', choices=['on', 'off'], help='PSU1 State')
    args = parser.parse_args()
    sys.exit(main(args))
