#!/usr/bin/env python3

import sys
import json
import time
import logging
import collections
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
sys.path.append(modules_path)
import UTP
import CAM

UUTStatus = collections.namedtuple('UUTStatus', ('IP', 'Card', 'Operation', 'Start_time', 'Current_program', 'Test_time', 'Status'))

def get_host_ip():
    host_ip = ''
    ifconfig_cmd = "/sbin/ifconfig -a|grep inet|grep -v 127.0.0.1|grep -v inet6|awk '{print $2}'|tr -d 'addr:'|grep '10.100'|grep -v '10.100.193'"
    host_ip_line = UTP.run(ifconfig_cmd, shell=True, check=False).strip()
    host_ip_list = host_ip_line.split('\n')
    if len(host_ip_list) == 1:
        host_ip = host_ip_list[0]
    else:
        logging.error('Detected host ip more/less than one, please call engineer to check.')
        raise Exception('Detected host ip error.')
    return host_ip

def main():   
    current_op = UTP.get('current_op', '')
    current_op_start = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(UTP.get('.{}_start'.format(current_op), '')))
    
    host_ip = CAM.get_host_ip()
    
    mlu370_qty = UTP.run("lspci -d cabc: | wc -l", shell=True).strip()
    pgmname = UTP.get('pgmname', '')
    pgmoptions = UTP.get('pgmoptions', '')
    current_pgm_start = UTP.get('current_pgm_start', '')
    current_pgm_seconds = int(time.time() - current_pgm_start)
    current_pgm_minutes = '{} min'.format(round(current_pgm_seconds/60)) if current_pgm_seconds > 60 else '{} sec'.format(current_pgm_seconds)
    
    prcstat = UTP.get('prcstat', '')
    status_list = [host_ip, mlu370_qty, current_op, current_op_start, '{} {}'.format(pgmname, pgmoptions), current_pgm_minutes, prcstat.capitalize()]
    
    print('**'.join(status_list))
    return
    
    compares = []
    compares.append(UUTStatus(host_ip, mlu370_qty, current_op, current_op_start, '{} {}'.format(pgmname, pgmoptions), current_pgm_minutes, prcstat.capitalize()))
    
    header = [x.replace('_', ' ').title() for x in UUTStatus._fields]
    logging.info(compares, table={'header': header, 'str_is_str': True, 'max_col_width': 80})
    
    return
    
if __name__ == '__main__':
    sys.exit(main())
    
