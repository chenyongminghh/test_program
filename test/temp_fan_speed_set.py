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

def temp_fan_set(com, temp_value):
    com_result = False
    com_cmd = 'fan_set {}\n'.format(temp_value)
    com_respone = 'fan:{}'.format(temp_value)
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
            logging.error(line)
        logging.error('{} -- setting failed'.format(com_cmd.strip()))
    return com_result

def temp_fan_get(com):
    com_cmd = 'fan_get\n'
    com_respone = 'fan:'
    
    com_result = ''
    com.write(com_cmd.encode())
    ret = com.read(100).decode().strip()
    for line in ret.strip().split('\n'):
        line = line.strip().strip(';')
        if com_respone in line:
            logging.debug(line)
            logging.debug('{} -- setting success'.format(com_cmd.strip()))
            com_result = line.split(':')[1].strip()
            break
    if not com_result:
        for line in ret.strip().split('\n'):
            logging.error(line)
        logging.error('{} -- setting failed'.format(com_cmd.strip()))
    return com_result

def temp_target_set(com, temp_value):
    com_result = False
    com_cmd = 'temp_set {}\n'.format(temp_value)
    com_respone = 'temp:{}'.format(temp_value)
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
            logging.error(line)
        logging.error('{} -- setting failed'.format(com_cmd.strip()))
    return com_result

def pid_fan_set(com, temp_value=''):
    com_result = False
    
    if temp_value != '':
        com_cmd = 'pid_fan_set {}\n'.format(temp_value)
        com_respone = 'pid_fan_duty:{}'.format(temp_value)
    else:
        com_cmd = 'pid_fan_stop \n'
        com_respone = 'pid_fan enter pid mode'
    
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
            logging.error(line)
        logging.error('{} -- setting failed'.format(com_cmd.strip()))
    return com_result

def main(args):    
    case_name = 'mlu370 Temperature Fan Set'
    logging.info('{}'.format(case_name), section=True)
    
    card_type = CAM.get_mlu370_type('0')
    
    inlet_fan_speed_normal = {'S4':'30', 'S8':'30', 'X4':'60', 'X4K':'60', 'X4L':'60', 'EVBD':'60', 'X8':'70', 'X9':'70', 'X9L':'70', 'D2':'30'}
    inlet_fan_speed_stress = {'S4':'35', 'S8':'35', 'X4':'60', 'X4K':'60', 'X4L':'60', 'EVBD':'60', 'X8':'90', 'X9':'90', 'X9L':'90', 'D2':'35'}
    pid_fan_speed_dict = {'S4':'20', 'S8':'20', 'X4':'30', 'X4K':'30', 'X4L':'30', 'EVBD':'30', 'X8':'40', 'X9':'40', 'X9L':'40', 'D2':'20'}
    
    inlet_fan_speed = inlet_fan_speed_stress.get(card_type) if args.stress else inlet_fan_speed_normal.get(card_type)
    pid_fan_speed = pid_fan_speed_dict.get(card_type) if not args.stress else ''
    
    pid_temp_target = {'S4':'50', 'S8':'50', 'X4':'45', 'X4K':'45', 'X4L':'45', 'EVBD':'45', 'X8':'45', 'X9':'45', 'X9L':'45', 'D2':'50'}
    target_temp = pid_temp_target.get(card_type) if args.stress else '45'
    
    if args.inlet in range(101):
        inlet_fan_speed = args.inlet
    if args.pid in range(101):
        pid_fan_speed = args.pid
    
    logging.info('Card type {}'.format(card_type))
    logging.info('Setting Inlet Fan Speed to {}%'.format(inlet_fan_speed))
    if pid_fan_speed != '':
        logging.info('Setting Outlet Fan Speed to {}%'.format(pid_fan_speed))
    else:
        logging.info('Setting Outlet Fan Speed to Auto, Use PID Mode')
    logging.info('Setting PID Target Temp to {} degree <Only PID Mode Use>'.format(target_temp))
    
    serial_port_list = serial_list()
    if not serial_port_list or len(serial_port_list) != 1:
        logging.error('Detected Serial Port <{}> FAILED'.format(serial_port_list))
        CAM.record_fail_case(case_name)
        raise Exception('Detected Serial Port FAILED')
    
    serial_port = serial_port_list[0]
    logging.info('Detected Serial Port {}'.format(serial_port))
    
    com = serial_open(serial_port)
    result = 'PASS' if temp_fan_set(com, inlet_fan_speed) and pid_fan_set(com, pid_fan_speed) and temp_target_set(com, target_temp) else 'FAIL'
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--stress', action='store_true', help='Stress Function Test')
    parser.add_argument('--inlet', action='store', type=int, help='Set Inlet Fan Speed')
    parser.add_argument('--pid', action='store', type=int, help='Set PID Fan Speed')
    args = parser.parse_args()
    sys.exit(main(args))
    