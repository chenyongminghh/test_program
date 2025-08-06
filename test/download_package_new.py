#!/usr/bin/env python3

import os
import sys
import logging
import argparse
import subprocess
import os.path as osp
from collections import OrderedDict

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
utilities_path = osp.join(testcode_path, 'utilities')
modules_path = osp.join(testcode_path, 'modules')
sys.path.append(modules_path)
import UTP
import CAM

def check_md5sum(local_path, filename, md5value):
    logging.info('File <{}> check md5sum value'.format(osp.join(local_path, filename)))
    proc = UTP.runproc_rt(['md5sum', filename], log_stdout=logging.DEBUG, stderr=subprocess.STDOUT, check=False, cwd=local_path)
    if proc.returncode:
        logging.info('Create md5sum value Failed')
        return False
    rtn_md5, rtn_file = proc.stdout.decode('utf-8').strip().split()
    if rtn_md5 != md5value:
        logging.info('File <{}> check md5sum value mismatch'.format(osp.join(local_path, filename)))
        logging.info('actual-md5:{} expect-md5:{}'.format(rtn_md5, md5value))
        return False
    logging.info('File <{}> check md5sum value Success'.format(osp.join(local_path, filename)))
    return True

def copy_file(source_path, target_path, filename):
    source_file = osp.join(source_path, filename)
    target_file = osp.join(target_path, filename)
    if not osp.exists(source_file):
        logging.info('File <{}> not exists, please check'.format(source_file))
        return False
    logging.info('Copy {}/{} to {}'.format(source_path, filename, target_path))
    proc = UTP.runproc_rt(['cp', source_file, target_file], log_stdout=logging.INFO, stderr=subprocess.STDOUT, check=False)
    if proc.returncode:
        logging.info('File <{}> copy Failed'.format(filename))
        return False
    return True

def check_local_backup(local_path, filename, md5value):
    if not osp.exists(local_path):
        logging.info('Mkdir {}'.format(local_path))
        os.makedirs(local_path)
        return False
    local_file_path = osp.join(local_path, filename)
    if not osp.exists(local_file_path):
        logging.info('File <{}> not exists, need download'.format(local_file_path))
        return False
    if not check_md5sum(local_path, filename, md5value):
        return False
    return True

def delete_file(local_path, file_type):
    for root, dirs, files in os.walk(local_path):
        break
    for filename in files:
        if file_type in filename:
            file_path = osp.join(local_path, filename)
            logging.info('Remove local {}'.format(file_path))
            UTP.run(['rm', '-rf', file_path], log_stdout=logging.DEBUG)

def download_packages(server_path, local_path, utilities_path, filename, md5value, file_type):
    # Local not exists, copy from server to local
    # Local exists, but check md5sum Failed, copy from server to local
    # Local exists, and check md5sum Success, copy from local to utilities
    if not check_local_backup(local_path, filename, md5value):
        delete_file(local_path, file_type)
        if not copy_file(server_path, local_path, filename):
            return False
        if not check_md5sum(local_path, filename, md5value):
            return False
    if not copy_file(local_path, utilities_path, filename):
        return False
    return True

def main(args):
    case_name = 'Download DVT Packages'
    logging.info(case_name, section=True)
    
    main_path = osp.dirname(osp.dirname(testcode_path))
    nfs_path = osp.join(main_path, "spider_test")
    local_path = osp.join(main_path, 'campackages')
    server_path = osp.join(nfs_path, 'utilities')
    
    download_result = True
    download_dict = OrderedDict()
    download_dict['mlu370_dvt_test'] = ['DVT_PACKAGE', 'DVT_PACKAGE_MD5SUM']
    download_dict['MLU290_BA_BMC'] = ['BMC_PACKAGE', 'BMC_PACKAGE_MD5SUM']
    for file_type in download_dict.keys():
        logging.info('Start checking {} file package'.format(file_type))
        package_name = UTP.get(download_dict.get(file_type)[0], '')
        md5value = UTP.get(download_dict.get(file_type)[1], '')
        utilities_dvt_file = osp.join(utilities_path, package_name)
        if osp.exists(utilities_dvt_file) and check_md5sum(utilities_path, package_name, md5value):
            logging.info('File <{}> exists, skip download and checking'.format(package_name))
            continue
        if download_packages(server_path, local_path, utilities_path, package_name, md5value, file_type):
            logging.info('Download {} file package success'.format(file_type))
        else:
            logging.info('Download {} file package Failed'.format(file_type))
            download_result = False
    
    result = 'PASS' if download_result else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    else:
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
        raise Exception('There are some card boot failed.')
    return
    
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    sys.exit(main(args))
