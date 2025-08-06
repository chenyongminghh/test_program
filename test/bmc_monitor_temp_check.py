#!/usr/bin/env python3

import os
import re
import sys
import logging
import argparse
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
logs_path = osp.join(testcode_path, 'logs')
modules_path = osp.join(testcode_path, 'modules')

sys.path.append(modules_path)
import UTP
import FRU
import CAM

mc_attr = ['ba_sn', 'mc_sn', 'mc_power', 'mc_board_temp', 'chip_temp', 'hbm1_temp', 'hbm2_temp', 'hbm3_temp', 'hbm4_temp']

def get_fru_sn(fru_lookup, fru_location):
    fru_device = fru_lookup.get(fru_location)
    if fru_device == 'EMPTY':
        return 'EMPTY'
    fru_sn_value = fru_device.get('Product Serial')
    return fru_sn_value

def check_temp(inlet_temp, mc_temp, temp_diff):
    return True if mc_temp - inlet_temp > int(temp_diff) else False

def check_mc_temp(log_file_name, temp_diff, fru_lookup):
    # 2021-08-19 16:31:25 Inlet_Temp:23 MC0_CORE_Temp:31 MC1_CORE_Temp:31 MC2_CORE_Temp:30 MC3_CORE_Temp:32 MC0_Power:56 MC1_Power:56 MC2_Power:58 MC3_Power:54
    
    all_passed = True
    mc0_passed = True
    mc1_passed = True
    mc2_passed = True
    mc3_passed = True
    
    expect_mc0_sn = get_fru_sn(fru_lookup, 'MezzCard0')
    expect_mc1_sn = get_fru_sn(fru_lookup, 'MezzCard1')
    expect_mc2_sn = get_fru_sn(fru_lookup, 'MezzCard2')
    expect_mc3_sn = get_fru_sn(fru_lookup, 'MezzCard3')
    
    with open(log_file_name, mode="r", encoding="utf-8") as file:
        for line in file.readlines():
            line = line.strip()
            if line == '':
                continue
            line_list = line.split()
            inlet_temp = int(line_list[2].split(':')[1])
            mc0_temp = int(line_list[3].split(':')[1])
            mc1_temp = int(line_list[4].split(':')[1])
            mc2_temp = int(line_list[5].split(':')[1])
            mc3_temp = int(line_list[6].split(':')[1])
            
            if check_temp(inlet_temp, mc0_temp, temp_diff):
                logging.error('MC0 <{}> Temp {} {} Inlet_Temp:{} MC0_CORE_Temp:{}'.format(expect_mc0_sn, line_list[0], line_list[1], inlet_temp, mc0_temp))
                mc0_passed = False
            
            if check_temp(inlet_temp, mc1_temp, temp_diff):
                logging.error('MC1 <{}> Temp {} {} Inlet_Temp:{} MC1_CORE_Temp:{}'.format(expect_mc1_sn, line_list[0], line_list[1], inlet_temp, mc1_temp))
                mc1_passed = False
            
            if check_temp(inlet_temp, mc2_temp, temp_diff):
                logging.error('MC2 <{}> Temp {} {} Inlet_Temp:{} MC2_CORE_Temp:{}'.format(expect_mc2_sn, line_list[0], line_list[1], inlet_temp, mc2_temp))
                mc2_passed = False
            
            if check_temp(inlet_temp, mc3_temp, temp_diff):
                logging.error('MC3 <{}> Temp {} {} Inlet_Temp:{} MC3_CORE_Temp:{}'.format(expect_mc3_sn, line_list[0], line_list[1], inlet_temp, mc3_temp))
                mc3_passed = False
    
    if not mc0_passed:
        all_passed = False
        logging.error('MC0 Temp Check Failed')
    if not mc1_passed:  
        all_passed = False
        logging.error('MC1 Temp Check Failed')
    if not mc2_passed:
        all_passed = False
        logging.error('MC2 Temp Check Failed')
    if not mc3_passed:
        all_passed = False
        logging.error('MC3 Temp Check Failed')
    return all_passed
    
def main(args):
    case_name = 'mlu370 M8 Temperature Monitor Check'
    logging.info('{}'.format(case_name), section=True)
    
    mcSN = CAM.get_sn('0')
    temp_diff = '37' if mcSN.startswith('58')  else '43'
    logging.info('MC Core Temperature minus Inlet Temperature expect less than {} degrees'.format(temp_diff))
    
    mc_temp_logname = osp.join(logs_path, 'monitor_temp.log')
    if not osp.exists(mc_temp_logname):
        CAM.record_fail_case(case_name)
        logging.error('Please collect core temperature')
        raise Exception('Please collect core temperature')
    
    fru_lookup = FRU.parse_fru_logs(0)
    result = 'PASS' if check_mc_temp(mc_temp_logname, temp_diff, fru_lookup) else 'FAIL'
    
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
    args = parser.parse_args()
    sys.exit(main(args))
    
