#!/usr/bin/python3.5
import os
import sys
import time
import logging
import argparse
import subprocess
import os.path as osp
from collections import OrderedDict

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
sttools_path = osp.join(testcode_path, 'sttools')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import CAM

dvt_ver_path = osp.join(sttools_path, UTP.get('DVT_VER'))
assist_org = osp.join(dvt_ver_path, 'mlu370_dvt_test/ipu/tools/release_run_inst_tool/assist_org')
assist_path = osp.join(dvt_ver_path, 'mlu370_dvt_test/ipu/tools/release_run_inst_tool/assist')
assist_pincs = osp.join(dvt_ver_path, 'mlu370_dvt_test/ipu/tools/release_run_inst_tool/assist_pincs')

card_qty = CAM.detected_mlu370()
check_list = ['card 0', 'card 1', 'card 2', 'card 3', 'card 4', 'card 5', 'card 6', 'card 7', 'card 8', 'card 9', 'card 10', 'card 11', 'card 12', 'card 13', 'card 14', 'card 15'][0:card_qty]

def grep_time(name):
    current_time = 0
    output=UTP.run("dmesg | grep '{} boot ok'| grep -v grep".format(name), shell=True, check=False)
    for line in output.splitlines():
        time_stamp = line.split(']')[0].strip(' []')
        current_time = time_stamp.split('.')[0].strip()
    return current_time

def check_boot_ok(last_time):
    time_count = 0
    boot_ok_list = list()
    while True:
        logging.info('waiting 2 seconds for card boot ...')
        time.sleep(2)
        
        all_boot_ok = True
        for name in check_list:
            if name in boot_ok_list:
                continue
            current_time = grep_time(name)
            if int(current_time) <= int(last_time[name]):
                all_boot_ok = False
            else:
                logging.info('{} boot ok --> {}'.format(name, current_time))
                boot_ok_list.append(name)
        
        if all_boot_ok:
            break
        elif time_count > 300:
            break
        else:
            time_count += 2
    return all_boot_ok

def load_mlu370_drivers(caseName, load_driver_path, virtual=False):
    logging.info('Clear host caches')
    UTP.run("sync; echo 3 > /proc/sys/vm/drop_caches", shell=True, log_stdout=logging.INFO)
    logging.info('Start loading cambricon_drv driver')
    logging.info('{}'.format(load_driver_path))
    load_driver_dir = osp.dirname(load_driver_path)
    test_cmd = ['./load_driver.sh', '-v'] if virtual else ['./load_driver.sh', '-p']
    log_fname = os.path.join(logs_path, 'mlu370_test.log')
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Test Start on {}\n'.format(caseName, time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, cwd=load_driver_dir, check=False)
    with open(log_fname, mode='a') as test_log:
        test_log.write('\n')
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('###{} Test End on {}\n\n'.format(caseName, time.ctime()))
    load_result = True
    if proc.returncode:
        logging.error('Load cambricon_drv driver failed with returncode {}'.format(proc.returncode))
        load_result = False
    return_context = proc.stdout.decode('utf-8')
    if "fail" in return_context or "FAIL" in return_context:
        logging.error('Load cambricon_drv driver failed, please check mlu370_test.log')
        load_result = False
    if ">>>DONE" not in return_context:
        logging.error('Load cambricon_drv driver failed, please check mlu370_test.log')
        load_result = False
    return load_result

def deploy_ncs_env(ncs_flag, board_type):
    if board_type not in ['X4', 'X4K', 'X4L']:
        return True
    if not ncs_flag:
        return True
    
    caseName = 'deploying mlu370-x4 ncs env'
    logging.info('Start deploying mlu370-x4 ncs env')
    test_cmd = ['./deploy_ncs_env.sh', '2', 'ilkn']
    log_fname = os.path.join(logs_path, 'mlu370_test.log')
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Test Start on {}\n'.format(caseName, time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, cwd=dvt_ver_path, check=False)
    with open(log_fname, mode='a') as test_log:
        test_log.write('\n')
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('###{} Test End on {}\n\n'.format(caseName, time.ctime()))
    deploy_result = True
    return_context = proc.stdout.decode('utf-8')
    for i in range(card_qty):
        checking_str = 'Card {} serdes init finished'.format(str(i))
        if checking_str not in return_context:
            logging.error('{} --> Not detected'.format(checking_str))
            deploy_result = False
    if deploy_result:
        logging.info('Deploying mlu370-x4 ncs env success')
    return deploy_result


def deploy_ncs_retry():
    # 2023/06/05 for M8, X8 PI+NCS
    caseName = 'deploying mlu370-x8,m8 pi and ncs retry'
    logging.info('Start deploying mlu370-x8,m8 pi and ncs retry')
    test_cmd = ['./open_retry.sh', ]
    log_fname = os.path.join(logs_path, 'mlu370_test.log')
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Test Start on {}\n'.format(caseName, time.ctime()))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(test_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, cwd=dvt_ver_path, check=False)
    with open(log_fname, mode='a') as test_log:
        test_log.write('\n')
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('TEST_CMD={}\n'.format(' '.join(test_cmd)))
        test_log.write('###{} Test End on {}\n\n'.format(caseName, time.ctime()))
    deploy_result = False if proc.returncode else True
    if deploy_result:
        logging.info('Deploying mlu370-x8,m8 pi and ncs retry success')
    return deploy_result


def main(args):
    case_name = 'mlu370 Load DVT Driver'
    logging.info(case_name, section=True)
    
    UTP.run(['rm', '-rf', assist_path], log_stdout=logging.DEBUG)
    if args.pincs:
        UTP.run(['cp', '-rf', assist_pincs, assist_path], log_stdout=logging.DEBUG)
    else:
        UTP.run(['cp', '-rf', assist_org, assist_path], log_stdout=logging.DEBUG)
   
    board_type = CAM.get_mlu370_type('0')
 
    last_time = OrderedDict()
    for name in check_list:
        last_time[name] = grep_time(name)
    assert last_time, 'There has error when grep last time'
    logging.info('boot ok last time = {}'.format(last_time))
    
    ncs_flag = True
    if CAM.get_mlu370_type('0') == 'S8':
        release_ver = osp.join(dvt_ver_path, UTP.get('RELEASE_VER_S8'))
    elif CAM.get_mlu370_type('0') in ['X9', 'X9L']:
        release_ver = osp.join(dvt_ver_path, UTP.get('RELEASE_VER_X9'))
    else:
        release_ver = osp.join(dvt_ver_path, UTP.get('RELEASE_VER'))
    
    if args.pincs:
        ncs_flag = False
        if CAM.get_mlu370_type('0') in ['X9', 'X9L']:
            release_ver = osp.join(dvt_ver_path, UTP.get('RELEASE_PINCS_X9', 'release_neuware_PIandNCS_special'))
        else:
            release_ver = osp.join(dvt_ver_path, UTP.get('RELEASE_PINCS', 'release_neuware_PIandNCS_special'))
    
    if args.powerddr:
        ncs_flag = False
        if CAM.get_mlu370_type('0') == 'D2':
            release_ver = osp.join(dvt_ver_path, UTP.get('RELEASE_POWERDDR_D2', 'release_power_ddr'))
        else:
            release_ver = osp.join(dvt_ver_path, UTP.get('RELEASE_POWERDDR', 'release_power_ddr'))
    
    if board_type == 'X4K':
        if not UTP.get('X4_SERDES_LINE', None):
            if not UTP.get('MFG_MODE', None):
                ncs_flag = False
    else:
        ncs_flag = False
    
    logging.info('Driver version {}'.format(release_ver))
    
    release_ver_path = osp.join(dvt_ver_path, release_ver)
    load_driver_path = osp.join(release_ver_path, 'neuware/tools/startup-system/load_driver.sh')
    load_result = load_mlu370_drivers(case_name, load_driver_path, args.virtual)    
    
    result = 'PASS' if load_result and check_boot_ok(last_time) else 'FAIL'
    if result == 'PASS':
        logging.info('All cards boot ok.')
        deploy_ncs_env(ncs_flag, board_type)
        if args.pincs:
            deploy_ncs_retry()
        CAM.create_drv_flag()
        logging.info('{} PASSED'.format(case_name))
        time.sleep(1)
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
        raise Exception('There are some card boot failed.')
    return
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--virtual', action='store_true', help='virtual tty')
    parser.add_argument('--powerddr', action='store_true', help='virtual tty')
    parser.add_argument('--pincs', action='store_true', help='PI and NCS Driver')
    args = parser.parse_args()
    sys.exit(main(args))
