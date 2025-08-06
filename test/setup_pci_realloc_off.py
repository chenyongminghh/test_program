#!/usr/bin/env python3
import os
import sys
import time
import shutil
import logging
import argparse
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
tests_path = osp.join(testcode_path, 'tests')
utilities_path = osp.join(testcode_path, 'utilities')
sys.path.append(modules_path)
import UTP
import CAM

def chmod_file(file_path, mode='755'):
    cmd_chmod = 'sudo chmod -R {} {}'.format(mode, file_path)
    UTP.run(cmd_chmod, shell=True)

def chown_file(file_path, username):
    UTP.run('sudo chown -R {}:{} {}'.format(username, username, file_path), shell=True)
    UTP.run('sudo chmod -R 755 {}'.format(file_path), shell=True)
    
def alter_string(file_name, old_str, new_str):
    logging.info('Update {}'.format(file_name))
    with open(file_name, "r", encoding="utf-8") as f1:
        context_list = f1.readlines()
    with open("{}.bak".format(file_name), "w", encoding="utf-8") as f2:
        for line in context_list:
            if old_str in line:
                logging.info('Old Line:{}'.format(line.strip()))
                line = line.replace(old_str, new_str)
                logging.info('New Line:{}'.format(line.strip()))
            f2.write(line)
    os.remove(file_name)
    os.rename("{}.bak".format(file_name), file_name)

def add_string(file_name, new_str):
    logging.info('Update {}'.format(file_name))
    with open(file_name, "r", encoding="utf-8") as f1:
        context_list = f1.readlines()
    with open("{}.bak".format(file_name), "w", encoding="utf-8") as f2:
        for line in context_list:
            if '/boot' in line and 'linux' in line and 'root=UUID' in line:
                if "pci=realloc" not in line:
                    logging.info('Old Line:{}'.format(line.strip()))
                    line = line.rstrip() + ' ' + new_str + '\n'
                    logging.info('New Line:{}'.format(line.strip()))
            f2.write(line)
    os.remove(file_name)
    os.rename("{}.bak".format(file_name), file_name)

def main(args):
    logging.info('Setup PCI Realloc Off', section=True)
    
    grub_file_path = '/boot/grub/grub.cfg'
    grub_nvme_file_path = '/boot/grub/grub.cfg.nvme'

    if not osp.exists(grub_file_path):
        logging.error('Not exists /boot/grub/grub.cfg, Please check host')
        raise Exception('Not exists /boot/grub/grub.cfg, Please check host')

    if osp.exists(grub_nvme_file_path):
        logging.info('Modify grub.cfg from grub.cfg.nvme')
        UTP.run(['cp', '-rf', grub_nvme_file_path, grub_file_path], log_stdout=logging.INFO)
        chmod_file(grub_file_path, mode='744')
        alter_string(grub_file_path, 'pci=realloc=on', 'pci=realloc=off')
        chmod_file(grub_file_path, mode='444')
    else:
        logging.info('Modify grub.cfg directly')
        chmod_file(grub_file_path, mode='744')
        add_string(grub_file_path, 'pci=realloc=off')
        chmod_file(grub_file_path, mode='444')
    return

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    sys.exit(main(args))
