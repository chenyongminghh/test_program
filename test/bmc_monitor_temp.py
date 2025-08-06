#!/usr/bin/env python3

import os
import sys
import time
import logging
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import IMM
import UTP

mc_temp = ['Inlet_Temp', 'MC0_CORE_Temp', 'MC1_CORE_Temp', 'MC2_CORE_Temp', 'MC3_CORE_Temp', 'MC0_Power', 'MC1_Power', 'MC2_Power', 'MC3_Power']

def main():
    logging.info('Start to collect BMC Sensor List')
    imm = IMM.IMM()
    
    mc_temp_logname = osp.join(logs_path, 'monitor_temp.log')
    if osp.exists(mc_temp_logname):
        os.unlink(mc_temp_logname)
    
    while True:
        imm_num = 0
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        sensor_context = imm.get_ipmi_sensors_list(imm_num)
        sensor_logname = osp.join(logs_path, 'sensor{}.log'.format(imm_num))
        logging.debug("sensor list is {}".format(sensor_context))
        with open(sensor_logname, mode='w') as sensor_log:
            sensor_log.write(sensor_context)
            
        sensor_dict = {}
        for line in sensor_context.splitlines():
            sensor_name = line.split("|")[0].strip()
            sensor_value = line.split("|")[1].strip()
            if '.' in sensor_value and '_vdd' not in sensor_name.lower():
                sensor_value = sensor_value.split('.')[0]
            if sensor_value == 'na':
                sensor_value = '0'
            sensor_dict[sensor_name] = sensor_value
            
        w_mc_temp_line = current_time
        for item in mc_temp:
            w_mc_temp_line = w_mc_temp_line + ' {}:{}'.format(item, sensor_dict[item])
        
        with open(mc_temp_logname, mode='a') as w_mc_file:
            w_mc_file.write(w_mc_temp_line + '\n')
        
        time.sleep(1)
    return
    

if __name__ == '__main__':
    sys.exit(main())
