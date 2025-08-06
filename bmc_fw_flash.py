#!/usr/bin/env python3
"""
  if exists fl_bmc_don and not --force, skip bmc firmware flash
  if bmc_flash_required = False and not --force, skip bmc firmware flash
  if bmc_flash_required = True or --force, start bmc firmware flash
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
import CAM

flash_dir = osp.join(testcode_path, 'bmc')
bmc_image = UTP.get('BMC_IMAGE')
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

def flash_firmware(bmc_ip, caseName, flash_tool_path):
    # ./Yafuflash -f -non-interactive -nw -ip 192.168.100.50 -u admin -p admin -mse 3 MLU290_BA_bmc_v0.01.0000.ima
    caseName = 'BMC Firmware Flash'
    flash_tool_dir = osp.dirname(flash_tool_path)
    flash_cmd = ['./{}'.format(FLASH_TOOL), '-f', '-non-interactive', '-nw', '-ip', bmc_ip, '-u', 'admin', '-p', 'admin', '-mse', '3', bmc_image, '-preserve-net']
    logging.info('flash_tool directory --> {}'.format(flash_tool_dir))
    logging.info('flash_cmd --> {}'.format(' '.join(flash_cmd)))
    logging.info('Please wait about 15 minutes.')
    
    log_fname = os.path.join(logs_path, 'fw_bmc_flash.log')
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Start on {}\n'.format(caseName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
        test_log.write('TEST_CMD={}\n'.format(' '.join(flash_cmd)))
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
        logging.info('BMC Firmware Flash Completed')
        return True
    else:
        time.sleep(60)
        logging.error('BMC Firmware Flash failed with returncode {}'.format(proc.returncode))
        return False
    
def main(args):
    case_name = 'BMC Firmware Flash'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    bmc_ip_list = imm.get_bmc_ip()
    logging.info('bmc_ip_list:{}'.format(bmc_ip_list))
    
    flash_tool_path = flash_extract()
    
    all_passed = True
    for imm_num in range(imm_qty):
        bmc_flash_required = False
        don_flag = 'fl_bmc{}_don'.format(imm_num)
        
        image1_level = imm.get_bmc_fw_level_image1(imm_num)
        image2_level = imm.get_bmc_fw_level_image2(imm_num)
        image1_flash_req = True if UTP.get('BMC_OKAY') != image1_level else False
        image2_flash_req = True if UTP.get('BMC_OKAY') != image2_level else False
        logging.info('Current BMC<{}> Image1 Firmware Version --> {}'.format(imm_num, image1_level))
        logging.info('Current BMC<{}> Image2 Firmware Version --> {}'.format(imm_num, image2_level))
        
        if image1_flash_req or image2_flash_req:
            logging.info('BMC<{}> FW Flash Required is True.'.format(imm_num))
            bmc_flash_required = True
        if bmc_flash_required:
            if UTP.get(don_flag, False):
                if args.force:
                    logging.info('bmc_flash_required = True, and don flag <{}> exists.'.format(don_flag))
                    logging.info('but args.force = True, flash the firmware forcely.')
                else:
                    logging.error('bmc_flash_required = True, but don flag exists, please check the environment.')
                    CAM.record_fail_case(case_name)
                    raise Exception('bmc_flash_required = True, but don flag exists, please check the environment.')
            else:
                logging.info('bmc_flash_required = True, flash the firmware normally.')
        else:
            if args.force:
                logging.info('args.force = True, flash the firmware forcely.')
            else:
                logging.info('bmc_flash_required = False, skip...')
                continue
        
        logging.info('BMC<{}> Starting FW Flash'.format(imm_num))
        bmc_ip = bmc_ip_list[imm_num]
        if flash_firmware(bmc_ip, case_name, flash_tool_path):
            logging.info('BMC<{}> FW Flash Success'.format(imm_num))
            UTP.set(don_flag, True)
        else:
            logging.error('BMC<{}> FW Flash Failed'.format(imm_num))
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
