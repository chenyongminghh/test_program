#!/usr/bin/env python3

import os
import os.path as osp
import sys
import time
import logging

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
    
    #logging.info('Get BMC <{}> sensor data'.format(imm_num))
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

def check_master_psu(p_out, i_out, v_out):
    res_p = True if float(p_out)>0 else False
    res_i = True if float(i_out)>0 else False
    res_v = True if float(v_out)>54 else False
    res_all = res_p and res_i and res_v
    logging.info('POUT:{}W  IOUT:{}A  VOUT:{}V  Check Result:{}'.format(p_out, i_out, v_out, res_all))
    return res_all

def check_slave_psu(p_out, i_out, v_out):
    res_p = True if float(p_out)<20 else False
    res_i = True if float(i_out)==0 else False
    res_v = True if float(v_out)>52 and float(v_out)<53.5 else False
    res_all = res_p and res_i and res_v
    logging.info('POUT:{}W  IOUT:{}A  VOUT:{}V  Check Result:{}'.format(p_out, i_out, v_out, res_all))
    return res_all

def master_psu_check(psu_slot, psu_sensor_values):
    if psu_slot == 'psu0':
        p_out = psu_sensor_values.get('psu0_pout')
        i_out = psu_sensor_values.get('psu0_iout')
        v_out = psu_sensor_values.get('psu0_vout')
    elif psu_slot == 'psu1':
        p_out = psu_sensor_values.get('psu1_pout')
        i_out = psu_sensor_values.get('psu1_iout')
        v_out = psu_sensor_values.get('psu1_vout')
    else:
        logging.error('Please check the parameter')
        CAM.record_fail_case('BMC PSU Cold Backup Test')
        raise Exception('Please check the parameter')
    
    res_p = True if float(p_out)>0 else False
    res_i = True if float(i_out)>0 else False
    res_v = True if float(v_out)>=53 and float(v_out)<=56 else False
    psu_check_result = res_p and res_i and res_v
    
    logging.info('Master PSU --> POUT:{}W  IOUT:{}A  VOUT:{}V --> Check Result:{}'.format(p_out, i_out, v_out, psu_check_result))
    return psu_check_result

def slave_psu_check(psu_slot, psu_sensor_values):
    if psu_slot == 'psu0':
        p_out = psu_sensor_values.get('psu0_pout')
        i_out = psu_sensor_values.get('psu0_iout')
        v_out = psu_sensor_values.get('psu0_vout')
    elif psu_slot == 'psu1':
        p_out = psu_sensor_values.get('psu1_pout')
        i_out = psu_sensor_values.get('psu1_iout')
        v_out = psu_sensor_values.get('psu1_vout')
    else:
        logging.error('Please check the parameter')
        CAM.record_fail_case('BMC PSU Cold Backup Test')
        raise Exception('Please check the parameter')
    
    res_p = True if float(p_out)<20 else False
    res_i = True if float(i_out)==0 else False
    res_v = True if float(v_out)>50 and float(v_out)<=53 else False
    psu_check_result = res_p and res_i and res_v
        
    logging.info('Slave PSU --> POUT:{}W  IOUT:{}A  VOUT:{}V --> Check Result:{}'.format(p_out, i_out, v_out, psu_check_result))
    return psu_check_result

def main():
    case_name = 'BMC PSU Cold Backup Test'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    all_passed = True
    for imm_num in range(imm_qty):
        logging.info('BMC <{}> Keep PSU0 on, Keep PSU1 off'.format(imm_num))
        imm.set_psu_cold_backup(imm_num, psu0='0x00', psu1='0x02')
        time.sleep(10)
        
        psu_sensor_values = {}
        sensors_dict = get_ipmi_sensors_list(imm_num)
        for sensor_name in sensors_dict.keys():
            if 'psu' in sensor_name[:3] and 'out' in sensor_name:
                psu_value = sensors_dict.get(sensor_name)
                psu_sensor_values[sensor_name] = psu_value
        
        if master_psu_check('psu0', psu_sensor_values) and slave_psu_check('psu1', psu_sensor_values):
            logging.info('BMC <{}> PSU0 as master and PSU1 as slave check PASSED.'.format(imm_num))
        else:
            logging.error('BMC <{}> PSU0 as master and PSU1 as slave check FAILED.'.format(imm_num))
            all_passed = False
        
        #logging.info('BMC <{}> setting PSU0 as slave and PSU1 as master'.format(imm_num))
        imm.set_psu_cold_backup(imm_num, psu0='0x02', psu1='0x00')
        time.sleep(10)
        psu_sensor_values = {}
        sensors_dict = get_ipmi_sensors_list(imm_num)
        for sensor_name in sensors_dict.keys():
            if 'psu' in sensor_name[:3] and 'out' in sensor_name:
                psu_value = sensors_dict.get(sensor_name)
                psu_sensor_values[sensor_name] = psu_value
        
        if master_psu_check('psu1', psu_sensor_values) and slave_psu_check('psu0', psu_sensor_values):
            logging.info('BMC <{}> PSU0 as slave and PSU1 as master check PASSED.'.format(imm_num))
        else:
            logging.error('BMC <{}> PSU0 as slave and PSU1 as master check FAILED.'.format(imm_num))
            all_passed = False
        
        imm.set_psu_cold_backup(imm_num, psu0='0x00', psu1='0x00')
        time.sleep(5)
    
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
