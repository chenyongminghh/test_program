#!/usr/bin/env python3

import os
import os.path as osp
import sys
import json
import time
import logging
import subprocess
import multiprocessing as mp
from datetime import datetime

import UTP
import PCITools
import Devices

testcode_path = os.getcwd()
utilities_path = osp.join(testcode_path, 'utilities')
modules_path = osp.join(testcode_path, 'modules')
tests_path = osp.join(testcode_path, 'tests')
logs_path = osp.join(testcode_path, 'logs')
sttools_path = osp.join(testcode_path, 'sttools')
debug_tool_path = osp.join(utilities_path, UTP.get('DEBUG_TOOL'))

# MLU370
dvt_ver_path = osp.join(sttools_path, UTP.get('DVT_VER'))
dvt_test_path = osp.join(dvt_ver_path, 'mlu370_dvt_test')
release_ver_path = osp.join(dvt_ver_path, UTP.get('RELEASE_VER', 'release'))
mlu370_test_log = 'mlu370_test.log'
mlu370_test_log_failed = osp.join(logs_path, 'mlu370_test_fail.log')

cnqual_path = osp.join(testcode_path, 'cnqual')
cnqual_ver_path = osp.join(cnqual_path, UTP.get('CNQUAL_VER'))

def get_dvt_path():
    return dvt_test_path

def format_fname(mcPort, mcSN, dvt_name=''):
    dvt_name = '_{}'.format(dvt_name.lower()) if dvt_name else ''
    fname = '{}_card{}{}_test.log'.format(mcSN, mcPort, dvt_name)
    if UTP.get('MFG_NAME', None) or 'card' in mcSN:
        fname = 'card{}{}_test.log'.format(mcPort, dvt_name)
    return fname

def extract_cnqual_packages(case_name, force_update=False):
    cnqual_package = UTP.get('CNQUAL_PACKAGE', None)
    if not cnqual_package:
        logging.error('Please identify the CNQUAL_PACKAGE in variables')
        return False
    util = osp.join(utilities_path, cnqual_package)
    if not osp.exists(util):
        logging.info('CNQUAL_PACKAGE <{}> not exists, please copy to utilities folder'.format(cnqual_package))
        return False
    extract_res = True if extract_packages(case_name, cnqual_package, cnqual_path, force_update) else False
    return extract_res

def load_cnqual_drivers(case_name):
    if not extract_cnqual_packages(case_name):
        logging.error('Unzip cnqual package failed')
        return False
    setenv_path = osp.join(cnqual_ver_path, 'setenv.sh')
    logging.info('Load cnqual driver --> {}'.format(setenv_path))
    test_cmd = ['./setenv.sh']
    log_fname = os.path.join(logs_path, mlu370_test_log)
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Test Start\n'.format(case_name))
        test_log.write('Start = {}\n'.format(time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, cwd=cnqual_ver_path)
    with open(log_fname, mode='a') as test_log:
        test_log.write('\n')
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('End = {}\n'.format(time.ctime()))
        test_log.write('###{} Test End\n\n'.format(case_name))
    if proc.returncode:
        logging.error('setenv.sh load driver failed with returncode {}'.format(proc.returncode))
        return False
    return_context = proc.stdout.decode('utf-8')
    if "fail" in return_context or "FAIL" in return_context:
        logging.error('Detected FAIL in the output, please check mlu370_test.log')
        return False
    if ">>>DONE" not in return_context:
        logging.error('Not detect >>>DONE in the output, please check mlu370_test.log')
        return False
    logging.info('Load cnqual driver successfully')
    return True

def unload_cnqual_drivers():
    logging.info('Start unloading cambricon_drv driver')
    if not check_cambricon_drv():
        logging.info('Do not exists cambricon_drv driver, skip unload')
        return True
    unload_path = osp.join(cnqual_ver_path, 'driver/cndrv_host_cnqual/unload')
    unload_dir = osp.dirname(unload_path)
    logging.info('{}'.format(unload_path))
    caseName = 'mlu370 Unlod Driver'
    test_cmd = ['./unload']
    log_fname = os.path.join(logs_path, mlu370_test_log)
    with open(log_fname, mode='a') as test_log:
        test_log.write('####################{} Start\n'.format(caseName))
        test_log.write('Start = {}\n'.format(time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, cwd=unload_dir, check=False)
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('End = {}\n'.format(time.ctime()))
        test_log.write('####################{} End\n\n'.format(caseName))
    unload_result = True
    if proc.returncode:
        logging.error('Unload cambricon_drv driver failed with returncode {}'.format(proc.returncode))
        unload_result = False
    time.sleep(1)
    if check_cambricon_drv():
        logging.error('Unload cambricon_drv driver failed, please check mlu370_test.log')
        unload_result = False
    return unload_result

def mt_run_cnqual_test(caseName, cnqual_cmd, cnqual_loops):
    p_lst = []
    q = mp.Queue()
    mcPorts = detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.5)
        p = mp.Process(target=cnqual_one_test, args=(q, mcPort, caseName, cnqual_cmd, cnqual_loops))
        p.start()
        p_lst.append(p)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for mcPort in range(mcPorts):
        res_dvt = q.get()
        if not res_dvt:
            allPassed = False
    return allPassed

def cnqual_one_test(q, mcPort, caseName, cnqual_cmd, cnqual_loops, timeout=7200):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    case_cmd_format = cnqual_cmd.ljust(26)
    logging.info('{} Start  on Card{} <{}>'.format(case_cmd_format, mcPort, mcSN))
    
    cnqual_result = True
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, 'cnqual'), format_fname(mcPort, mcSN, cnqual_cmd)))
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start\n'.format(caseName))
        test_log.write('Start = {}\n'.format(time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    media_to_log = (log_fname, logging.DEBUG)
    test_cmd = ['./cnqual', mcPort, cnqual_cmd, cnqual_loops]
    start_time = datetime.now()
    proc = UTP.runproc_rt(test_cmd, cwd=cnqual_ver_path, log_stdout=media_to_log, stderr=subprocess.STDOUT, check=False)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('\n')
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('End = {}\n'.format(time.ctime()))
        test_log.write('###{} End\n\n'.format(caseName))
    if proc.returncode:
        logging.error('{} Failed on Card{} with returncode {}'.format(case_cmd_format, mcPort, proc.returncode))
        cnqual_result = False
        return q.put(cnqual_result)
    error_code_list = []
    return_context = proc.stdout.decode('utf-8')
    for line in return_context.split('\n'):
        if 'Error code' in line and ':' in line:
            error_code_list.append(line.split(':')[1].strip())
    for errorcode in error_code_list:
        if errorcode != '0':
            logging.error('{} Failed on Card{} with Error Code != 0'.format(case_cmd_format, mcPort))
            cnqual_result = False
            break
    if cnqual_result:
        logging.info('{} Passed on Card{} [{} sec]'.format(case_cmd_format, mcPort, total_seconds))
    return q.put(cnqual_result)

def cnqual_all_test(caseName, cnqual_cmd, cnqual_loops, timeout=7200):
    mcPorts = detected_mlu370()
    case_cmd_format = cnqual_cmd.ljust(26)
    logging.info('{} Start on {} Cards'.format(case_cmd_format, str(mcPorts)))
    
    cnqual_result = True
    log_fname = osp.join(logs_path, mlu370_test_log)
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start\n'.format(caseName))
        test_log.write('Start = {}\n'.format(time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    media_to_log = (log_fname, logging.DEBUG)
    test_cmd = ['./cnqual', 'a', cnqual_cmd, cnqual_loops]
    start_time = datetime.now()
    proc = UTP.runproc_rt(test_cmd, cwd=cnqual_ver_path, log_stdout=media_to_log, stderr=subprocess.STDOUT, check=False)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('\n')
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('End = {}\n'.format(time.ctime()))
        test_log.write('###{} End\n\n'.format(caseName))
    if proc.returncode:
        logging.error('{} Failed with returncode {}'.format(case_cmd_format, proc.returncode))
        cnqual_result = False
        return cnqual_result
    error_code_list = []
    return_context = proc.stdout.decode('utf-8')
    for line in return_context.split('\n'):
        if 'Error code' in line and ':' in line:
            error_code_list.append(line.split(':')[1].strip())
    for errorcode in error_code_list:
        if errorcode != '0':
            logging.error('{} Failed with Error Code != 0'.format(case_cmd_format))
            cnqual_result = False
            break
    if cnqual_result:
        logging.info('{} Passed [{} sec]'.format(case_cmd_format, total_seconds))
    return cnqual_result

def cnqual_temp_test(caseName, cnqual_cmd, cnqual_loops, timeout=7200):
    mcPorts = detected_mlu370()
    case_cmd_format = cnqual_cmd.ljust(26)
    logging.info('{} Start on {} Cards'.format(case_cmd_format, str(mcPorts)))
    
    cnqual_result = True
    log_fname = osp.join(logs_path, mlu370_test_log)
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start\n'.format(caseName))
        test_log.write('Start = {}\n'.format(time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    media_to_log = (log_fname, logging.DEBUG)
    test_cmd = ['./cnqual', '1,2,3', cnqual_cmd, cnqual_loops]
    start_time = datetime.now()
    proc = UTP.runproc_rt(test_cmd, cwd=cnqual_ver_path, log_stdout=media_to_log, stderr=subprocess.STDOUT, check=False)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('\n')
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('End = {}\n'.format(time.ctime()))
        test_log.write('###{} End\n\n'.format(caseName))
    if proc.returncode:
        logging.error('{} Failed with returncode {}'.format(case_cmd_format, proc.returncode))
        cnqual_result = False
        return cnqual_result
    error_code_list = []
    return_context = proc.stdout.decode('utf-8')
    for line in return_context.split('\n'):
        if 'Error code' in line and ':' in line:
            error_code_list.append(line.split(':')[1].strip())
    for errorcode in error_code_list:
        if errorcode != '0':
            logging.error('{} Failed with Error Code != 0'.format(case_cmd_format))
            cnqual_result = False
            break
    if cnqual_result:
        logging.info('{} Passed [{} sec]'.format(case_cmd_format, total_seconds))
    return cnqual_result

def cnqual_config(case_name, minutes):
    config_ini_path = osp.join(cnqual_ver_path, 'config/config.ini')
    if 'Power' in case_name:
        key_string = 'Power Test RunTime :'
    elif 'Stress' in case_name:
        key_string = 'Stress Test RunTime :'
    elif 'Thermal' in case_name:
        key_string = 'Thermal Test RunTime :'
    else:
        logging.error('Maybe {} format issue, please call engineer!'.format(config_ini_path))
        raise Exception('File Format Issue')
    new_str = key_string + ' {}mins\n'.format(minutes)
    new_file = []
    with open(config_ini_path, "r", encoding="utf-8") as f:
        content = f.readlines()
        for line in content:
            if key_string in line:
                line = new_str
            new_file.append(line)
    with open(config_ini_path,"w",encoding="utf-8") as f:
        f.writelines(new_file)

def extract_serdes_packages(case_name, force_update=True):
    serdes_path = osp.join(testcode_path, 'serdes')
    serdes_package = UTP.get('SERDES_PACKAGE', None)
    if not serdes_package:
        logging.error('Please identify the SERDES_PACKAGE in variables')
        return False
    util = osp.join(utilities_path, serdes_package)
    if not osp.exists(util):
        logging.error('SERDES_PACKAGE <{}> not exists, please copy to utilities folder'.format(serdes_package))
        return False
    extract_res = True if extract_packages(case_name, serdes_package, serdes_path, force_update) else False
    return extract_res

def extract_packages(caseName, package, local_folder, force_update):
    logging.info(caseName)
    util = osp.join(utilities_path, package)
    if not osp.exists(util):
        logging.error('Packages <{}> not exists'.format(package))
        logging.error('Please make sure packages exists'.format(package))
        return False
    if osp.exists(local_folder) and force_update:
        logging.info('Force remove {}'.format(local_folder))
        UTP.run(['rm', '-rf', local_folder], log_stdout=logging.DEBUG)
    elif osp.exists(local_folder):
        logging.info('Exist {}'.format(local_folder))
        logging.info('Skip extract {}'.format(package))
        return True
    if not osp.exists(local_folder):
        logging.info('Mkdir {}'.format(local_folder))
        UTP.run(['mkdir', '-p', local_folder], log_stdout=logging.DEBUG)
    logging.info('Extract <{}> to <{}>'.format(package, local_folder))
    test_cmd = ['tar', '-xzvf', util, '-C', local_folder]
    log_fname = osp.join(logs_path, 'mlu370_test.log')
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start\n'.format(caseName))
        test_log.write('Start = {}\n'.format(time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    media_to_log = (log_fname, logging.DEBUG)
    proc = UTP.runproc_rt(test_cmd, log_stdout=media_to_log, stderr=subprocess.STDOUT, check=False)
    with open(log_fname, mode='a') as test_log:
        test_log.write('\n')
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('End = {}\n'.format(time.ctime()))
        test_log.write('###{} End\n\n'.format(caseName))
    if proc.returncode:
        logging.error('{} failed with returncode {}'.format(caseName, proc.returncode))
        return False
    username = get_system_username()
    UTP.run(['chmod', '777', '-R', local_folder])
    UTP.run(['chown', '{}:{}'.format(username, username), '-R', local_folder])
    return True

def build_packages():
    logging.info('Starting build.sh')
    BUILD_SH = "build_all_mfg.sh"
    build_sh_path = UTP.run(['find', sttools_path, '-name', BUILD_SH]).strip()
    build_sh_dir = osp.dirname(build_sh_path)
    
    caseName = 'DVT Package Build'
    log_fname = os.path.join(logs_path, 'ba_test.log')
    test_cmd = ['/bin/bash', 'build_all_mfg.sh', 'all']
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Test Start on {}\n'.format(caseName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, cwd=build_sh_dir)
    with open(log_fname, mode='a') as test_log:
        test_log.write('\n')
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('###{} Test End  on {}\n\n'.format(caseName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
    
    if proc.returncode:
        logging.error('build_all_mfg.sh failed with returncode {}'.format(proc.returncode))
        return False
    return_context = proc.stdout.decode('utf-8')
    if "fail" in return_context or "FAIL" in return_context:
        logging.error('build_all_mfg.sh failed')
        return False
    UTP.run(['chmod', '777', '-R', sttools_path])
    logging.info('build_all_mfg.sh run successfully')
    return True
    
def get_host_ip():
    host_ip = ''
    host_ip_path = osp.join(testcode_path, 'hostip.txt')
    ifconfig_cmd = "/sbin/ifconfig -a|grep inet|grep -v 127.0.0.1|grep -v inet6|awk '{print $2}'|tr -d 'addr:'|grep '10.100'|grep -v '10.100.193'"
    host_ip_line = UTP.run(ifconfig_cmd, shell=True, check=False).strip()
    host_ip_list = host_ip_line.split('\n')
    if len(host_ip_list) == 1:
        host_ip = host_ip_list[0]
    if not host_ip and osp.exists(host_ip_path):
        logging.debug('host_ip_path:{}'.format(host_ip_path))
        with open(host_ip_path, mode="r", encoding="utf-8") as f:
            lines = f.readlines()
            host_ip = lines[0].strip()
    if not host_ip:
        logging.error('Detected host ip more/less than one, please call engineer to check.')
    return host_ip

def read_datetime():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def read_first_line(file_path):
    first_line = ''
    with open(file_path, 'rb') as f:
        f.seek(0, 0)
        first_line = f.readline().strip()
    return first_line.decode()

def read_last_line(file_path):
    last_line = ''
    with open(file_path, 'rb') as f:
        f.seek(0, 2)
        max_offset = f.tell()
        if max_offset < 50:
            offset = -max_offset
        else:
            offset = -50    # Set Offset
        while True:
            f.seek(offset, 2)                   # seek(offset, 2)表示文件指针：从文件末尾(2)开始向前50个字符(-50)
            lines = f.readlines()               # 读取文件指针范围内所有行
            if len(lines) >= 2:                 # 判断是否最后至少有两行，这样保证了最后一行是完整的
                last_line = lines[-1].strip()   # 取最后一行
                break
            offset *= 2
    return last_line.decode()

def add_befor_last_line(file_path, last_line):
    last_line = last_line + '\n'
    with open(file_path, 'r') as f:
        content = f.readlines()
    lines_no = len(content)
    content.insert(lines_no-1, last_line)
    with open(file_path, 'w') as f:
        f.writelines(content)
        f.flush()

def add_last_line(file_path, last_line):
    with open(file_path, 'a+') as f:
        f.seek(0, 2)
        f.write(last_line)
        f.write(os.linesep)
        f.flush()
    
def add_case_start_time(file_path, case_name, start_time):
    if not osp.exists(file_path):
        return
    new_line = case_name + '=' + start_time + ','
    add_last_line(file_path, new_line)

def update_last_line(file_path, end_string):
    with open(file_path, 'ab+') as f:
        f.seek(-len(os.linesep), 2)
        f.truncate()
        f.write(end_string)
        f.flush()

def update_case_end_time(file_path, case_name, start_time, end_time, result):
    if not osp.exists(file_path):
        return
    file_last_line = read_last_line(file_path)
    original_line = case_name + '=' + start_time + ','
    end_string = end_time + ',' + result + os.linesep
    if file_last_line == original_line:
        update_last_line(file_path, end_string.encode())

def check_uut_log(file_path):
    all_case_result = 'PASS'
    first_line = read_first_line(file_path)
    last_line = read_last_line(file_path)
    if not first_line == '***START***':
        logging.error('First Line --> {}'.format(first_line))
        logging.error('File <{}> Format error, please call engineer.'.format(uut_sn_log_name))
        raise Exception('File <{}> Format error, please call engineer.'.format(uut_sn_log_name))
    if last_line == '***END***':
        with open(file_path, 'r') as f:
            f.seek(0, 0)
            for line in f.readlines():
                line = line.strip()
                if line.startswith('CASE-') and line.split(',')[-1].strip() != 'PASS':
                    all_case_result = 'FAIL'
                    break
    elif last_line.endswith('FAIL'):
        all_case_result = 'FAIL'
    elif last_line.endswith(','):
        all_case_result = 'HANG'
    else:
        all_case_result = 'OTHER'
    return all_case_result

def read_seq_end_time(file_path):
    seq_end_time = ''
    with open(file_path, 'r') as f:
        f.seek(0, 0)
        for line in f.readlines():
            line = line.strip()
            if line.startswith('UUT_SEQ_END_TIME='):
                seq_end_time = line.split('=')[1].strip()
    return seq_end_time

def read_seq_name(file_path):
    seq_name = ''
    with open(file_path, 'r') as f:
        f.seek(0, 0)
        for line in f.readlines():
            line = line.strip()
            if line.startswith('UUT_SEQ_NAME='):
                seq_name = line.split('=')[1].strip()
    if not seq_name:
        logging.error('UUT_SEQ_NAME is empty, please call engineer to check.')
        raise Exception('UUT_SEQ_NAME is empty, please call engineer to check.')
    return seq_name

def read_host_ip(file_path):
    host_ip = ''
    with open(file_path, 'r') as f:
        f.seek(0, 0)
        for line in f.readlines():
            line = line.strip()
            if line.startswith('HOST_IP='):
                host_ip = line.split('=')[1].strip()
    if not host_ip:
        logging.error('Host_IP is empty, please call engineer to check.')
        #raise Exception('Host_IP is empty, please call engineer to check.')
    return host_ip

def backup_tar_gz(file_path):
    str_date = osp.basename(file_path).split('_')[2]
    stamp = datetime.strptime(str_date, '%Y%m%d')
    log_date = stamp.strftime('%Y-%m-%d')
    
    tar_gz_log_path = osp.join(testcode_path, 'status')
    if osp.exists('/spider_test/config/autotest.site') and UTP.get('AUTOTEST', False):
        tar_gz_log_path = osp.join(osp.dirname(testcode_path), 'Logs/{}'.format(log_date))
    if not osp.isdir(tar_gz_log_path):
        logging.info('Mkdir folder {}'.format(tar_gz_log_path))
        UTP.run(['mkdir', '-p', tar_gz_log_path])
    
    des_path = osp.join(tar_gz_log_path, osp.basename(file_path))
    logging.info('cp -rf {} {}'.format(file_path, des_path))
    UTP.run(['cp', '-rf', file_path, des_path])
    if not osp.exists(des_path):
        logging.error('{} not exists, please check the tar gz file backup'.format(des_path))
        raise Exception('{} not exists, please check the tar gz file backup'.format(des_path))

def backup_uut_log(file_path, des_name):
    uut_sn = osp.basename(des_name).split('_')[1]
    
    uut_sn_log_path = osp.join(testcode_path, 'status')
    if osp.exists('/spider_test/config/autotest.site') and UTP.get('AUTOTEST', False):
        uut_sn_log_path = osp.join('/spider_test/logfile', 'mlu290/{}'.format(uut_sn))
    
    if not osp.isdir(uut_sn_log_path):
        logging.info('Mkdir folder {}'.format(uut_sn_log_path))
        UTP.run(['mkdir', '-p', uut_sn_log_path])
    
    des_path = osp.join(uut_sn_log_path, des_name)
    logging.info('cp -rf {} {}'.format(file_path, des_path))
    UTP.run(['cp', '-rf', file_path, des_path])
    if not osp.exists(des_path):
        logging.error('{} not exists, please check file backup'.format(des_path))
        raise Exception('{} not exists, please check file backup'.format(des_path))
    os.unlink(file_path)

def scp_logs_new(user, ip, password, local_source, remote_dest):
    SCP_CMD_BASE = r"""
        expect -c "
        set timeout 60 ;
        spawn scp -o StrictHostKeyChecking=no -r {localsource} {username}@{host}:{remotedest} ;
        expect *assword* {{{{ send {password}\r }}}} ;
        expect *\r ;
        expect \r ;
        expect eof
        "
    """.format(username=user, password=password, host=ip, localsource=local_source, remotedest=remote_dest)
    SCP_CMD = SCP_CMD_BASE.format(localsource = local_source)
    UTP.runproc_rt(SCP_CMD, shell=True, log_stdout=logging.INFO)

def backup_to_server(tar_gz_path):
    if UTP.get('SITE', '') == 'Beijing':
        logging.info('Beijing Lab need scp to server.')
        host_ip = get_host_ip()
        if not host_ip:
            logging.error('Host IP did not detected')
            raise Exception('Host IP did not detected')
        ip_folder = host_ip.split('.', 2)[2]
        destination_path = "/home/cambricon/test_log/MLU290_log/{}/".format(ip_folder)
        scp_logs_new("cambricon", "10.100.192.9", "hello123", tar_gz_path, destination_path)
        time.sleep(10)        
    else:
        logging.info('Only Beijing Site need scp to server.')

def init_file(file_path, myhost):
    uut_seq_name = UTP.get('SEQUENCE_NAME', '')
    uut_seq_start_time = read_datetime()
    logging.info('UUT SN         : {}'.format(myhost.uut_sn))
    logging.info('UUT SEQ NAME   : {}'.format(uut_seq_name))
    logging.info('UUT START TIME : {}'.format(uut_seq_start_time))
    logging.info('Host IP        : {}'.format(myhost.host_ip))
    logging.info('Host OS        : {}'.format(myhost.host_os))
    logging.info('Host Name      : {}'.format(myhost.host_name))
    with open(file_path, 'w') as f:
        f.seek(0,0)
        f.write('***START***\n')
        f.write('UUT_SN={}\n'.format(myhost.uut_sn))
        f.write('UUT_SEQ_NAME={}\n'.format(uut_seq_name))
        f.write('UUT_SEQ_START_TIME={}\n'.format(uut_seq_start_time))
        f.write('HOST_IP={}\n'.format(myhost.host_ip))
        f.write('HOST_OS={}\n'.format(myhost.host_os))
        f.write('HOST_NAME={}\n'.format(myhost.host_name))
        f.flush()

def get_failure_case(file_path):
    failure_case = ''
    with open(file_path, 'r') as f:
        f.seek(0, 0)
        for line in f.readlines():
            line = line.strip()
            if line.startswith('CASE-') and line.split(',')[-1].strip() != 'PASS':
                failure_case = failure_case + line.split('=')[0].lstrip('CASE-')
                failure_case = failure_case + ','
    if failure_case and failure_case.endswith(','):
        failure_case = failure_case.rstrip(',')
    return failure_case
    
def detected_mlu370():
    device_list = UTP.run(['lspci', '-d', 'cabc:0370'], check = False).strip()
    detect_qty = len(device_list.split('\n')) if device_list else 0
    if detect_qty > 0:
        logging.info('Using <lspci -d cabc:0370> Detected MLU370 Qty <{}>'.format(detect_qty))
        return detect_qty
    else:
        device_list = UTP.run(['lspci', '-d', 'cabc:0365'], check = False).strip()
        detect_qty_d2 = len(device_list.split('\n')) if device_list else 0
        if detect_qty_d2 > 0:
            logging.info('Using <lspci -d cabc:0365> Detected MLU370-D2 Qty <{}>'.format(detect_qty_d2))
            return detect_qty_d2
        else:
            #return 0
            raise Exception('Detected MLU370 Qty FAILED')

def get_sn(slot_port):
    if slot_port not in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15']:
        logging.error('Slot port <{}> not in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]'.format(slot_port))
        raise Exception('Read serial number on Card{} FAILED'.format(slot_port))
    serial_number = ''
    content = UTP.run([debug_tool_path, '-i', slot_port, '-p', '3'], check = False)
    for line in content.split('\n'):
        if 'sn_code:' in line:
            serial_number = line.split(':')[1].strip()
    if serial_number and serial_number.lower() != 'ffffffffffff':
        return serial_number
    else:
        logging.error('Read serial number on Card{} FAILED'.format(slot_port))
        serial_number = 'card' + slot_port.strip()
        return serial_number

def get_bdf(slot_port):
    bdf_string = ''
    content = UTP.run([debug_tool_path, '-i', slot_port, '-p', '2'], check = False)
    for line in content.split('\n'):
        if 'bdf_number:' in line:
            bdf_string = line.split(':', 2)[2].strip()
            break
    return bdf_string

def get_chip_id(slot_port):
    chip_id_string = ''
    content = UTP.run([debug_tool_path, '-i', slot_port, '-p', '22'], check = False)
    for line in content.split('\n'):
        if 'chip_id:' in line:
            chip_id_string = line.split(':')[1].strip()
            break
    return chip_id_string

def get_cpm_count(slot_port):
    cpm_count = ''
    content = UTP.run([debug_tool_path, '-i', slot_port, '-f', '15'], check = False)
    for line in content.split('\n'):
        if 'cpm_cnt=' in line:
            cpm_count = line.split('=')[1].strip()
            break
    return cpm_count

def get_mlu370_type(slot_port):
    slot_port = str(slot_port)
    card_sn = get_sn(slot_port)
    if card_sn.startswith('53'):
        card_type = 'S4'
    elif card_sn.startswith('72'):
        card_type = 'S8'
    elif card_sn.startswith('50'):
        card_type = 'EVBD'
    elif card_sn.startswith('57'):
        card_type = 'X4'
    elif card_sn.startswith('54'):
        card_type = 'X8'
    elif card_sn.startswith('77'):
        card_type = 'X9'
    elif card_sn.startswith('78'):
        card_type = 'X9L'
    elif card_sn.startswith('55'):
        card_type = 'M8'
    elif card_sn.startswith('56'):
        card_type = 'D2'
    elif card_sn.startswith('59'):
        card_type = 'X4K'
    elif card_sn.startswith('52'):
        card_type = 'X4L'
    elif card_sn.startswith('58'):
        card_type = 'M8'
    else:
        card_type = 'OTHER'
    return card_type
    
def get_mlu370_dvt_type(slot_port):
    if slot_port not in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15']:
        logging.error('Slot port not in support list')
        raise Exception('Get card type on Card{} FAILED'.format(slot_port))
    card_type = ''
    content = UTP.run([debug_tool_path, '-i', slot_port, '-r', '-a', 'a0'], check = False)
    for line in content.split('\n'):
        if 'value of addr' in line:
            card_type = line.split()[-1].strip()
    if not card_type:
        logging.error('Get card type on Card{} FAILED'.format(slot_port))
        return card_type
    if card_type == '0x0053cabc':
        card_type = 'S4'
    elif card_type == '0x0072cabc':
        card_type = 'S8'
    elif card_type == '0x0050cabc':
        card_type = 'EVBD'
    elif card_type == '0x0057cabc':
        card_type = 'X4'
    elif card_type == '0x0054cabc':
        card_type = 'X8'
    elif card_type == '0x0077cabc':
        card_type = 'X9'
    elif card_type == '0x0078cabc':
        card_type = 'X9L'
    elif card_type == '0x0055cabc':
        card_type = 'M8'
    elif card_type == '0x0056cabc':
        card_type = 'D2'
    elif card_type == '0x0059cabc':
        card_type = 'X4K'
    elif card_type == '0x0052cabc':
        card_type = 'X4L'
    elif card_type == '0x0058cabc':
        card_type = 'M8'
    else:
        card_type = 'OTHER'
    return card_type

def check_cambricon_drv():
    output=UTP.run("lsmod | grep 'cambricon_drv'", shell=True, check=False).strip()
    if output:
        logging.info(output)
    return True if len(output) else False

def unload_mlu370_drivers():
    logging.info('Start unloading cambricon_drv driver')
    if not check_cambricon_drv():
        logging.info('Do not exists cambricon_drv driver, skip unload')
        return True
    unload_path = osp.join(release_ver_path, 'neuware/src/driver/cndrv_host/unload')
    unload_dir = osp.dirname(unload_path)
    logging.info('{}'.format(unload_path))
    caseName = 'mlu370 Unlod Driver'
    test_cmd = ['./unload']
    log_fname = os.path.join(logs_path, mlu370_test_log)
    with open(log_fname, mode='a') as test_log:
        test_log.write('####################{} Start\n'.format(caseName))
        test_log.write('Start = {}\n'.format(time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, cwd=unload_dir, check=False)
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('End = {}\n'.format(time.ctime()))
        test_log.write('####################{} End\n\n'.format(caseName))
    unload_result = True
    if proc.returncode:
        logging.error('Unload cambricon_drv driver failed with returncode {}'.format(proc.returncode))
        unload_result = False
    time.sleep(1)
    if check_cambricon_drv():
        logging.error('Unload cambricon_drv driver failed, please check mlu370_test.log')
        unload_result = False
    return unload_result
    
def extract_dvt_packages(case_name, force_update=False):
    dvt_package = UTP.get('DVT_PACKAGE', None)
    if not dvt_package:
        logging.error('Please identify the DVT_PACKAGE in variables')
        return False
    util = osp.join(utilities_path, dvt_package)
    if not osp.exists(util):
        logging.info('DVT_PACKAGE <{}> not exists, please copy to utilities folder'.format(dvt_package))
        return False
    extract_res = True if extract_packages(case_name, dvt_package, sttools_path, force_update) else False
    logging.info('Update driver_path_cfg file')
    driver_path_cfg = osp.join(release_ver_path, 'neuware/src/driver/cndrv_host')
    driver_path_file = osp.join(dvt_ver_path, 'driver_path_cfg')
    with UTP.open_file(driver_path_file, mode='w') as wf:
        wf.write('{}\n'.format(driver_path_cfg))
    username = get_system_username()
    UTP.run(['chown', '{}:{}'.format(username, username), '-R', driver_path_file])
    return extract_res
    
def build_dvt_packages(case_name, force_update=False):
    if not extract_dvt_packages(case_name, force_update):
        logging.error('Unzip dvt package failed')
        return False
    logging.info('Starting build.sh')
    caseName = 'DVT Package Build'
    log_fname = os.path.join(logs_path, mlu370_test_log)
    test_cmd = ['/bin/bash', 'build_all_mfg.sh', 'all']
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start\n'.format(caseName))
        test_log.write('Start = {}\n'.format(time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, cwd=dvt_test_path)
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('End = {}\n'.format(time.ctime()))
        test_log.write('###{} End\n\n'.format(caseName))
    if proc.returncode:
        logging.error('build_all_mfg.sh failed with returncode {}'.format(proc.returncode))
        return False
    return_context = proc.stdout.decode('utf-8')
    if "fail" in return_context or "FAIL" in return_context:
        logging.error('build_all_mfg.sh failed')
        return False
    UTP.run(['chmod', '777', '-R', sttools_path])
    logging.info('build_all_mfg.sh run successfully')
    return True

def get_system_username():
    system_username = 'cambricon'
    pwd_list = testcode_path.split('/')
    if pwd_list[2] == 'cambricon':
        system_username = 'cambricon'
    elif pwd_list[2] == 'cambricon_test':
        system_username = 'cambricon_test'
    return system_username

def get_all_path(cwd, file_list):   
    get_dir = os.listdir(cwd)
    for i in get_dir:
        sub_dir = osp.join(cwd,i)
        if osp.isdir(sub_dir):
            get_all_path(sub_dir, file_list)
        else:
            file_list.append(sub_dir)
    return file_list

def del_dvt_package():
    package_list = []
    package_list.append(sttools_path)
    for package in package_list:
        if osp.exists(package):
            UTP.run(['rm', '-rf', package], log_stdout=logging.DEBUG)
            logging.info('removed {}'.format(package))

def get_dvt_list(case_type):
    dvt_list = []
    for dvt_file in UTP.glob_file(osp.join(dvt_test_path, '{}/build/bin/mlu370/*'.format(case_type))):
        dvt_file_name = osp.basename(dvt_file)
        if dvt_file_name.startswith('mlu370'):
            dvt_list.append(dvt_file_name)
    return dvt_list
    
def mt_run_power_Test_only_x8_filter(caseName, ipu_cmd, high_loops, low_loops, internal_loops, overall, dvt_name, mlu_id):
    p_lst = []
    q = mp.Queue()
    mcPorts = detected_mlu370()
    
    port_list = []
    port_list_mlu0 = [str(i) for i in range(mcPorts) if i % 2 == 0]
    port_list_mlu1 = [str(i) for i in range(mcPorts) if i % 2 == 1]
    port_list = port_list_mlu0 if mlu_id == '0' else port_list_mlu1
    
    for mcPort in port_list:
        time.sleep(0.1)
        p = mp.Process(target=mlu370_new_power_one_card, args=(q, mcPort, caseName, ipu_cmd, high_loops, low_loops, internal_loops, overall, dvt_name))
        p.start()
        p_lst.append(p)
    time.sleep(0.5)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for mcPort in port_list:
        res_power = q.get()
        logging.debug("res_power --> {}".format(res_power))
        if not res_power:
            allPassed = False
    return allPassed
    
def mt_run_power_Test(caseName, ipu_cmd, high_loops, low_loops, internal_loops, overall, dvt_name):
    p_lst = []
    q = mp.Queue()
    mcPorts = detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.1)
        p = mp.Process(target=mlu370_new_power_one_card, args=(q, mcPort, caseName, ipu_cmd, high_loops, low_loops, internal_loops, overall, dvt_name))
        p.start()
        p_lst.append(p)
    time.sleep(0.5)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for mcPort in range(mcPorts):
        res_power = q.get()
        logging.debug("res_power --> {}".format(res_power))
        if not res_power:
            allPassed = False
    return allPassed

def mlu370_new_power_one_card(q, mcPort, caseName, ipu_cmd, high_loops, low_loops, internal_loops, overall, dvt_name, length=None, timeout=7200):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    
    test_cmd = './{} {} {} {}'.format(ipu_cmd, high_loops, low_loops, internal_loops)
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, overall), format_fname(mcPort, mcSN, dvt_name)))
    
    if check_card_fail(mcPort, mcSN):
        logging.info('{} Skiped on Card{}'.format(test_cmd, mcPort))
        return q.put(True)
    
    length = len(caseName) if not length else length
    case_name_format = caseName.ljust(length)
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    env_ipu = dict(os.environ)
    env_ipu.setdefault('MLU_VISIBLE_DEVICES', mcPort)
    dvt_path = osp.join(dvt_test_path, 'ipu/build/bin/mlu370')
    
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
        test_log.write('TEST_CMD={}\n'.format(test_cmd))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, cwd=dvt_path, shell=True, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False, env=env_ipu)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('###{} End  on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    if proc.returncode:
        failure_message = '{} Failed on Card{} with returncode {}'.format(caseName, mcPort, proc.returncode)
        logging.error('{}'.format(failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return q.put(False)
    return_context = proc.stdout.decode('utf-8')
    if "FAILED" in return_context:
        failure_message = '{} Failed on Card{} with detect FAILED'.format(caseName, mcPort)
        logging.error('{}'.format(failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return q.put(False)
    if "PASSED" not in return_context:
        failure_message = '{} Failed on Card{} with not detect PASSED'.format(caseName, mcPort)
        logging.error('{}'.format(failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return q.put(False)
    logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    return q.put(True)

def mlu370_dimz(type_name, case_name, dimz):
    testcfg_path = osp.join(dvt_test_path, 'ipu/{}/{}/test.conf'.format(type_name, case_name))
    new_str = 'dim_quadrant_z = {}\n'.format(dimz)
    new_file = []
    with open(testcfg_path, "r", encoding="utf-8") as f:
        content = f.readlines()
        for line in content:
            if 'dim_quadrant_z' in line:
                line = new_str
            new_file.append(line)
    with open(testcfg_path,"w",encoding="utf-8") as f:
        f.writelines(new_file)

def format_dirname(mcPort, mcSN, overall=''):
    dirname = '{}_card{}'.format(mcSN, mcPort)
    if UTP.get('MFG_NAME', None) or 'card' in mcSN:
        dirname = 'card{}_dvt'.format(mcPort)
    if overall:
        dirname = dirname + '/{}'.format(overall)
    card_dvt_path = osp.join(logs_path, dirname)    
    if not osp.exists(card_dvt_path):
        UTP.run(['mkdir', '-p', card_dvt_path])
    UTP.run(['chmod', '777', '-R', card_dvt_path])
    username = get_system_username()
    UTP.run(['chown', '{}:{}'.format(username, username), '-R', card_dvt_path])
    return dirname

def get_errorcode(key):
    errorcode_json = osp.join(utilities_path, 'errorcode.json')
    if not osp.exists(errorcode_json):
        error_code = 'E9999'
        return error_code
    with open(errorcode_json, 'r') as load_f:
        error_code_dict = json.load(load_f)
    error_code = error_code_dict.get(key)
    error_code = error_code if error_code else 'E9999'
    return error_code

def get_keys(value):
    description_json = osp.join(utilities_path, 'description.json')
    if not osp.exists(description_json):
        return value.replace(' ', '_')
    with open(description_json, 'r') as load_f:
        case_dict = json.load(load_f)
    py_caseList = [k for k,v in case_dict.items() if value in v]
    logging.debug('py_caseList:{}'.format(py_caseList))
    py_caseName = py_caseList[0] if py_caseList else value.replace(' ', '_')
    return py_caseName

def check_card_fail(mcPort, mcSN):
    dirname = '{}_card{}'.format(mcSN, mcPort)
    dirname_path = osp.join(logs_path, dirname)
    card_faillog_path = osp.join(dirname_path, 'failure.log')
    return True if osp.exists(card_faillog_path) and UTP.get('FAIL_SKIP', False) else False

def record_card_fail(mcPort, mcSN, caseName, failure_info):
    dirname = '{}_card{}'.format(mcSN, mcPort)
    dirname_path = osp.join(logs_path, dirname)
    card_faillog_path = osp.join(dirname_path, 'failure.log')
    
    convert_caseName = get_keys(caseName.strip())
    error_code = get_errorcode(convert_caseName.strip())
    if not osp.exists(dirname_path):
        UTP.run(['mkdir', '-p', dirname_path])
    with open(card_faillog_path, mode='a') as test_log:
        test_log.write('{} {} {} {}\n'.format(time.strftime('%Y%m%d-%H%M%S',time.localtime()), convert_caseName, error_code, failure_info.replace(' ', '_')))
        test_log.flush()
        os.fsync(test_log.fileno())
    UTP.run(['chmod', '777', '-R', dirname_path])
    UTP.run(['chmod', '777', '-R', card_faillog_path])

def record_fail_case(caseName):
    mcPorts = detected_mlu370()
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = get_sn(mcPort)
        failure_info = '{} FAILED'.format(caseName)
        record_card_fail(mcPort, mcSN, caseName, failure_info)
    with open(mlu370_test_log_failed, 'a') as fw:
        fw.write('{} {} FAILED\n'.format(datetime.now().strftime("%Y-%m-%d-%H:%M:%S"), caseName))

def record_card_warn(mcPort, mcSN, caseName, warning_info):
    dirname = '{}_card{}'.format(mcSN, mcPort)
    dirname_path = osp.join(logs_path, dirname)
    card_warnlog_path = osp.join(dirname_path, 'warn.log')
    
    convert_caseName = get_keys(caseName.strip())
    if not osp.exists(dirname_path):
        UTP.run(['mkdir', '-p', dirname_path])
    with open(card_warnlog_path, mode='a') as test_log:
        test_log.write('{} {} {}\n'.format(time.strftime('%Y%m%d-%H%M%S',time.localtime()), convert_caseName, warning_info.replace(' ', '_')))
        test_log.flush()
        os.fsync(test_log.fileno())
    UTP.run(['chmod', '777', '-R', dirname_path])
    UTP.run(['chmod', '777', '-R', card_warnlog_path])

def get_mcu_ver(slot_port):
    mcu_version = ''
    content = UTP.run([debug_tool_path, '-i', slot_port, '-p', '5'], check = False)
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        if 'mcu_version:' in line:
            mcu_version = line.split(':')[1].replace('.', '').strip()
    if not mcu_version:
        logging.error('Read mcu version on Card{} FAILED'.format(slot_port))
    return mcu_version.upper()

def get_image_ver(slot_port):
    isse_m0_version = ''
    d2d_m0_version = ''
    ddr_m0_version = ''
    content = UTP.run([debug_tool_path, '-i', slot_port, '-p', '6'], check = False)
    for line in content.split('\n'):
        if 'isse_m0_version:' in line:
            isse_m0_version = line.split(':')[1].strip()
        elif 'd2d_m0_version:' in line:
            d2d_m0_version = line.split(':')[1].strip()
        elif 'ddr_m0_version:' in line:
            ddr_m0_version = line.split(':')[1].strip()
    return isse_m0_version.upper(),d2d_m0_version.upper(),ddr_m0_version.upper()

def mlu370_ddr_init(q, mcPort, caseName, init_tool, timeout=7200):
    if UTP.run('lsmod').strip().find('cambricon_drv') != -1:
        logging.info("The system installed cambricon driver, unload cambricon_drv")
        unload_mlu370_drivers()
    
    ddr_init_result = True
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    logging.info('{} Start on Card{} --> {}'.format(caseName, mcPort, mcSN))
    log_fname = osp.join(logs_path, format_fname(mcPort, mcSN))
    test_cmd = [init_tool, '-i', str(mcPort), '-f', '0']
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start\n'.format(caseName))
        test_log.write('Start = {}\n'.format(time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False, timeout=timeout)
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('End = {}\n'.format(time.ctime()))
        test_log.write('###{} End\n\n'.format(caseName))
    if proc.returncode:
        logging.error('{} Failed on Card{} with returncode {}'.format(caseName, mcPort, proc.returncode))
        ddr_init_result = False
        return q.put(ddr_init_result)
    return_context = ''
    return_context = proc.stdout.decode('utf-8')
    if "ERROR" in return_context:
        logging.error('{} Failed on Card{}'.format(caseName, mcPort))
        ddr_init_result = False
        return q.put(ddr_init_result)
    if "ddr init pass" not in return_context:
        logging.error('{} Failed on Card{}'.format(caseName, mcPort))
        ddr_init_result = False
        return q.put(ddr_init_result)
    if ddr_init_result:
        logging.info('{} successfully on Card{}'.format(caseName, mcPort))
    return q.put(ddr_init_result)

def mt_run_ddr_init(caseName, init_tool):
    logging.info('Starting {} for all Cards'.format(caseName))
    p_lst = []
    q = mp.Queue()
    mcPorts = detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.1)
        p = mp.Process(target=mlu370_ddr_init, args=(q, mcPort, caseName, init_tool))
        p.start()
        p_lst.append(p)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for i in range(mcPorts):
        res = q.get()
        if not res:
            allPassed = False
    return allPassed

def mlu370_ncs_one_card(q, mcPort, caseName, loops, overall, timeout=7200):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    case_name_format = caseName.ljust(19)
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    ncs_list_old = ['mlu370_ncs_mlu_c2c_topology', 'mlu370_ncs_mlu_c2c_allreduce', 
                'mlu370_ncs_mlu_c2c_arm_tri_bytrans_arm_tri_bytask', 
                'mlu370_ncs_mlu_c2c_arm_tri_bytrans_js_tri_bytask',
                'mlu370_ncs_mlu_c2c_err_dst_addr_nt',
                'mlu370_ncs_mlu_c2c_error_kernel',
                'mlu370_ncs_mlu_c2c_err_src_addr_hat',
                'mlu370_ncs_mlu_c2c_event_pre',
                'mlu370_ncs_mlu_c2c_multi_current_event',
                'mlu370_ncs_mlu_c2c_multi_event_erraddr_errkernel',
                'mlu370_ncs_mlu_c2c_nowait',
                'mlu370_ncs_mlu_c2c_nt',
                'mlu370_ncs_mlu_c2c_random_pre',
                'mlu370_ncs_mlu_c2c_reduce_post',
                'mlu370_ncs_mlu_c2c_resource_conf_nt',
                'mlu370_ncs_mlu_c2c_spec_test_full_rob',
                'mlu370_ncs_mlu_c2c_wait']
    
    ncs_list = ['mlu370_ncs_mlu_c2c_topology', 
                'mlu370_ncs_mlu_c2c_allreduce', 
                'mlu370_ncs_mlu_c2c_arm_tri_bytrans_arm_tri_bytask', 
                'mlu370_ncs_mlu_c2c_arm_tri_bytrans_js_tri_bytask',
                'mlu370_ncs_mlu_c2c_event_pre',
                'mlu370_ncs_mlu_c2c_multi_current_event',
                'mlu370_ncs_mlu_c2c_nt',
                'mlu370_ncs_mlu_c2c_random_pre',
                'mlu370_ncs_mlu_c2c_reduce_post']
    ncs_result = True
    start_time = datetime.now()
    ncs_result = mlu370_ncs_test(mcPort, 'driver', 'ncs', ncs_list, loops, overall)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    if ncs_result:
        logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    else:
        logging.error('{} Failed on Card{}'.format(case_name_format, mcPort))
    return q.put(ncs_result)

def mlu370_ncs_test(mcPort, dvt_type, case_type, case_list, loops='1', overall='', timeout=7200):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    
    all_case_passed = True
    dvt_path = osp.join(dvt_test_path, '{}/build/bin/mlu370'.format(dvt_type))
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, overall), format_fname(mcPort, mcSN, case_type)))
    for case_cmd in case_list:
        time.sleep(5)
        case_cmd_format = case_cmd.ljust(36)
        test_cmd = ['./{}'.format(case_cmd), mcPort, '2', loops]
        logging.debug('{} Start  on Card{} <{}>'.format(case_cmd_format, mcPort, mcSN))
        start_time = datetime.now()
        with open(log_fname, mode='a') as test_log:
            test_log.write('###{} Start\n'.format(case_cmd))
            test_log.write('Start = {}\n'.format(start_time.strftime("%Y-%m-%d-%H:%M:%S")))
            test_log.flush()
            os.fsync(test_log.fileno())
        proc = UTP.runproc_rt(test_cmd, cwd=dvt_path, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
        end_time = datetime.now()
        total_seconds = int((end_time - start_time).total_seconds())
        with open(log_fname, mode='a') as test_log:
            test_log.write('TEST_RTN={}\n'.format(proc.returncode))
            test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
            test_log.write('End = {}\n'.format(end_time.strftime("%Y-%m-%d-%H:%M:%S")))
            test_log.write('###{} End\n\n'.format(case_cmd))
        if proc.returncode:
            logging.error('{} Failed on Card{} with returncode {}'.format(case_cmd_format, mcPort, proc.returncode))
            all_case_passed = False
            break
        return_context = proc.stdout.decode('utf-8')
        if "FAILED" in return_context or "failed" in return_context:
            logging.error('{} Failed on Card{} with detect [FAILED]'.format(case_cmd_format, mcPort))
            all_case_passed = False
            break
        if "PASSED" not in return_context:
            logging.error('{} Failed on Card{} with not detect [PASSED]'.format(case_cmd_format, mcPort))
            all_case_passed = False
            break
        
        time.sleep(5)
        test_cmd = ['./{}'.format(case_cmd), mcPort, '3', loops]
        start_time = datetime.now()
        with open(log_fname, mode='a') as test_log:
            test_log.write('###{} Start\n'.format(case_cmd))
            test_log.write('Start = {}\n'.format(start_time.strftime("%Y-%m-%d-%H:%M:%S")))
            test_log.flush()
            os.fsync(test_log.fileno())
        proc = UTP.runproc_rt(test_cmd, cwd=dvt_path, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
        end_time = datetime.now()
        total_seconds = int((end_time - start_time).total_seconds())
        with open(log_fname, mode='a') as test_log:
            test_log.write('TEST_RTN={}\n'.format(proc.returncode))
            test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
            test_log.write('End = {}\n'.format(end_time.strftime("%Y-%m-%d-%H:%M:%S")))
            test_log.write('###{} End\n\n'.format(case_cmd))
        if proc.returncode:
            logging.error('{} Failed on Card{} with returncode {}'.format(case_cmd_format, mcPort, proc.returncode))
            all_case_passed = False
            break
        return_context = proc.stdout.decode('utf-8')
        if "FAILED" in return_context or "failed" in return_context:
            logging.error('{} Failed on Card{} with detect [FAILED]'.format(case_cmd_format, mcPort))
            all_case_passed = False
            break
        if "PASSED" not in return_context:
            logging.error('{} Failed on Card{} with not detect [PASSED]'.format(case_cmd_format, mcPort))
            all_case_passed = False
            break
    return all_case_passed

def mlu370_x8_ncs_one_card(q, mcPort, caseName, loops, dvt_dir, length=None, timeout=3600):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    
    length = len(caseName) if not length else length
    case_name_format = caseName.ljust(length)
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    ncs_list = ['mlu370_ncs_mlu_c2c_topology', 'mlu370_ncs_mlu_c2c_reduce_post', 'mlu370_ncs_mlu_c2c_nt']
    start_time = datetime.now()
    ncs_result = mlu370_x8_ncs_test(mcPort, mcSN, ncs_list, loops, dvt_dir)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    if ncs_result:
        logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    else:
        logging.error('{} Failed on Card{}'.format(case_name_format, mcPort))
        failure_message = '{} Failed on Card{}'.format(caseName, mcPort)
        record_card_fail(mcPort, mcSN, caseName, failure_message)
    return q.put(ncs_result)

def mlu370_x8_ncs_test(mcPort, mcSN, case_list, loops='1', dvt_dir='', timeout=3600):    
    all_case_passed = True
    dvt_path = osp.join(dvt_test_path, 'driver/build/bin/mlu370')
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, dvt_dir), format_fname(mcPort, mcSN, 'ncs')))
    
    board_type = get_mlu370_type(mcPort)
    port_list = ['2', '3'] if board_type in ['X4', 'X4K', 'X4L'] else ['0', '1', '2', '3']
    for case_cmd in case_list:
        ncs_loops = '1' if case_cmd == 'mlu370_ncs_mlu_c2c_topology' else loops
        time.sleep(1)
        for serdes_port in port_list:
            time.sleep(1)
            case_cmd_format = case_cmd.ljust(len(case_cmd))
            test_cmd = ['./{}'.format(case_cmd), mcPort, serdes_port, ncs_loops]
            start_time = datetime.now()
            with open(log_fname, mode='a') as test_log:
                test_log.write('###{} Start on {}\n'.format(' '.join(test_cmd), start_time.strftime("%Y-%m-%d-%H:%M:%S")))
                test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
                test_log.flush()
                os.fsync(test_log.fileno())
            proc = UTP.runproc_rt(test_cmd, cwd=dvt_path, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
            end_time = datetime.now()
            total_seconds = int((end_time - start_time).total_seconds())
            with open(log_fname, mode='a') as test_log:
                test_log.write('TEST_RTN={}\n'.format(proc.returncode))
                test_log.write('###{} End on {}\n\n'.format(' '.join(test_cmd), end_time.strftime("%Y-%m-%d-%H:%M:%S")))
            if proc.returncode:
                logging.error('{} Failed on Card{} with returncode {}'.format(case_cmd_format, mcPort, proc.returncode))
                all_case_passed = False
                break
            return_context = proc.stdout.decode('utf-8')
            if "FAILED" in return_context or "failed" in return_context:
                logging.error('{} Failed on Card{} with detect [FAILED]'.format(case_cmd_format, mcPort))
                all_case_passed = False
                break
            if "PASSED" not in return_context:
                logging.error('{} Failed on Card{} with not detect [PASSED]'.format(case_cmd_format, mcPort))
                all_case_passed = False
                break
    return all_case_passed

def mlu370_new_gdmac_test(q, mcPort, caseName, gdmac_cmd, loops, dvt_dir, dvt_name, length=None, timeout=7200):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    
    env_ipu = dict(os.environ)
    env_ipu.setdefault('MLU_VISIBLE_DEVICES', mcPort)
    dvt_path = osp.join(dvt_test_path, 'driver/build/bin/mlu370')
    
    length = len(caseName) if not length else length
    case_name_format = caseName.ljust(length)
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, dvt_dir), format_fname(mcPort, mcSN, dvt_name)))
    
    start_time = datetime.now()
    test_cmd = ['./{}'.format(gdmac_cmd), '2', '128', '4', loops]
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d %H:%M:%S")))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, cwd=dvt_path, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False, env=env_ipu)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('###{} End   on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    if proc.returncode:
        failure_message = '{} Failed on Card{} with returncode {}'.format(caseName, mcPort, proc.returncode)
        logging.error('{}'.format(failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return q.put(False)
    return_context = proc.stdout.decode('utf-8')
    if "FAILED" in return_context or "failed" in return_context:
        failure_message = '{} Failed on Card{} with detect FAILED'.format(caseName, mcPort)
        logging.error('{}'.format(failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return q.put(False)
    if "PASSED" not in return_context:
        failure_message = '{} Failed on Card{} with not detect PASSED'.format(caseName, mcPort)
        logging.error('{}'.format(failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return q.put(False)
    logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    return q.put(True)

def mlu370_resnet_u4_one_card(q, mcPort, caseName, resnet_cmd, loops, dimz, dvt_dir, dvt_name, timeout=7200):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    
    test_cmd = './{} {} {}'.format(resnet_cmd, loops, dimz)
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, dvt_dir), format_fname(mcPort, mcSN, dvt_name)))
    
    if check_card_fail(mcPort, mcSN):
        logging.info('{} Skiped on Card{}'.format(test_cmd, mcPort))
        return q.put(True)
    
    env_ipu = dict(os.environ)
    env_ipu.setdefault('MLU_VISIBLE_DEVICES', mcPort)
    dvt_path = osp.join(dvt_test_path, 'typicalnet/build/bin/mlu370')
    
    logging.info('{} Start  on Card{} <{}>'.format(test_cmd, mcPort, mcSN))
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(test_cmd, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, cwd=dvt_path, shell=True, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False, env=env_ipu)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(test_cmd))
        test_log.write('###{} End   on {}\n\n'.format(test_cmd, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    if proc.returncode:
        failure_message = '{} Failed on Card{} with returncode {}'.format(test_cmd, mcPort, proc.returncode)
        logging.error('{}'.format(failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return q.put(False)
    return_context = proc.stdout.decode('utf-8')
    if "FAILED" in return_context:
        failure_message = '{} Failed on Card{} with detect FAILED'.format(test_cmd, mcPort)
        logging.error('{}'.format(failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return q.put(False)
    if "PASSED" not in return_context:
        failure_message = '{} Failed on Card{} with not detect PASSED'.format(test_cmd, mcPort)
        logging.error('{}'.format(failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return q.put(False)
    
    seqname_path = osp.join(testcode_path, 'seqname.txt')
    if osp.exists(seqname_path):
        seq_name = UTP.run('cat {}'.format(seqname_path), shell=True).strip()
    else:
        seq_name = UTP.get('SEQNAME', 'mlu370mfg.seq').split('.')[0]
    seq_name = seq_name.split('.')[0] if seq_name.endswith('.seq') else seq_name
    
    cluster_time_check = True
    cluster_time = 0
    for line in return_context.split('\n'):
        line = line.strip()
        if not line:
            continue
        if 'time:' in line and 'us' in line:
            line = line.strip('us')
            cluster_time = int(line.split(':')[1].strip())//(1023*int(loops)*int(dimz))
            if cluster_time > 2666:
                cluster_time_check = False
    if mcSN[0:2] in ['53', '72'] and 'fct' in seq_name:
        if cluster_time == 0:
            failure_message = '{} Failed on Card{} with detect cluster time FAILED'.format(test_cmd, mcPort)
            logging.error('{}'.format(failure_message))
            record_card_fail(mcPort, mcSN, caseName, failure_message)
            return q.put(False)
        if not cluster_time_check:
            failure_message = '{} Failed on Card{} with cluster time <{}> more than 2666 FAILED'.format(test_cmd, mcPort, cluster_time)
            logging.error('{}'.format(failure_message))
            record_card_fail(mcPort, mcSN, caseName, failure_message)
            return q.put(False)
    logging.info('{} Passed on Card{} [{} sec]'.format(test_cmd, mcPort, total_seconds))
    return q.put(True)

def mlu370_cnnl_one_loop(mcPort, dvt_type, case_type, case_list, loop='0', dvt_dir='', timeout=1800):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    
    env_ipu = dict(os.environ)
    env_ipu.setdefault('MLU_VISIBLE_DEVICES', mcPort)
    
    all_case_passed = True
    dvt_path = osp.join(dvt_test_path, '{}/build/bin/mlu370'.format(dvt_type))
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, dvt_dir), format_fname(mcPort, mcSN, case_type)))
    for case_cmd in case_list:
        test_cmd = ['./{}'.format(case_cmd)]
        start_time = datetime.now()
        with open(log_fname, mode='a') as test_log:
            test_log.write('###{} Loop{} Start on {}\n'.format(case_cmd, loop, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
            test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
            test_log.flush()
            os.fsync(test_log.fileno())
        proc = UTP.runproc_rt(test_cmd, cwd=dvt_path, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False, env=env_ipu)
        end_time = datetime.now()
        total_seconds = int((end_time - start_time).total_seconds())
        with open(log_fname, mode='a') as test_log:
            test_log.write('TEST_RTN={}\n'.format(proc.returncode))
            test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
            test_log.write('###{} Loop{} End  on {}\n\n'.format(case_cmd, loop, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
        if proc.returncode:
            logging.error('{} Failed on Card{} with returncode {} -- Loop{}'.format(case_cmd, mcPort, proc.returncode, loop))
            all_case_passed = False
            break
        return_context = proc.stdout.decode('utf-8')
        if "FAILED" in return_context:
            logging.error('{} Failed on Card{} with detect [FAILED] -- Loop{}'.format(case_cmd, mcPort, loop))
            all_case_passed = False
            break
        if "ALL PASSED" not in return_context:
            logging.error('{} Failed on Card{} with not detect [PASSED] -- Loop{}'.format(case_cmd, mcPort, loop))
            all_case_passed = False
            break
    return all_case_passed

def mlu370_cnnl_one_card(q, mcPort, caseName, dvt_type, case_type, case_list, dvt_loops, dvt_dir, length=None, timeout=1800):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    
    length = len(caseName) if not length else length
    case_name_format = caseName.ljust(length)
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
        
    all_result = True
    start_time = datetime.now()
    for loop in range(int(dvt_loops)):
        one_loop_res = mlu370_cnnl_one_loop(mcPort, dvt_type, case_type, case_list, loop, dvt_dir)
        if not one_loop_res:
            all_result = False
            break
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    if all_result:
        logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    else:
        logging.error('{} Failed on Card{} [{} loops]'.format(case_name_format, mcPort, loop))
        failure_message = '{} Failed on Card{}'.format(caseName, mcPort)
        record_card_fail(mcPort, mcSN, caseName, failure_message)
    return q.put(all_result)

def mlu370_dvt_one_loop(mcPort, dvt_type, case_type, case_list, loop='0', dvt_dir='', timeout=1800):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    
    env_ipu = dict(os.environ)
    env_ipu.setdefault('MLU_VISIBLE_DEVICES', mcPort)
    
    all_case_passed = True
    dvt_path = osp.join(dvt_test_path, '{}/build/bin/mlu370'.format(dvt_type))
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, dvt_dir), format_fname(mcPort, mcSN, case_type)))
    for case_cmd in case_list:
        test_cmd = ['./{}'.format(case_cmd)]
        start_time = datetime.now()
        with open(log_fname, mode='a') as test_log:
            test_log.write('###{} Loop{} Start on {}\n'.format(case_cmd, loop, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
            test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
            test_log.flush()
            os.fsync(test_log.fileno())
        proc = UTP.runproc_rt(test_cmd, cwd=dvt_path, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False, env=env_ipu)
        end_time = datetime.now()
        total_seconds = int((end_time - start_time).total_seconds())
        with open(log_fname, mode='a') as test_log:
            test_log.write('TEST_RTN={}\n'.format(proc.returncode))
            test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
            test_log.write('###{} Loop{} End  on {}\n\n'.format(case_cmd, loop, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
        if proc.returncode:
            logging.error('{} Failed on Card{} with returncode {} -- Loop{}'.format(case_cmd, mcPort, proc.returncode, loop))
            all_case_passed = False
            break
        return_context = proc.stdout.decode('utf-8')
        if "FAILED" in return_context:
            logging.error('{} Failed on Card{} with detect [FAILED] -- Loop{}'.format(case_cmd, mcPort, loop))
            all_case_passed = False
            break
        if "PASSED" not in return_context:
            logging.error('{} Failed on Card{} with not detect [PASSED] -- Loop{}'.format(case_cmd, mcPort, loop))
            all_case_passed = False
            break
    return all_case_passed

def mlu370_dvt_one_card(q, mcPort, caseName, dvt_type, case_type, case_list, dvt_loops, dvt_dir, length=None, timeout=1800):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    
    length = len(caseName) if not length else length
    case_name_format = caseName.ljust(length)
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    all_result = True
    start_time = datetime.now()
    for loop in range(int(dvt_loops)):
        one_loop_res = mlu370_dvt_one_loop(mcPort, dvt_type, case_type, case_list, loop, dvt_dir)
        if not one_loop_res:
            all_result = False
            break
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    if all_result:
        logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    else:
        logging.error('{} Failed on Card{} [{} loops]'.format(case_name_format, mcPort, loop))
        failure_message = '{} Failed on Card{}'.format(caseName, mcPort)
        record_card_fail(mcPort, mcSN, caseName, failure_message)
    return q.put(all_result)

def new_mt_run_dvt_Test(caseName, dvt_type, case_type, case_list, dvt_loops, dvt_dir):
    p_lst = []
    q = mp.Queue()
    mcPorts = detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.1)
        p = mp.Process(target=mlu370_dvt_one_card, args=(q, mcPort, caseName, dvt_type, case_type, case_list, dvt_loops, dvt_dir))
        p.start()
        p_lst.append(p)
    time.sleep(0.5)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for mcPort in range(mcPorts):
        res = q.get()
        if not res:
            logging.error("Card{} res --> {}".format(mcPort, res))
            allPassed = False
    return allPassed

def mlu370_ddr_power_one_loop(mcPort, caseName, init_tool, loop, dvt_dir='stress-ddr', ddr_type='8', timeout=7200):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    
    test_cmd = [init_tool, '-i', str(mcPort), '-f', ddr_type]
    format_caseName = '{} Loop {}'.format(caseName, str(loop))
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, dvt_dir), format_fname(mcPort, mcSN, dvt_name='ddr_stress')))
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(format_caseName, start_time.strftime("%Y-%m-%d %H:%M:%S")))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False, timeout=timeout)
    end_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('###{} End   on {}\n\n'.format(format_caseName, end_time.strftime("%Y-%m-%d %H:%M:%S")))
    if proc.returncode:
        failure_message = '{} Failed on Card{} with returncode {}'.format(caseName, mcPort, proc.returncode)
        logging.error('{}'.format(failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return False
    return_context = ''
    return_context = proc.stdout.decode('utf-8')
    if "ERROR" in return_context:
        failure_message = '{} Failed on Card{} with detect ERROR'.format(caseName, mcPort)
        logging.error('{}'.format(failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return False
    if "ddr max power dt pass" not in return_context:
        failure_message = '{} Failed on Card{} with not detect ddr dt pass'.format(caseName, mcPort)
        logging.error('{}'.format(failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return False
    return True

def mlu370_ddr_power_one_card(q, mcPort, caseName, init_tool, loops, dvt_dir, length=None, ddr_type='8', timeout=7200):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    
    length = len(caseName) if not length else length
    case_name_format = caseName.ljust(length)
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    ddr_stress_result = True
    start_time = datetime.now()
    for loop in range(int(loops)):
        one_loop_res = mlu370_ddr_power_one_loop(mcPort, caseName, init_tool, loop, dvt_dir, ddr_type)
        if not one_loop_res:
            ddr_stress_result = False
            break
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    if ddr_stress_result:
        logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    else:
        logging.error('{} Failed on Card{}'.format(caseName, mcPort))
    return q.put(ddr_stress_result)    
    
def mlu370_ddr_stress(q, mcPort, caseName, init_tool, loops, dvt_dir='stress-ddr', timeout=7200):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, dvt_dir), format_fname(mcPort, mcSN, dvt_name='stress-ddr')))
    
    case_name_format = caseName.ljust(len(caseName))
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    ddr_stress_result = True
    test_cmd = [init_tool, '-i', str(mcPort), '-f', '1']
    start_time = datetime.now()
    for loop in range(int(loops)):
        format_caseName = '{} Loop {}'.format(caseName, str(loop))
        with open(log_fname, mode='a') as test_log:
            test_log.write('###{} Start on {}\n'.format(format_caseName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
            test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
            test_log.flush()
            os.fsync(test_log.fileno())
        proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False, timeout=timeout)
        with open(log_fname, mode='a') as test_log:
            test_log.write('TEST_RTN={}\n'.format(proc.returncode))
            test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
            test_log.write('###{} End  on {}\n\n'.format(format_caseName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
        if proc.returncode:
            logging.error('{} Failed on Card{} with returncode {}'.format(format_caseName, mcPort, proc.returncode))
            ddr_stress_result = False
            break
        return_context = ''
        return_context = proc.stdout.decode('utf-8')
        if "ERROR" in return_context:
            logging.error('{} Failed on Card{} with ERROR'.format(format_caseName, mcPort))
            ddr_stress_result = False
            break
        if "ddr dt pass" not in return_context:
            logging.error('{} Failed on Card{} with not detect [ddr dt pass]'.format(format_caseName, mcPort))
            ddr_stress_result = False
            break
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    if ddr_stress_result:
        logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    else:
        logging.error('{} Failed on Card{} [{} loops]'.format(case_name_format, mcPort, loop))
        failure_message = '{} Failed on Card{}'.format(caseName, mcPort)
        record_card_fail(mcPort, mcSN, caseName, failure_message)
    return q.put(ddr_stress_result)
    
def mt_run_ddr_stress(caseName, init_tool, loops, dvt_dir='stress-ddr'):
    logging.info('Starting {} for all Cards'.format(caseName))
    p_lst = []
    q = mp.Queue()
    mcPorts = detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(1)
        p = mp.Process(target=mlu370_ddr_stress, args=(q, mcPort, caseName, init_tool, loops, dvt_dir))
        p.start()
        p_lst.append(p)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for i in range(mcPorts):
        res = q.get()
        if not res:
            allPassed = False
    return allPassed

def mlu370_d2d_init(q, mcPort, caseName, init_tool, loops, overall='init-d2d', timeout=7200):
    if UTP.run('lsmod').strip().find('cambricon_drv') != -1:
        logging.info("The system installed cambricon driver, unload cambricon_drv")
        unload_mlu370_drivers()
    
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, overall), format_fname(mcPort, mcSN, dvt_name=overall)))
    
    case_name_format = caseName.ljust(len(caseName)+1)
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    d2d_init_result = True
    test_cmd = [init_tool, '-i', str(mcPort), '-t']
    start_time = datetime.now()
    for loop in range(int(loops)):
        format_caseName = '{} Loop {}'.format(caseName, str(loop))
        with open(log_fname, mode='a') as test_log:
            test_log.write('###{} Start\n'.format(format_caseName))
            test_log.write('Start = {}\n'.format(time.ctime()))
            test_log.flush()
            os.fsync(test_log.fileno())
        proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False, timeout=timeout)
        with open(log_fname, mode='a') as test_log:
            test_log.write('TEST_RTN={}\n'.format(proc.returncode))
            test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
            test_log.write('End = {}\n'.format(time.ctime()))
            test_log.write('###{} End\n\n'.format(format_caseName))
        if proc.returncode:
            logging.error('{} Failed on Card{} with returncode {}'.format(format_caseName, mcPort, proc.returncode))
            d2d_init_result = False
            break
        return_context = ''
        return_context = proc.stdout.decode('utf-8')
        if "ERROR" in return_context or "error" in return_context:
            logging.error('{} Failed on Card{} with error'.format(format_caseName, mcPort))
            d2d_init_result = False
            break
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    if d2d_init_result:
        logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    else:
        logging.error('{} Failed on Card{} [{} loops]'.format(case_name_format, mcPort, loop))
    return q.put(d2d_init_result)
    
def mt_run_d2d_init(caseName, init_tool, loops, overall='init-d2d'):
    logging.info('Starting {} for all Cards'.format(caseName))
    p_lst = []
    q = mp.Queue()
    mcPorts = detected_mlu370()
    for mcPort in range(mcPorts):
        time.sleep(0.2)
        p = mp.Process(target=mlu370_d2d_init, args=(q, mcPort, caseName, init_tool, loops, overall))
        p.start()
        p_lst.append(p)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for i in range(mcPorts):
        res = q.get()
        if not res:
            allPassed = False
    return allPassed

def x8_pcie_linkdown_test(mcPort, caseName, mc_dict, test_tool, loops, overall='pcie-test', gen1=False, timeout=7200):
    mcPort = str(mcPort)
    mcSN = mc_dict[mcPort]
    case_name_format = caseName.ljust(len(caseName))
    
    if check_card_fail(mcPort, mcSN):
        logging.info('{} Skiped on Card{}'.format(case_name_format, mcPort))
        return True
    
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, overall), format_fname(mcPort, mcSN, dvt_name='linkdown')))
    
    # ./PCIE_TEST_Tool -i 0 -D 370 -t 1 -L 5 -b -l 10000 -g 1
    test_cmd = [test_tool, '-i', mcPort, '-D', '370', '-t', '1', '-L', '5', '-b', '-l', loops, '-g', '4']
    if gen1:
        test_cmd = [test_tool, '-i', mcPort, '-D', '370', '-t', '1', '-L', '5', '-b', '-l', loops, '-g', '1']
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('###{} End  on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    if proc.returncode:
        failure_message = 'Failed on Card{} with returncode {}'.format(mcPort, proc.returncode)
        logging.error('{} {}'.format(case_name_format, failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return False
    logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    return True

def x4_pcie_linkdown_test(mcPort, caseName, mc_dict, test_tool, loops, overall='pcie-test', gen1=False, timeout=7200):
    mcPort = str(mcPort)
    mcSN = mc_dict[mcPort]
    case_name_format = caseName.ljust(len(caseName))
    
    if check_card_fail(mcPort, mcSN):
        logging.info('{} Skiped on Card{}'.format(case_name_format, mcPort))
        return True
    
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, overall), format_fname(mcPort, mcSN, dvt_name='linkdown')))
    
    # ./PCIE_TEST_Tool -i 0 -D 370 -t 1 -l 10000
    device_id = '365' if mcSN.startswith('56', 0, 2) else '370'
    test_cmd = [test_tool, '-i', mcPort, '-D', device_id, '-t', '1', '-l', loops, '-g', '4']
    if gen1:
        test_cmd = [test_tool, '-i', mcPort, '-D', device_id, '-t', '1', '-l', loops, '-g', '1']
    
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('###{} End  on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    if proc.returncode:
        failure_message = 'Failed on Card{} with returncode {}'.format(mcPort, proc.returncode)
        logging.error('{} {}'.format(case_name_format, failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return False
    logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    return True

def pcie_linkdown_test(q, mcPort, caseName, mc_dict, test_tool, loops, overall='pcie-test', gen1=False, timeout=7200):
    mcPort = str(mcPort)
    mcSN = mc_dict[mcPort]
    case_name_format = caseName.ljust(len(caseName))
    
    if check_card_fail(mcPort, mcSN):
        logging.info('{} Skiped on Card{}'.format(case_name_format, mcPort))
        return q.put(True)
    
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, overall), format_fname(mcPort, mcSN, dvt_name='linkdown')))
    
    # ./PCIE_TEST_Tool -i 0 -D 370 -t 1 -l 10000
    device_id = '365' if mcSN.startswith('56', 0, 2) else '370'
    test_cmd = [test_tool, '-i', mcPort, '-D', device_id, '-t', '1', '-l', loops, '-g', '4']
    if gen1:
        test_cmd = [test_tool, '-i', mcPort, '-D', device_id, '-t', '1', '-l', loops, '-g', '1']
    
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('###{} End  on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    if proc.returncode:
        failure_message = 'Failed on Card{} with returncode {}'.format(mcPort, proc.returncode)
        logging.error('{} {}'.format(case_name_format, failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return q.put(False)
    logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    return q.put(True)

def pcie_link_speed_test(q, mcPort, caseName, mc_dict, test_tool, loops, overall='pcie-test', timeout=7200):
    mcPort = str(mcPort)
    mcSN = mc_dict[mcPort]
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, overall), format_fname(mcPort, mcSN, dvt_name='speedchange')))
    
    case_name_format = caseName.ljust(len(caseName))
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    # ./PCIE_TEST_Tool -i 0 -D 370 -t 3 -g 4 -l 10000
    device_id = '365' if mcSN.startswith('56', 0, 2) else '370'
    test_cmd = [test_tool, '-i', mcPort, '-D', device_id, '-t', '3', '-l', loops]
    
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('###{} End  on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    if proc.returncode:
        failure_message = 'Failed on Card{} with returncode {}'.format(mcPort, proc.returncode)
        logging.error('{} {}'.format(case_name_format, failure_message))
        record_card_fail(mcPort, mcSN, caseName, failure_message)
        return q.put(False)
    logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    return q.put(True)

def mlu370_bsp_test(caseName, loops='1'):
    all_case_passed = True
    dvt_path = osp.join(dvt_test_path, 'bsp/build/bin/mlu370')
    
    test_cmd = ['./mlu370_bsp_startos_test']
    logging.info('{} Start  on All Cards'.format(caseName))
    log_fname = os.path.join(logs_path, mlu370_test_log)
    start_time = datetime.now()
    for loop in loops:
        with open(log_fname, mode='a') as test_log:
            test_log.write('###{} Loop{} Start on {}\n'.format(caseName, loop, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
            test_log.flush()
            os.fsync(test_log.fileno())
        proc = UTP.runproc_rt(test_cmd, cwd=dvt_path, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
        with open(log_fname, mode='a') as test_log:
            test_log.write('TEST_RTN={}\n'.format(proc.returncode))
            test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
            test_log.write('###{} Loop{} End  on {}\n\n'.format(caseName, loop, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
        if proc.returncode:
            logging.error('{} Failed on All Cards with returncode {}'.format(caseName, proc.returncode))
            all_case_passed = False
            break
        return_context = proc.stdout.decode('utf-8')
        if "FAILED" in return_context:
            logging.error('{} Failed on All Cards with detect [FAILED]'.format(caseName))
            all_case_passed = False
            break
        if "PASSED" not in return_context:
            logging.error('{} Failed on All Cards with not detect [PASSED]'.format(caseName))
            all_case_passed = False
            break
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    if all_case_passed:
        logging.info('{} Passed on All Cards [{} sec]'.format(caseName, total_seconds))
    return all_case_passed

def serdes_test_by_port(caseName, mcPort, serdesPort, test_type, test_tool, speed, overall):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, overall), format_fname(mcPort, mcSN, dvt_name='serdes')))
    
    case_name_format = '{} Port={} Type={}'.format(caseName, serdesPort, test_type)
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(case_name_format, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
        test_log.flush()
        os.fsync(test_log.fileno())
    
    # ./t_serdes_X4 -i 0 -b 0 -r 6 -s 50 -m 0
    test_cmd = [test_tool, '-i', mcPort, '-b', serdesPort, '-r', test_type, '-s', speed, '-m', '0']
    if test_type in ['5', '8']:
        test_cmd = [test_tool, '-i', mcPort, '-b', serdesPort, '-r', test_type, '-s', speed]
    proc = UTP.runproc_rt(test_cmd, cwd=osp.dirname(test_tool), log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('###{} End  on {}\n\n'.format(caseName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
    if proc.returncode:
        logging.error('{} Failed on Card{} with returncode {}'.format(case_name_format, mcPort, proc.returncode))
        return False
    if test_type == '2':
        return_context = proc.stdout.decode('utf-8')
        if "HBER Error Flag Clear" in return_context:
            logging.info('{} Warned on Card{} with detect [HBER Error Flag Clear]'.format(case_name_format, mcPort))
            return True
    return True

def serdes_type_one_card(q, caseName, mcPort, test_tool, retry_times, test_type, overall='serdes-test'):
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    
    case_name_format = caseName.ljust(len(caseName))
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    all_result = True
    start_time = datetime.now()
    serdes_port_list = ['2', '3'] if get_mlu370_type('0') in ['X4', 'X4K', 'X4L'] else ['0', '1', '2', '3']
    for serdes_port in serdes_port_list:
        type_result = False
        for i in range(int(retry_times)):
            if serdes_test_by_port(caseName, mcPort, serdes_port, test_type, test_tool, speed='50', overall=overall):
                type_result = True
                break
            time.sleep(2)
        if not type_result:
            all_result = False
            break
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    if all_result:
        logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    else:
        logging.error('{} Failed on Card{}'.format(case_name_format, mcPort))
    return q.put(all_result)

def serdes_test_one_card(q, mcPort, test_tool, loops, test_mode, overall='serdes-test'):
    caseName = 'Serdes Test'
    mcPort = str(mcPort)
    mcSN = get_sn(mcPort)
    case_name_format = caseName.ljust(19)
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    all_result = True
    start_time = datetime.now()
    for loop in range(int(loops)):
        port0_type1 = False
        for i in range(5):
            if serdes_test_by_port(caseName, mcPort, '0', '1', test_tool, speed='50', overall=overall):
                port0_type1 = True
                break
        if not port0_type1:
            all_result = False
            break
        
        port1_type1 = False
        for i in range(5):
            if serdes_test_by_port(caseName, mcPort, '1', '1', test_tool, speed='50', overall=overall):
                port1_type1 = True
                break
        if not port1_type1:
            all_result = False
            break
        
        time.sleep(1)
        port0_type2 = False
        for i in range(5):
            if serdes_test_by_port(caseName, mcPort, '0', '2', test_tool, speed='50', overall=overall):
                port0_type2 = True
                break
        if not port0_type2:
            all_result = False
            break
        
        port1_type2 = False
        for i in range(5):
            if serdes_test_by_port(caseName, mcPort, '1', '2', test_tool, speed='50', overall=overall):
                port1_type2 = True 
                break                
        if not port1_type2:
            all_result = False
            break
        
        time.sleep(1)
        if not serdes_test_by_port(caseName, mcPort, '0', test_mode, test_tool, speed='50', overall=overall):
            all_result = False
            break
        if not serdes_test_by_port(caseName, mcPort, '1', test_mode, test_tool, speed='50', overall=overall):
            all_result = False
            break
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    if all_result:
        logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    else:
        logging.error('{} Failed on Card{} [{} loops]'.format(case_name_format, mcPort, loop))
    return q.put(all_result)

def change_core_voltage(mcPort, mcSN, caseName, debug_tool, core_voltage):
    mcPort = str(mcPort)
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, 'voltage'), format_fname(mcPort, mcSN, dvt_name='change_voltage')))
    
    case_name_format = caseName.ljust(len(caseName))
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    # ./Debug_Tool -i 0 -w -a 0x0036806c -m 0x00ffff00 -v 0xA0000046
    hex_core_vol = '0xA00000{:02X}'.format(int(core_voltage))
    test_cmd = [debug_tool, '-i', mcPort, '-w', '-a', '0x0036806c', '-m', '0x00ffff00', '-v', hex_core_vol]
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    time.sleep(3)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('###{} End on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    if proc.returncode:
        logging.error('{} Failed on Card{} with returncode {}'.format(case_name_format, mcPort, proc.returncode))
        return False
    if not check_core_voltage(mcPort, mcSN, debug_tool, core_voltage):
        logging.error('{} Failed on Card{} Check Failed'.format(case_name_format, mcPort))
        return False
    logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    return True

def check_core_voltage(mcPort, mcSN, debug_tool, core_voltage, display=False):
    mcPort = str(mcPort)
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, 'voltage'), format_fname(mcPort, mcSN, dvt_name='change_voltage')))
    
    caseName = 'Check Core Voltage to 0.{}V'.format(core_voltage)
    case_name_format = caseName.ljust(len(caseName))
    if display:
        logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    # sudo ./MLU370_Debug_Tool_V0_0_4_x86 -i 0 -r -a 0x83D45A8
    test_cmd = [debug_tool, '-i', mcPort, '-r', '-a', '0x83D45A8']
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('###{} End on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    if proc.returncode:
        logging.error('{} Failed on Card{} with returncode {}'.format(case_name_format, mcPort, proc.returncode))
        return False
    return_context = ''
    return_context = proc.stdout.decode('utf-8')
    check_result = False
    for line in return_context.split('\n'):
        line = line.strip()
        if "value of addr 83d45a8 is" in line:
            len_line = len(line)
            hex_vol = line[len_line-4:len_line-2]
            decimal_vol = int(hex_vol,16)
            if decimal_vol == int(core_voltage):
                check_result = True
                break
            elif decimal_vol == int(core_voltage)-1:
                check_result = True
                break
    if not check_result:
        logging.error('{} Failed on Card{}'.format(case_name_format, mcPort))
        return False
    if display:
        logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    return True

def read_core_voltage(mcPort, debug_tool):
    core_voltage_int = 0
    # sudo ./MLU370_Debug_Tool_V0_0_4_x86 -i 0 -r -a 0x83D45A8
    test_cmd = [debug_tool, '-i', str(mcPort), '-r', '-a', '0x83D45A8']
    proc = UTP.runproc_rt(test_cmd, log_stdout=logging.DEBUG, stderr=subprocess.STDOUT, check=False)
    if proc.returncode:
        logging.error('Read Core Voltage Failed on Card{} with returncode {}'.format(caseName, mcPort, proc.returncode))
        return core_voltage_int
    return_context = ''
    return_context = proc.stdout.decode('utf-8')
    for line in return_context.split('\n'):
        line = line.strip()
        if not line:
            continue
        if "value of addr 83d45a8 is" in line:
            len_line = len(line)
            core_voltage_hex = line[len_line-4:len_line-2]
            core_voltage_int = int(core_voltage_hex, 16)
    return core_voltage_int

def read_reg_value(mcPort, debug_tool, reg_addr):
    reg_value = 0
    test_cmd = [debug_tool, '-i', str(mcPort), '-r', '-a', reg_addr]
    proc = UTP.runproc_rt(test_cmd, log_stdout=logging.DEBUG, stderr=subprocess.STDOUT, check=False)
    if proc.returncode:
        logging.error('Read Register Value Failed on Card{} with returncode {}'.format(caseName, mcPort, proc.returncode))
        return reg_value
    return_context = proc.stdout.decode('utf-8')
    for line in return_context.split('\n'):
        line = line.strip()
        if not line:
            continue
        if "value of addr {} is".format(reg_addr.lstrip('0x')) in line:
            reg_value = line.split('is')[1].strip()
    return reg_value

def change_soc_voltage(mcPort, mcSN, caseName, debug_tool, soc_voltage):
    mcPort = str(mcPort)
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, 'voltage'), format_fname(mcPort, mcSN, dvt_name='change_voltage')))
    
    case_name_format = caseName.ljust(len(caseName))
    logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    hex_soc_vol = {'74':'0xA24a0000', '75':'0xA24b0000', '76':'0xA24c0000', '78':'0xA24e0000'}.get(soc_voltage)
    if not hex_soc_vol:
        logging.error('{} Failed on Card{} with converting voltage'.format(case_name_format, mcPort))
        return False
    
    # ./Debug_Tool -i 0 -w -a 0x0036806c -m 0x0000ffff -v 0xA24c0000
    test_cmd = [debug_tool, '-i', mcPort, '-w', '-a', '0x0036806c', '-m', '0x0000ffff', '-v', hex_soc_vol]
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    time.sleep(3)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('###{} End on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    if proc.returncode:
        logging.error('{} Failed on Card{} with returncode {}'.format(case_name_format, mcPort, proc.returncode))
        return False
    if not check_soc_voltage(mcPort, mcSN, debug_tool, soc_voltage):
        logging.error('{} Failed on Card{} Check Failed'.format(case_name_format, mcPort))
        return False
    logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    return True

def check_soc_voltage(mcPort, mcSN, debug_tool, soc_voltage, display=False):
    mcPort = str(mcPort)
    log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, 'voltage'), format_fname(mcPort, mcSN, dvt_name='change_voltage')))
    
    caseName = 'Check SOC Voltage to 0.{}V'.format(soc_voltage)
    case_name_format = caseName.ljust(len(caseName))
    if display:
        logging.info('{} Start  on Card{} <{}>'.format(case_name_format, mcPort, mcSN))
    
    hex_soc_vol = {'74':'4a', '75':'4b', '76':'4c', '78':'4e'}.get(soc_voltage)
    if not hex_soc_vol:
        logging.error('{} Failed on Card{} with converting voltage'.format(case_name_format, mcPort))
        return False
    # sudo ./MLU370_Debug_Tool_V0_0_4_x86 -i 0 -r -a 0x83D45A8
    test_cmd = [debug_tool, '-i', mcPort, '-r', '-a', '0x83D45A8']
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    end_time = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('###{} End on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    if proc.returncode:
        logging.error('{} Failed on Card{} with returncode {}'.format(case_name_format, mcPort, proc.returncode))
        return False
    return_context = ''
    return_context = proc.stdout.decode('utf-8')
    check_result = False
    for line in return_context.split('\n'):
        line = line.strip()
        if "value of addr 83d45a8 is" in line:
            len_line = len(line)
            if line[len_line-2:] == hex_soc_vol:
                check_result = True
                break
    if not check_result:
        logging.error('{} Failed on Card{}'.format(case_name_format, mcPort))
        return False
    if display:
        logging.info('{} Passed on Card{} [{} sec]'.format(case_name_format, mcPort, total_seconds))
    return True

def read_register(mcPort, log_fname, reg_addr):
    caseName = "Read Register"
    debug_tool = osp.join(utilities_path, UTP.get('DEBUG_TOOL'))
    test_cmd = [debug_tool, '-i', mcPort, '-r', '-a', reg_addr]
    start_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, start_time.strftime("%Y-%m-%d-%H:%M:%S")))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, check=False)
    end_time = datetime.now()
    with open(log_fname, mode='a') as test_log:
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('###{} End on {}\n\n'.format(caseName, end_time.strftime("%Y-%m-%d-%H:%M:%S")))
    return True

def read_register_all_cards(reg_addr_list):
    mcPorts = detected_mlu370()
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = get_sn(mcPort)
        log_fname = osp.join(logs_path, '{}/{}'.format(format_dirname(mcPort, mcSN, 'voltage'), format_fname(mcPort, mcSN, dvt_name='read_register')))
        for reg_addr in reg_addr_list:
            read_register(mcPort, log_fname, reg_addr)

def remove_drv_flag():
    drv_load_flg = osp.join(logs_path, 'driver_loaded')
    if osp.exists(drv_load_flg):
        UTP.run(['rm', '-rf', drv_load_flg], log_stdout=logging.DEBUG)
        time.sleep(5)

def create_drv_flag():
    drv_load_flg = osp.join(logs_path, 'driver_loaded')
    UTP.run(['touch', drv_load_flg], log_stdout=logging.DEBUG)


if __name__ == '__main__':
    logging.error('hello world')
