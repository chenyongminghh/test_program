#!/usr/bin/env python3

import sys
import json
import logging
import subprocess
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
sys.path.append(modules_path)
import UTP
import CAM

def main():
    logging.info('Update variables', section=True)
    
    main_path = osp.dirname(osp.dirname(testcode_path))
    nfs_path = osp.join(main_path, 'spider_test')
    lab_cfg_path = osp.join(nfs_path, 'setting/labcfg.json')
    local_cfg_path = osp.join(testcode_path, 'utilities/hostcfg.json')
    if osp.exists(lab_cfg_path):
        proc = UTP.runproc_rt(['cp', '-rf', lab_cfg_path, local_cfg_path], log_stdout=logging.INFO, stderr=subprocess.STDOUT, check=False)
        if proc.returncode:
            logging.info('File <labcfg.json> copy Failed')
            raise Exception('File <labcfg.json> copy Failed')
        else:
            logging.info('File <labcfg.json> copy success')
    
    with open(local_cfg_path, 'r') as load_f:
        var_dict = json.load(load_f)
    
    logging.info('Setting below general variables')
    general_dict = var_dict.get('General')
    for key,value in general_dict.items():
        logging.info('Setting {} as {}'.format(key, value))
        value = False if not value else value
        UTP.set(key, value)
    
    host_ip = CAM.get_host_ip()
    if not host_ip:
        logging.info('Host IP is empty, Please exec <ifconfig> to check')
        logging.info('Skip setting special variables')
        return
    
    if host_ip in var_dict.keys():
        logging.info('Setting below special variables')
        host_dict = var_dict.get(host_ip)
        for key,value in host_dict.items():
            logging.info('Setting {} as {}'.format(key, value))
            value = False if not value else value
            UTP.set(key, value)
    
    # If seqname as m8oamburnin.seq, set NVME_QTY and IB_QTY as 0
    seqname_path = osp.join(testcode_path, 'seqname.txt')
    if osp.exists(seqname_path):
        seq_name = UTP.run('cat {}'.format(seqname_path), shell=True).strip()
    else:
        seq_name = UTP.get('SEQNAME', 'mlu370mfg.seq').split('.')[0]
    if not seq_name:
        logging.error('seq_name is empty')
        raise Exception('seq_name is empty')
    seq_name = seq_name.split('.')[0] if seq_name.endswith('.seq') else seq_name
    seq_name = seq_name.lower()
    if seq_name in ['m8oamburnin', ]:
        logging.info('Setting NVME_QTY as 0')
        logging.info('Setting IB_QTY as 0')
        UTP.set('NVME_QTY', '0')
        UTP.set('IB_QTY', '0')
    return
    
if __name__ == '__main__':
    sys.exit(main())
    
