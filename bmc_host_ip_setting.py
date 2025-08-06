#!/usr/bin/env python3

import os
import sys
import time
import logging
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
utilities_path = osp.join(testcode_path, 'utilities')
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import CAM

mac_file = osp.join(utilities_path, 'bmc_mac.txt')

def ping_bmc_ip(ip_addr):
    proc = UTP.runproc(['ping', '-c4', ip_addr])
    if proc.returncode is 0:
        logging.info('Host ping BMC IP {} success!'.format(ip_addr))
        return True
    else:
        logging.info('Host ping BMC IP {} failed!'.format(ip_addr))
        return False
    
def check_mac(file_name, find_mac):    
    logging.info('Check if {} exists in {}'.format(find_mac, file_name))
    res = False
    with open(file_name, "r", encoding="utf-8") as f1:
        for line in f1:
            if find_mac in line:
                logging.info('Find MAC {} in file {}'.format(find_mac, file_name))
                res = True
    return res

def main():
    '''
        eth0      Link encap:Ethernet  HWaddr 40:b0:76:60:e8:a3
        eth1      Link encap:Ethernet  HWaddr 00:22:75:d7:1c:f1
    '''
    case_name = 'BMC Host IP Setting'
    logging.info('{}'.format(case_name), section=True)
    
    all_passed = True
    BMC_IP = UTP.get('BMC_IP', ['192.168.100.50', ''])[0]
    if ping_bmc_ip(BMC_IP):
        logging.info('Ping BMC IP {} success'.format(BMC_IP))
        logging.info('Skip Host NIC Port setting')
    else:
        bmc_eth_dict = {}
        context = UTP.run('ifconfig -a | grep "eth[[:digit:]]*.*HWaddr"', shell=True, log_stdout=logging.INFO).strip()
        for line in context.split('\n'):
            eth_name = line.split()[0].strip()
            mac_addr = line.split()[4].strip()
            if check_mac(mac_file, mac_addr):
                bmc_eth_dict[eth_name] = mac_addr
        if len(bmc_eth_dict) == 1:
            bmc_eth_name = list(bmc_eth_dict.keys())[0]
            UTP.run('ifconfig {} 192.168.100.251 netmask 255.255.255.0'.format(bmc_eth_name), shell=True, log_stdout=logging.INFO)
            time.sleep(1)
            if ping_bmc_ip(BMC_IP):
                logging.info('Ping BMC IP {} success'.format(BMC_IP))
            else:
                logging.info('Ping BMC IP {} Failed'.format(BMC_IP))
                all_passed = False
        else:
            logging.error('Detected <{}> USB Dongle MAC Addr. Only request one'.format(len(bmc_eth_dict)))
            all_passed = False
    
    result = 'PASS' if all_passed else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    else:
        CAM.record_fail_case(case_name)
        raise Exception('Some failure detected, please check the log.')
    return
    
if __name__ == '__main__':
    sys.exit(main())
    
