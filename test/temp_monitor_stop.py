#!/usr/bin/env python3

import sys
import logging
import collections
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
sys.path.append(modules_path)
import UTP
import CAM

import serial
import serial.tools.list_ports

MonitorStatus = collections.namedtuple('TemperatureMonitorResult',
                                      ('slot', 'serial_number', 'total_times', 'fail_times', 'max_diff', 'fan_temp', 'first_times', 'status'))

def serial_list():
    serialPortList = list(serial.tools.list_ports.comports())
    serialCOMList = list()
    if len(serialPortList) == 0:
        print(">>>>[ERROR]: No serial COM")
        return serialCOMList
    
    for i in range(0, len(serialPortList)):
        logging.debug('{} --> {}'.format(serialPortList[i].description, serialPortList[i].device))
        if serialPortList[i].description == "CP2108 Quad USB to UART Bridge Controller - CP2108 Interface 0":
            serialCOMList.append(serialPortList[i].device)
    
    if len(serialCOMList) == 0:
        logging.info(">>>>[ERROR]: No CP2108 Interface 0 Found")
        return False
    return serialCOMList

def serial_open(SerialCOM):
    try:
        bps=115200
        timeout=2
        com=serial.Serial(SerialCOM, bps, timeout=timeout)
    except:
        logging.error("[ERROR]:Failed to open serial {}".format(SerialCOM))
        return False
    return com

def serial_close(com):
    com.close()

def temp_monitor_start(com, max_temp_diff):
    com_cmd = 'temp_monitor_start {} \n'.format(max_temp_diff)
    com_respone = 'temperature_threshold:{}'.format(max_temp_diff)
    
    com_result = False
    com.write(com_cmd.encode())
    ret = com.read(100).decode().strip()
    for line in ret.strip().split('\n'):
        line = line.strip().strip(';')
        if com_respone in line:
            logging.info(line)
            logging.debug('{} -- setting success'.format(com_cmd.strip()))
            com_result = True
            break
    if not com_result:
        for line in ret.strip().split('\n'):
            logging.info(line)
        logging.error('{} -- setting failed'.format(com_cmd.strip()))
    return com_result

def temp_monitor_stop(com):
    com_cmd = 'temp_monitor_stop\n'
    com_respone = 'temp_monitor_stop:success!'
    
    com_result = False
    com.write(com_cmd.encode())
    ret = com.read(100).decode().strip()
    for line in ret.strip().split('\n'):
        line = line.strip().strip(';')
        if com_respone in line:
            logging.info(line)
            logging.debug('{} -- setting success'.format(com_cmd.strip()))
            com_result = True
            break
    if not com_result:
        logging.error('{} -- setting failed'.format(com_cmd.strip()))
    return com_result

def temp_monitor_result(com, board_type):
    '''
        SLOT1:pass;572103300056;4882;0;6;29;1131
        SLOT2:pass;572103300058;4882;0;7;28;2562
        SLOT3:pass;572103300049;4882;0;7;28;2562
        SLOT4:pass;572103300043;4882;0;8;28;2562
        SLOT5:pass;572103300034;4882;0;8;28;2562
    '''
        
    com_cmd = 'temp_monitor_result \n'
    com.write(com_cmd.encode())
    ret = com.read(1000).decode().strip()
    
    compares = []
    for line in ret.strip().split('\n'):
        line = line.strip().strip(';')
        if 'SLOT' not in line:
            continue
        slot_num, slot_result = line.split(':')
        slot_result_list = slot_result.split(';')
        serial_number = slot_result_list[1]
        check_result = slot_result_list[0]
        total_times = slot_result_list[2]
        fail_times = slot_result_list[3]
        max_temp_diff = slot_result_list[4]
        inlet_fan_temp = slot_result_list[5]
        first_failure_times = slot_result_list[6]
        compares.append(MonitorStatus(slot_num, serial_number, total_times, fail_times, max_temp_diff, inlet_fan_temp, first_failure_times, check_result))
    return compares

def main():    
    case_name = 'mlu370 Temperature Monitor Stop'
    logging.info('{}'.format(case_name), section=True)
    
    serial_port_list = serial_list()
    if not serial_port_list or len(serial_port_list) != 1:
        logging.error('Detected Serial Port <{}> FAILED'.format(serial_port_list))
        CAM.record_fail_case(case_name)
        raise Exception('Detected Serial Port FAILED')
    
    serial_port = serial_port_list[0]
    logging.info('Detected Serial Port {}'.format(serial_port))
    
    com = serial_open(serial_port)
    temp_monitor_stop(com)
    card_type = CAM.get_mlu370_type('0')
    compares = temp_monitor_result(com, card_type)
    serial_close(com)
    
    header = [x.replace('_', ' ').title() for x in MonitorStatus._fields]
    logging.info(compares, table={'header': header, 'name': 'mlu370 Temperature Monitor Results', 'str_is_str': True, 'max_col_width': 80})
    
    port_sn_dict = dict()
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = CAM.get_sn(mcPort)
        port_sn_dict[mcPort] = mcSN
    sn_port_dict = {value:key for key,value in port_sn_dict.items()}
    
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
    sys.exit(main())
    