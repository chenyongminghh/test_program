#!/usr/bin/env python3

import os
import sys
import time
import logging
import subprocess
import os.path as osp
import multiprocessing as mp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')
sttools_path = osp.join(testcode_path, 'sttools')
dvt_path = osp.join(sttools_path, 'mlu290_dvt_test/driver_dvt_test/data')
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

def run_fix_maxpower():
    case_name = 'mlu370 Power Fix Maxpower Test'
    high_loops = '2500'
    low_loops = '0'
    inner_loops = '100000'
    dimz_loops = '10'
    
    dvt_dir = 'dvt-power'
    dvt_name = 'fix_maxpower'
    ipu_cmd = 'mlu370_ipu_IPU_INST_FIX_MAXPOWER_U8'
    CAM.mlu370_dimz('fix_test', 'maxp_u1', dimz_loops)
    CAM.mlu370_dimz('fix_test', 'maxp_u4', dimz_loops)
    CAM.mlu370_dimz('fix_test', 'maxp_u8', dimz_loops)
    logging.info('Running {} {} {} {} <dimz:{}>'.format(ipu_cmd, high_loops, low_loops, inner_loops, dimz_loops))
    res_maxpower = CAM.mt_run_power_Test(case_name, ipu_cmd, high_loops, low_loops, inner_loops, dvt_dir, dvt_name)
    return res_maxpower

def check_psu_pout(imm_num, psu_pout):
    sensors_dict = get_ipmi_sensors_list(imm_num)
    logging.info('{} --> {}'.format(psu_pout, sensors_dict.get(psu_pout.lower())))
    if sensors_dict.get(psu_pout.lower()) == '0.000':
        return True
    else:
        return False

def main():
    case_name = 'BMC PSU Single Power Test'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    all_passed = True
    for imm_num in range(imm_qty):
        logging.info('BMC <{}> setting PSU0 on and PSU1 on'.format(imm_num))
        imm.set_psu_status(imm_num, psu0='0xa1', psu1='0xa1')
        time.sleep(5)
        
        imm.set_psu_status(imm_num, psu0='0xa1', psu1='0xa0')
        time.sleep(5)
        if check_psu_pout(imm_num, 'PSU1_POUT'):
            logging.info('BMC <{}> setting PSU0 on and PSU1 off Passed'.format(imm_num))
            if run_fix_maxpower():
                logging.info('BMC <{}> PSU0 on and PSU1 off --> Max Power Test Passed'.format(imm_num))
            else:
                logging.error('BMC <{}> PSU0 on and PSU1 off --> Max Power Test Failed'.format(imm_num))
                all_passed = False
        else:
            logging.error('BMC <{}> setting PSU0 on and PSU1 off Failed'.format(imm_num))
            all_passed = False
        logging.info('Wait 30 seconds')
        time.sleep(30)
        
        imm.set_psu_status(imm_num, psu0='0xa0', psu1='0xa1')
        time.sleep(5)
        if check_psu_pout(imm_num, 'PSU0_POUT'):
            logging.info('BMC <{}> setting PSU0 off and PSU1 on Passed'.format(imm_num))
            if run_fix_maxpower():
                logging.info('BMC <{}> PSU0 off and PSU1 on --> Max Power Test Passed'.format(imm_num))
            else:
                logging.error('BMC <{}> PSU0 off and PSU1 on --> Max Power Test Failed'.format(imm_num))
                all_passed = False
        else:
            logging.error('BMC <{}> setting PSU0 off and PSU1 on Failed'.format(imm_num))
            all_passed = False
        logging.info('Wait 30 seconds')
        time.sleep(30)
        
        logging.info('BMC <{}> setting PSU0 on and PSU1 on'.format(imm_num))
        imm.set_psu_status(imm_num, psu0='0xa1', psu1='0xa1')
        time.sleep(5)
        if check_psu_pout(imm_num, 'PSU0_POUT') or check_psu_pout(imm_num, 'PSU1_POUT'):
            logging.error('BMC <{}> setting PSU0 on and PSU1 on Failed'.format(imm_num))
            all_passed = False
    
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
    sys.exit(main())
