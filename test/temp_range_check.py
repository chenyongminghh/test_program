#!/usr/bin/env python3

import sys
import logging
import argparse
import collections
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

def temp_inlet_get(com):
    com_cmd = 'temp_get\n'
    com_respone = 'max_temp:'
    
    com_result = ''
    com.write(com_cmd.encode())
    ret = com.read(100).decode().strip()
    for line in ret.strip().split('\n'):
        line = line.strip().strip(';')
        if com_respone in line:
            logging.debug(line)
            logging.debug('{} -- setting success'.format(com_cmd.strip()))
            com_result = line.split(':')[1].strip()
            logging.info('Inlet temp:{}'.format(com_result))
            break
    if not com_result:
        for line in ret.strip().split('\n'):
            logging.error(line)
        logging.error('{} -- setting failed'.format(com_cmd.strip()))
    return com_result

def main(args):    
    case_name = 'mlu370 Temperature Inlet Range Check'
    logging.info('{}'.format(case_name), section=True)
    
    serial_port_list = serial_list()
    if not serial_port_list or len(serial_port_list) != 1:
        logging.error('Detected Serial Port <{}> FAILED'.format(serial_port_list))
        CAM.record_fail_case(case_name)
        raise Exception('Detected Serial Port FAILED')
    
    serial_port = serial_port_list[0]
    logging.info('Detected Serial Port {}'.format(serial_port))
    
    com = serial_open(serial_port)
    temp_inlet = temp_inlet_get(com)
    if not temp_inlet:
        logging.info('Retry getting inlet temp one time')
        temp_inlet = temp_inlet_get(com)
    temp_inlet = int(temp_inlet) if temp_inlet else 0
    serial_close(com)
    
    card_type = CAM.get_mlu370_type('0')
    if card_type in ['S4', 'S8', 'D2']:
        low, high = (36, 56)
        logging.info('Borad:{} Range:[{},{}]'.format(card_type, low+1, high-1))
    elif card_type in ['X4', 'X8', 'X4K', 'X4L', 'X9', 'X9L']:
        low, high = (36, 51)
        logging.info('Borad:{} Range:[{},{}]'.format(card_type, low+1, high-1))
    else:
        low, high = (14, 61)
        logging.info('Borad:{} Range:[{},{}]'.format(card_type, low+1, high-1))
    
    result = 'PASS' if temp_inlet in range(low, high) else 'FAIL'
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--stress', action='store_true', help='Stress Function Test')
    args = parser.parse_args()
    sys.exit(main(args))
    