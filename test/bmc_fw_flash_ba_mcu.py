#!/usr/bin/env python3
"""
  if exists fl_bmc_don and not --force, skip ba mcu firmware flash
  if ba_mcu_flash_required = False and not --force, skip ba mcu firmware flash
  if ba_mcu_flash_required = True or --force, start ba mcu firmware flash
"""
import os
import sys
import time
import logging
import subprocess
import os.path as osp
import argparse

file_path = osp.abspath(__file__)
tests_path = osp.dirname(osp.abspath(__file__))
testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
utilities_path = osp.join(testcode_path, 'utilities')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import IMM
import FRU
import CAM

flash_dir = osp.join(testcode_path, 'bmc')
ba_mcu_image = UTP.get('BA_MCU_IMAGE', '')
assert ba_mcu_image, 'Please check the BA MCU Image setting'
bmc_package = osp.join(utilities_path, UTP.get('BMC_PACKAGE'))
FLASH_TOOL = "Yafuflash"

def flash_extract():
    if osp.exists(flash_dir):
        logging.info('Remove old folder {}'.format(flash_dir))
        UTP.run(['rm', '-rf', flash_dir])
    logging.info('Extracting BA BMC Image Package to {}'.format(flash_dir))
    UTP.run(['unzip', '-o', bmc_package, '-d', flash_dir])
    UTP.run(['chmod', '777', '-R', flash_dir])
    logging.info('Unzip BMC image package successfully')
    return UTP.run(['find', flash_dir, '-name', FLASH_TOOL]).strip()

def flash_firmware(bmc_ip, caseName):
    # ./Yafuflash -nw -ip bmcip -u username -p password -d 0x100 image.bin
    flash_tool_path = flash_extract()
    flash_tool_dir = osp.dirname(flash_tool_path)
    flash_cmd = ['./{}'.format(FLASH_TOOL), '-nw', '-ip', bmc_ip, '-u', 'admin', '-p', 'admin', '-d', '0x100', ba_mcu_image]
    logging.info('flash_tool directory --> {}'.format(flash_tool_dir))
    logging.info('flash_cmd --> {}'.format(' '.join(flash_cmd)))
    logging.info('Please wait about 2 minutes.')
    
    log_fname = os.path.join(logs_path, 'fw_ba_mcu_flash.log')
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
        test_log.write('TEST_CMD={}\n'.format(flash_cmd))
        test_log.flush()
        os.fsync(test_log.fileno())
    media_to_log = (log_fname, logging.DEBUG)
    proc = UTP.runproc_rt(flash_cmd, cwd=flash_tool_dir, log_stdout=media_to_log, stderr=subprocess.STDOUT)
    with open(log_fname, mode='a') as test_log:
        test_log.write('\n')
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('###{} End  on {}\n\n'.format(caseName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
    if proc.returncode == 0:
        time.sleep(60)
        logging.info('{} Completed!'.format(caseName))
        return True
    else:
        time.sleep(60)
        logging.error('{} failed with returncode {}'.format(caseName, proc.returncode))
        return False

def main(args):
    case_name = 'BMC BA MCU Firmware Flash'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    bmc_ip_list = imm.get_bmc_ip()
    logging.info('bmc_ip_list:{}'.format(bmc_ip_list))
    
    all_passed = True
    for imm_num in range(imm_qty):
        ba_mcu_flash_required = False
        don_flag = 'fl_bmc{}_ba_mcu_don'.format(imm_num)
        current_version = imm.get_ba_mcu_version(imm_num)
        if UTP.get('BA_MCU_OKAY') != current_version:
            logging.info('BMC<{}> {} Required is True.'.format(imm_num, case_name))
            ba_mcu_flash_required = True
        if ba_mcu_flash_required:
            logging.info('BMC<{}> Current BA MCU Version --> {}'.format(imm_num, current_version))
            if UTP.get(don_flag, False):
                if args.force:
                    logging.info('BMC<{}> ba_mcu_flash_required = True, and don flag <{}> exists.'.format(imm_num, don_flag))
                    logging.info('BMC<{}> but args.force = True, flash the firmware forcely.'.format(imm_num))
                else:
                    logging.error('BMC<{}> ba_mcu_flash_required = True, but don flag exists, please check the environment.'.format(imm_num))
                    CAM.record_fail_case(case_name)
                    raise Exception('BMC<{}> ba_mcu_flash_required = True, but don flag exists, please check the environment.'.format(imm_num))
            else:
                    logging.info('BMC<{}> ba_mcu_flash_required = True, flash the firmware normally.'.format(imm_num))
        else:
            logging.info('BMC<{}> Current BA MCU Version --> {} match the expect version'.format(imm_num, current_version))
            if args.force:
                logging.info('BMC<{}> args.force = True, flash the firmware forcely.'.format(imm_num))
            else:
                logging.info('BMC<{}> ba_mcu_flash_required = False, skip...'.format(imm_num))
                continue
        logging.info('BMC<{}> Starting {}'.format(imm_num, case_name))
        bmc_ip = bmc_ip_list[imm_num]
        if flash_firmware(bmc_ip, case_name):
            logging.info('BMC<{}> {} Success'.format(imm_num, case_name))
            UTP.set(don_flag, True)
        else:
            logging.error('BMC<{}> {} Failed'.format(imm_num, case_name))
            all_passed = False
    
    result = 'PASS' if all_passed else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.error('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        logging.error('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
        raise Exception('{} FAILED'.format(case_name))
    return

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='Force flash the firmware')
    args = parser.parse_args()
    sys.exit(main(args))
