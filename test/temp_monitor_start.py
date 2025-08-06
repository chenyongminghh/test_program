#!/usr/bin/env python3

import sys
import logging
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
sys.path.append(modules_path)
import UTP
import CAM

import serial
import serial.tools.list_ports

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

def main():    
    case_name = 'mlu370 Temperature Monitor Start'
    logging.info('{}'.format(case_name), section=True)
    
    max_temp_diff_dict = {'S4':'47', 'S8':'47', 'X4':'44', 'X4K':'44', 'X4L':'44', 'X8':'32 37', 'X9':'40 45', 'X9L':'40 45', 'D2':'45'}
    card_type = CAM.get_mlu370_type('0')
    if card_type in max_temp_diff_dict.keys():
        max_temp_diff = max_temp_diff_dict.get(card_type)
        logging.info('Card type {} - max temp diff {}'.format(card_type, max_temp_diff))
    else:
        CAM.record_fail_case(case_name)
        raise Exception('Please set Maximum temperature difference')
    
    serial_port_list = serial_list()
    if not serial_port_list or len(serial_port_list) != 1:
        logging.error('Detected Serial Port <{}> FAILED'.format(serial_port_list))
        CAM.record_fail_case(case_name)
        raise Exception('Detected Serial Port FAILED')
    
    serial_port = serial_port_list[0]
    logging.info('Detected Serial Port {}'.format(serial_port))
    
    com = serial_open(serial_port)
    result = 'PASS' if temp_monitor_start(com, max_temp_diff) else 'FAIL'
    serial_close(com)
    
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
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
    
