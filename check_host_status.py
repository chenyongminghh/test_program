#!/usr/bin/env python3

import os
import sys
import time
import shutil
import tarfile
import logging
import subprocess
import os.path as osp
from datetime import datetime

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
sequences_path = osp.join(testcode_path, 'sequences')
utilities_path = osp.join(testcode_path, 'utilities')
logs_path = osp.join(testcode_path, 'logs')
fail_log_path = osp.join(logs_path, 'mlu370_test_fail.log')
uptime_file = osp.join(logs_path, 'uptime.log')

sys.path.append(modules_path)
import UTP
import CAM

saved_log_flag = osp.join(testcode_path, 'saved.log')
variables_file = osp.join(utilities_path, 'variables')

def make_targz(output_filename, source_dir):
    logging.info('SN-{} tar gzip start'.format(osp.basename(source_dir)))
    try:
        with tarfile.open(output_filename, "w:gz") as tar:
            tar.add(source_dir, arcname=osp.basename(source_dir))
        return True
    except Exception as e:
        logging.error(e)
        return False

def get_all_path(cwd, file_list):   
    get_dir = os.listdir(cwd)
    for i in get_dir:
        sub_dir = osp.join(cwd,i)
        if osp.isdir(sub_dir):
            get_all_path(sub_dir, file_list)
        else:
            file_list.append(sub_dir)
    return file_list

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

def collect_logs(sn, mcPort, seq_name):
    file_list = []
    file_list.append(osp.join(testcode_path, 'error.log'))
    file_list.append(osp.join(testcode_path, 'errors.log'))
    file_list.append(osp.join(testcode_path, 'test.log'))
    file_list.append(osp.join(testcode_path, 'tester.log'))
    file_list.append(osp.join(testcode_path, 'variables'))
    file_list.append(osp.join(sequences_path, '{}.seq'.format(seq_name)))
    file_list.append(osp.join(logs_path, 'mlu370_test.log'))
    file_list.append(osp.join(logs_path, 'mlu370_test_fail.log'))
    file_list.append(osp.join(logs_path, 'monitor_card{}_{}.log'.format(mcPort, sn)))
    for root, dirs, files in os.walk(logs_path):
        break
    for sn_dir in dirs:
        if sn in sn_dir:
            file_list.append(osp.join(logs_path, sn_dir))
    return file_list
    
def create_sn(sn, mcPort, seq_name):
    sn_path = osp.join(testcode_path, sn)
    if osp.exists(sn_path):
        UTP.run(['rm', '-rf', sn_path])
    UTP.run(['mkdir', sn_path], check=False)
    
    file_list = collect_logs(sn, mcPort, seq_name)
    for file in file_list:
        if osp.exists(file):
            logging.info('SN-{} Copy {}'.format(sn, file))
            UTP.run(['cp', '-rf', file, sn_path], log_stdout=logging.DEBUG)

def clean_logs(mcPorts, seq_name):
    logging.info('Cleaning all log files')
    
    clean_list = []
    for mcPort in range(mcPorts):
        board_sn = CAM.get_sn(str(mcPort))
        file_list = collect_logs(board_sn, mcPort, seq_name)
        clean_list = clean_list + file_list
    for log_file in UTP.glob_file('{}/*.json'.format(testcode_path)):
        clean_list.append(log_file)
    for log_file in UTP.glob_file('{}/*.utp'.format(testcode_path)):
        clean_list.append(log_file)
    if osp.exists(osp.join(testcode_path, 'rawtester.log')):
        clean_list.append(osp.join(testcode_path, 'rawtester.log'))
    if osp.exists(osp.join(testcode_path, 'onfail.log')):
        clean_list.append(osp.join(testcode_path, 'onfail.log'))
        
    for file_name in clean_list:
        if file_name.endswith('.seq'):
            continue
        if osp.exists(file_name):
            UTP.run(['rm', '-rf', file_name], log_stdout=logging.DEBUG)
            logging.info('removed {}'.format(file_name))
    logging.info('All logs have been removed.')

def zipfile(host_ip, sn, seq_name, end_time):
    sn_path = osp.join(testcode_path, sn)
    if not osp.exists(sn_path):
        logging.info('{} Folder not exists, skip'.format(sn))
        return
    
    result = 'savelast'
    tar_gz_name = '{}_{}_{}_IP{}_{}.tar.gz'.format(sn, seq_name, end_time, host_ip.split('.')[-1], result)
    tar_gz_path = osp.join(testcode_path, tar_gz_name)
    if make_targz(tar_gz_path, sn_path):
        logging.info('SN-{} tar gzip passed'.format(sn))
    else:
        logging.error('SN-{} Tar gzip file failed'.format(sn))
        raise Exception('Tar gzip file failed')
    return tar_gz_path

def copy_to_local(local_file_path, des_path, board_sn):
    str_date = datetime.now().strftime('%Y-%m-%d')
    des_date_path = osp.join(des_path, str_date)
    if not osp.exists(des_date_path):
        logging.info('Mkdir {}'.format(des_date_path))
        UTP.run(['mkdir', '-p', des_date_path], log_stdout=logging.DEBUG)
    logging.info('Copy {} to {}'.format(osp.basename(local_file_path), des_date_path))
    UTP.run(['cp', '-rf', local_file_path, des_date_path], log_stdout=logging.DEBUG)
    time.sleep(10)
    
    des_file_path = osp.join(des_date_path, osp.basename(local_file_path))
    if osp.exists(des_file_path):
        logging.info('rm -rf {}'.format(local_file_path))
        UTP.run(['rm', '-rf', local_file_path])
    sn_path = osp.join(testcode_path, board_sn)
    if osp.exists(sn_path):
        logging.info('rm -rf {}'.format(sn_path))
        UTP.run(['rm', '-rf', sn_path])

def chown_file(file_path, username):
    UTP.run('sudo chown -R {}:{} {}'.format(username, username, file_path), shell=True)
    UTP.run('sudo chmod -R 755 {}'.format(file_path), shell=True)

def main():
    logging.info('Check Card Qty and Abnormal Reboot', section=True)
    
    mcPorts = CAM.detected_mlu370()
    config_qty = UTP.get('CARD_QTY', 0)
    if config_qty:
        if mcPorts == config_qty:
            logging.info('Detect {} mlu370 cards, correct'.format(config_qty))
        else:
            logging.error('Detect {} <expect {} cards> mlu370 cards, failed'.format(mcPorts, config_qty))
            raise Exception('Detecte mlu370 cards, failed')
    else:
        logging.warning('No expect CARD_QTY setting,skip')
    
    if not osp.exists(uptime_file):
        context = UTP.run(['uptime', '-s'], check=False)
        logging.info('Confirmed normal rebooting <{}>'.format(context.strip()))
        with open(uptime_file, 'w') as f:
            f.write(context)
        return
        
    logging.error('Detect rebooting Abnormal by engineer')
    
    host_ip = get_host_ip()
    seq_name = UTP.get('SEQNAME', 'mlu370mfg.seq').split('.')[0]
    end_time = CAM.read_datetime()
    des_path = "/home/cambricon/test_log/mlu370/"
    
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        board_sn = CAM.get_sn(str(mcPort))
        logging.info('SN-{} Logs Collect ***'.format(board_sn))
        create_sn(board_sn, mcPort, seq_name)
        tar_gz_path = zipfile(host_ip, board_sn, seq_name, end_time)
        copy_to_local(tar_gz_path, des_path, board_sn)
    clean_logs(mcPorts, seq_name)
    
    username = CAM.get_system_username()
    shutil.copy(variables_file, '{}/variables'.format(testcode_path))
    chown_file('{}/variables'.format(testcode_path), username)
    return
    
if __name__ == '__main__':
    sys.exit(main())
