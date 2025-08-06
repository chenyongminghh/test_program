#!/usr/bin/env python3

import argparse
import collections
import logging
import re
import sys
import os
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import IMM
import CAM

nvme_sensors = ['hd0_status', 'hd1_status', 'hd2_status', 'hd3_status']

def check_status(sensors_dict):
    test_hdd_result = True
    hdd_sensor_values = {}
    for sensor_name in sensors_dict.keys():
        if sensor_name.startswith('hd') and sensor_name.endswith('status'):
            sensor_value = sensors_dict.get(sensor_name)
            hdd_sensor_values[sensor_name] = sensor_value

    for sensor_id in nvme_sensors:
        presence = hdd_sensor_values.get('%s' % sensor_id)
        if presence is None or presence == 'na':
            presence = 'Not Installed'
        else:
            presence = 'Installed'
        logging.info("Sensor %s Presence = %s" % (sensor_id, presence))
        if presence == 'Installed':
            continue
        else:
            emsg = 'ERROR: %s not present' % (sensor_id)
            test_hdd_result = False
    return test_hdd_result

def get_ipmi_sensors_list(imm_num=0):
    """! Get sensors output
    
    @return Dictionary of sensor names and values, all as strings
    """
    ipmi_sensors_list={}
    imm = IMM.IMM()
    logging.info('Force generation of new ipmi sensor files.')
    sensor_log_path = osp.join(logs_path, 'ipmi_sensors{}.log'.format(imm_num))
    if osp.exists(sensor_log_path):
        os.unlink(sensor_log_path)
    
    logging.info('Get BMC<{}> sensor data'.format(imm_num))
    sensor_data = imm.get_ipmi_sensors_list(imm_num)
    logging.info('Log BMC<{}> sensors data to ipmi_sensors{}.log'.format(imm_num, imm_num))
    with open(sensor_log_path, mode='w') as fh:
        fh.write(sensor_data)
    
    with open(sensor_log_path) as sensor_file:
        for sensor_data_line in sensor_file:
            if '|' not in sensor_data_line:
                continue
            sname, svalue = sensor_data_line.strip().split('|')[:2]
            ipmi_sensors_list[ sname.strip().lower() ] = svalue.strip()
    return ipmi_sensors_list
    
def main():
    case_name = 'BMC NVME Presence Check'
    logging.info(case_name, section=True)
    
    if int(UTP.get('NVME_QTY', '4')) == 0:
        logging.info('Config 0 NVME Disk, Skip checking')
        return
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    
    all_passed = True
    for imm_num in range(imm_qty):
        logging.info('BMC <{}> NVME Presence Check Start'.format(imm_num))
        sensors_dict = get_ipmi_sensors_list(imm_num)
        if check_status(sensors_dict):
            logging.info('BMC <{}> NVME Presence Check Passed'.format(imm_num))
        else:
            all_passed = False
            logging.error('BMC <{}> NVME Presence Check Failed'.format(imm_num))
    
    result = 'PASS' if all_passed else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
        raise Exception('There are some card boot failed.')
    return
    
if __name__ == '__main__':
    sys.exit(main())

