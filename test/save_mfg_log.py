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
main_path = osp.dirname(osp.dirname(testcode_path))

sys.path.append(modules_path)
import UTP
import CAM
import IMM

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

def collect_logs(sn, seq_name):
    file_list = []
    file_list.append(osp.join(testcode_path, 'error.log'))
    file_list.append(osp.join(testcode_path, 'errors.log'))
    file_list.append(osp.join(testcode_path, 'test.log'))
    file_list.append(osp.join(testcode_path, 'tester.log'))
    file_list.append(osp.join(testcode_path, 'variables'))
    file_list.append(osp.join(testcode_path, 'init.need'))
    file_list.append(osp.join(testcode_path, 'seqname.txt'))
    file_list.append(osp.join(testcode_path, 'version.txt'))
    file_list.append(osp.join(testcode_path, 'hostip.txt'))
    file_list.append(osp.join(testcode_path, 'fru.log'))
    file_list.append(osp.join(sequences_path, '{}.seq'.format(seq_name)))
    for root, dirs, files in os.walk(logs_path):
        break
    for sn_dir in dirs:
        if sn in sn_dir:
            file_list.append(osp.join(logs_path, sn_dir))
    for file in files:
        file_list.append(osp.join(logs_path, file))
    return file_list
    
def create_sn(sn, seq_name, product_sn):
    sn_path = osp.join(testcode_path, sn)
    if osp.exists(sn_path):
        UTP.run(['rm', '-rf', sn_path])
    UTP.run(['mkdir', sn_path], check=False)
    
    file_list = collect_logs(sn, seq_name)
    for file in file_list:
        if osp.exists(file):
            logging.info('SN-{} Copy {}'.format(sn, file))
            UTP.run(['cp', '-rf', file, sn_path], log_stdout=logging.DEBUG)
    if product_sn:
        product_sn_path = osp.join(testcode_path, product_sn)
        if not osp.exists(product_sn_path):
            UTP.run(['mkdir', product_sn_path], check=False)
        logging.info('Copy {} to {}'.format(sn_path, product_sn_path))
        UTP.run(['cp', '-rf', sn_path, product_sn_path], log_stdout=logging.DEBUG)
    
def clean_logs(mcPorts, seq_name):
    logging.info('Cleaning all log files')
    
    clean_list = []
    for mcPort in range(mcPorts):
        board_sn = CAM.get_sn(str(mcPort))
        file_list = collect_logs(board_sn, seq_name)
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
        if 'variables' in file_name:
            continue
        if 'seqname.txt' in file_name:
            continue
        if 'tester.log' in file_name:
            continue
        if osp.exists(file_name):
            UTP.run(['rm', '-rf', file_name], log_stdout=logging.DEBUG)
            logging.info('removed {}'.format(file_name))
    logging.info('All logs have been removed.')

def zipfile(host_ip, sn, seq_name, mcu_version, end_time, result, errorcode):
    sn_path = osp.join(testcode_path, sn)
    if not osp.exists(sn_path):
        logging.info('{} Folder not exists, skip'.format(sn))
        return
    
    if sn.startswith('53'):
        board_type = 'MLU370-S4'
    elif sn.startswith('72'):
        board_type = 'MLU370-S8'
    elif sn.startswith('57'):
        board_type = 'MLU370-X4'
    elif sn.startswith('59'):
        board_type = 'MLU370-X4K'
    elif sn.startswith('52'):
        board_type = 'MLU370-X4L'
    elif sn.startswith('54'):
        board_type = 'MLU370-X8'
    elif sn.startswith('77'):
        board_type = 'MLU370-X9'
    elif sn.startswith('78'):
        board_type = 'MLU370-X9L'
    elif sn.startswith('55') or sn.startswith('58'):
        board_type = 'MLU370-M8'
    elif sn.startswith('56'):
        board_type = 'MLU365-D2'
    elif sn.startswith('47'):
        board_type = 'MLU-X1001'
    else:
        board_type = 'OTHER'
    
    seq_name = seq_name.lower()
    if seq_name in ['s4fct', 's8fct', 'x4fct', 'x4kfct', 'x4lfct', 'x8fct', 'x9fct', 'x9lfct', 'm8fct', 'd2fct']:
        seq_name = 'FCT1'
    elif seq_name in ['s4burnin', 's8burnin', 'x4burnin', 'x4kburnin', 'x4lburnin', 'x8burnin', 'x9burnin', 'x9lburnin', 'm8burnin', 'm8oamburnin', 'd2burnin']:
        seq_name = 'Burn-In'
    else:
        seq_name = seq_name
    
    # IP108_532101300113_FAIL-10_0A92_20210729-212638_MLU370-S4_FCT1.tar.gz
    tar_gz_name = 'IP{}_{}_{}-{}_V{}_{}_{}_{}.tar.gz'.format(host_ip.split('.')[-1], sn, result.upper(), errorcode, mcu_version, end_time, board_type, seq_name)
    tar_gz_path = osp.join(testcode_path, tar_gz_name)
    if make_targz(tar_gz_path, sn_path):
        logging.info('SN-{} tar gzip success'.format(sn))
    else:
        logging.error('SN-{} Tar gzip file failed'.format(sn))
        raise Exception('Tar gzip file failed')
    return tar_gz_path

def copy_to_local(local_file_path, des_path, board_sn, result):
    str_date = datetime.now().strftime('%Y-%m-%d')
    des_date_path = osp.join(des_path, '{}/{}'.format(str_date, result))
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

def record_result(des_path, board_sn, seq_name, mcu_version, result, end_time, host_ip, tar_gz_path):
    # SN**FCT**MCU**PASS**DATETIME**HOST**LOGFILE
    write_line = board_sn + '**'
    write_line = write_line + seq_name + '**'
    write_line = write_line + mcu_version + '**'
    write_line = write_line + result + '**'
    write_line = write_line + end_time + '**'
    write_line = write_line + host_ip + '**'
    write_line = write_line + osp.basename(tar_gz_path) + '\n'
    
    record_path = osp.join(des_path, 'record_result')
    nfs_sn_txt_path = osp.join(record_path, '{}.txt'.format(board_sn))
    
    if not osp.exists(record_path):
        logging.info('Mkdir {}'.format(record_path))
        UTP.run(['mkdir', '-p', record_path], log_stdout=logging.DEBUG)
    
    logging.info('Update NFS {}.txt'.format(board_sn))
    with open(nfs_sn_txt_path, 'a') as wf:
        wf.write(write_line)

def get_errorcode(failure_log_path):
    errorcode_list = []
    if osp.exists(failure_log_path):
        with open(failure_log_path, 'r') as f:
            f.seek(0, 0)
            failure_list = f.readlines()
        for line in failure_list:
            line = line.strip()
            if not line:
                continue
            line_list = line.split()
            if len(line_list) == 4 and line_list[2].strip() not in errorcode_list:
                errorcode_list.append(line_list[2].strip())
    if not errorcode_list:
        errorcode_list = ['E0000']
    return errorcode_list
    
def main():
    logging.info('Saving All Log Files', section=True)
    
    imm = IMM.IMM()
    host_ip = CAM.get_host_ip()
    end_time = CAM.read_datetime()
    save_log_time = datetime.now().strftime("%Y%m%d-%H%M%S")
    nfs_path = osp.join(main_path, "spider_test")
    des_path = osp.join(nfs_path, 'xlogfiles')
    
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
    board_type = CAM.get_mlu370_type('0')
    
    product_sn = ''
    product_error_list = []
    if seq_name not in ['s4fct', 's8fct', 'x4fct', 'x4kfct', 'x4lfct', 'x8fct', 'x9fct', 'x9lfct', 'm8fct', 'd2fct'] and board_type == 'M8':
        product_sn = imm.read_product_sn(0)
    
    result_dict = dict()
    mcPorts = CAM.detected_mlu370()
    port_list = [str(i) for i in range(mcPorts) if i % 2 == 0] if board_type in ['X8', 'X9', 'X9L'] else [str(i) for i in range(mcPorts)]
    for mcPort in port_list:
        board_sn = CAM.get_sn(mcPort)
        logging.info('SN-{} Logs Collect ***'.format(board_sn)) 
        create_sn(board_sn, seq_name, product_sn)
        failure_log_path = osp.join(logs_path, '{}_card{}/failure.log'.format(board_sn, mcPort))
        result = 'fail' if osp.exists(failure_log_path) else 'pass'
        errorcode_list = get_errorcode(failure_log_path)
        if board_type in ['X8', 'X9', 'X9L']:
            second_mcPort = str(int(mcPort)+1)
            second_failure_log_path = osp.join(logs_path, '{}_card{}/failure.log'.format(board_sn, second_mcPort))
            result = 'fail' if osp.exists(second_failure_log_path) or osp.exists(failure_log_path) else 'pass'
            result_dict[second_mcPort] = result
            errorcode_list = errorcode_list + get_errorcode(second_failure_log_path)
        
        if UTP.get('prcstat', 'RUNNING') == 'FAILED':
            result = 'fail'
        if 'FAIL' in UTP.get('exec_mode', 'NORMAL').upper():
            result = 'fail'
        if len(board_sn) < 12:
            result = 'fail'
        
        new_errorcode_list = []
        [new_errorcode_list.append(i) for i in errorcode_list if not i in new_errorcode_list]
        if result == 'fail' and 'E0000' in new_errorcode_list:
            new_errorcode_list.remove('E0000')
            if not new_errorcode_list:
                new_errorcode_list.append('E9999')
        errorcode = '-'.join(new_errorcode_list)
        
        result_dict[mcPort] = result
        mcu_version = CAM.get_mcu_ver(mcPort)
        tar_gz_path = zipfile(host_ip, board_sn, seq_name, mcu_version, save_log_time, result, errorcode)
        copy_to_local(tar_gz_path, des_path, board_sn, result)
        record_result(des_path, board_sn, seq_name, mcu_version, result, end_time, host_ip, tar_gz_path)
        for ec in new_errorcode_list:
            if ec not in product_error_list:
                product_error_list.append(ec)
        
    if product_sn:
        if 'E0000' in product_error_list and len(product_error_list) > 1:
            product_error_list.remove('E0000')
        product_errorcode = '-'.join(product_error_list)
        product_result = 'fail' if 'fail' in result_dict.values() else 'pass'
        bmc_version = '{}'.format(imm.get_bmc_fw_level_image1(0).replace('.', '').strip().rstrip('0'))
        ba_version = 'V{}'.format(imm.get_ba_mcu_version(0).strip())
        product_version = '{}-{}'.format(bmc_version, ba_version)
        tar_gz_path = zipfile(host_ip, product_sn, seq_name, product_version, save_log_time, product_result, product_errorcode)
        copy_to_local(tar_gz_path, des_path, product_sn, product_result)
        record_result(des_path, product_sn, seq_name, product_version, product_result, end_time, host_ip, tar_gz_path)
        
    if not osp.exists(fail_log_path) and 'fail' not in result_dict.values():
        clean_logs(mcPorts, seq_name)
    
    if osp.exists(fail_log_path):
        logging.info('removed {}'.format(fail_log_path))
        UTP.run(['rm', '-rf', fail_log_path], log_stdout=logging.DEBUG)
        
    if not osp.exists(osp.join(testcode_path, 'variables')):
        logging.info('Update variables')
        username = CAM.get_system_username()
        shutil.copy(variables_file, '{}/variables'.format(testcode_path))
        chown_file('{}/variables'.format(testcode_path), username)
    return
    
if __name__ == '__main__':
    sys.exit(main())
