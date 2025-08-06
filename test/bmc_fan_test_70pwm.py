#!/usr/bin/env python3
"""fan_test.py

Check fan presence and insure speed is in range. 
"""
import os
import os.path as osp
import sys
import time
import logging

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')

sys.path.append(modules_path)
import UTP
import IMM
import CAM

def fan_check(imm_num):
    """! Check fan presence and speed

    Insure that all fans required are installed 
    and that they are operating within specified RPM range
    @return booolean test result, True is pass, False is fail
    {
    'hilim': 
        {
            'fan0_inlet': 16800, 
            'fan1_inlet': 16800, 
            'fan2_inlet': 16800, 
            'fan3_inlet': 16800, 
            'fan4_1_inlet': 32620,             
            'fan4_2_inlet': 32620, 
            'fan0_outlet': 16800,
            'fan1_outlet': 16800,
            'fan2_outlet': 16800, 
            'fan3_outlet': 16800, 
            'fan4_1_outlet': 27120, 
            'fan4_2_outlet': 27120, 
        }, 
    'lolim': 
        {
            'fan0_inlet': 1360,
            'fan1_inlet': 1360, 
            'fan2_inlet': 1360, 
            'fan3_inlet': 1360, 
            'fan4_1_inlet': 2660,
            'fan4_2_inlet': 2660, 
            'fan0_outlet': 1200,  
            'fan1_outlet': 1200
            'fan2_outlet': 1200, 
            'fan3_outlet': 1200, 
            'fan4_1_outlet': 2640, 
            'fan4_2_outlet': 2640, 
        }
    }
    """ 
    logging.info('Check fan presence and speed')
    
    amb = {}
    amb['hilim'] = {}
    amb['lolim'] = {}
    
    amb['hilim']['fan0_inlet'] = 11740
    amb['hilim']['fan1_inlet'] = 11740
    amb['hilim']['fan2_inlet'] = 11740
    amb['hilim']['fan3_inlet'] = 11740
    amb['hilim']['fan4_1_inlet'] = 23177
    amb['hilim']['fan4_2_inlet'] = 23177
    
    amb['lolim']['fan0_inlet'] = 9576
    amb['lolim']['fan1_inlet'] = 9576
    amb['lolim']['fan2_inlet'] = 9576
    amb['lolim']['fan3_inlet'] = 9576
    amb['lolim']['fan4_1_inlet'] = 18963
    amb['lolim']['fan4_2_inlet'] = 18963
    
    amb['hilim']['fan0_outlet'] = 11740
    amb['hilim']['fan1_outlet'] = 11740
    amb['hilim']['fan2_outlet'] = 11740
    amb['hilim']['fan3_outlet'] = 11740
    amb['hilim']['fan4_1_outlet'] = 19008
    amb['hilim']['fan4_2_outlet'] = 19008
    
    amb['lolim']['fan0_outlet'] = 9576
    amb['lolim']['fan1_outlet'] = 9576
    amb['lolim']['fan2_outlet'] = 9576
    amb['lolim']['fan3_outlet'] = 9576
    amb['lolim']['fan4_1_outlet'] = 15552
    amb['lolim']['fan4_2_outlet'] = 15552

    fanids = ['fan4_1_inlet', 'fan4_2_inlet', 'fan4_1_outlet', 'fan4_2_outlet']
    fanids += ['fan0_inlet', 'fan1_inlet', 'fan2_inlet', 'fan3_inlet']
    fanids += ['fan0_outlet', 'fan1_outlet', 'fan2_outlet', 'fan3_outlet']
    
    test_fans_result = True
    logging.info('Testing Fan presence')
    fan_sensor_values = {}
    sensors_dict = get_ipmi_sensors_list(imm_num)
    
    for sensor_name in sensors_dict.keys():
        if 'fan' in sensor_name[:3] and 'let' in sensor_name:
            fan_speed_value = sensors_dict.get(sensor_name)
            fan_sensor_values[sensor_name] = fan_speed_value
    
    for fanid in fanids:
        presence = fan_sensor_values.get('%s' % fanid)
        if presence is None or presence == 'na':
            presence = 'Not Installed'
        else:
            presence = 'Installed'
        logging.info("Sensor %s Presence %s = %s" % (fanid, ' '*(13-len(fanid)), presence))
        if presence == 'Installed':
            continue
        else:
            emsg = 'ERROR: %s not present' % (fanid)
            logging.error(emsg)
            test_fans_result = False
            
    if not test_fans_result:
        logging.error('Error: test_fans FAILED for missing sensor data!')
        raise
    else:
        test_fans_result = True
        logging.info('Testing Fan Speeds')
        for fanid in fanids:
            lolim = amb['lolim'][ fanid ]
            hilim = amb['hilim'][ fanid ]
            time.sleep(2)
            speed = fan_sensor_values.get('%s' % fanid)
            
            if speed and speed != 'na':
                speed = float(speed.split('.')[0])
            else:
                speed = 0
            logging.info('Fan Sensor {} = {} RPMs'.format(fanid.ljust(13,' '), speed))
            if lolim <= speed <= hilim:
                pass
            else:
                logging.error('ERROR: {} out of Range({},{}) Actual = {}'.format(fanid,lolim,hilim,speed))
                test_fans_result = False

    return test_fans_result

def get_ipmi_sensors_list(imm_num=0, ipmi_sensors_list={}):
    """! Get sensors output

    @return Dictionary of sensor names and values, all as strings
    """
    
    imm = IMM.IMM()
    logging.info('Force generation of new ipmi sensor files.')
    sensor_log = '/tmp/ipmi_sensors_{}.log'.format(imm_num)
    if osp.exists(sensor_log):
        os.unlink(sensor_log)
    
    logging.info('Get BMC <{}> sensor data.'.format(imm_num))
    sensor_data = imm.get_ipmi_sensors_list(imm_num)
    logging.info('Log BMC <{}> sensor data to {}'.format(imm_num, sensor_log))
    with open(sensor_log, mode='w') as fh:
        fh.write(sensor_data)
    
    with open(sensor_log) as sensor_file:
        for sensor_data_line in sensor_file:
            if '|' not in sensor_data_line:
                continue
            sname, svalue = sensor_data_line.strip().split('|')[:2]
            ipmi_sensors_list[ sname.strip().lower() ] = svalue.strip()
            
    return ipmi_sensors_list

def main():
    case_name = 'BMC Fan Test at 70% PWM'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    all_passed = True
    for imm_num in range(imm_qty):
        imm.set_fan_speed_mfg(imm_num, speed='70')
        time.sleep(10)
        
        fan_result = fan_check(imm_num)
        if not fan_result:
            all_passed = False
            logging.error('Error: BMC <{}> fan check Failed'.format(imm_num))
        else:
            logging.info('BMC <{}> fan check Passed'.format(imm_num))
        imm.set_fan_speed(speed='Auto')
    
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
