#!/usr/bin/env python3

import os
import sys
import logging
import os.path as osp

file_path = osp.abspath(__file__)
tests_path = osp.dirname(osp.abspath(__file__))
testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import IMM
import CAM

def main():
    case_name = 'BMC PSU Firmware Check'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    results = []
    table_header = ['PSU SN', 'Firmware', 'Expected', 'Actual', 'Needs Flash']
    for imm_num in range(imm_qty):
        psu0_mfg = imm.get_psu_mfg(imm_num, '0')
        psu1_mfg = imm.get_psu_mfg(imm_num, '1')
        if psu0_mfg == "Great Wall" or psu1_mfg == "Great Wall":
            psu_ver_expect = UTP.get('PSU_OKAY_GW')
        else:
            psu_ver_expect = UTP.get('PSU_OKAY_TAIDA')
        
        psu0_sn = imm.get_psu_sn(imm_num, '0')
        psu1_sn = imm.get_psu_sn(imm_num, '1')
        
        psu0_fw_actual = imm.get_psu_version(imm_num, '0')
        psu1_fw_actual = imm.get_psu_version(imm_num, '1')
        
        psu0_flash_req = True if psu_ver_expect != psu0_fw_actual else False
        results.append([psu0_sn, 'BMC<{}> PSU0 Version'.format(imm_num), psu_ver_expect, psu0_fw_actual, psu0_flash_req])
        psu1_flash_req = True if psu_ver_expect != psu1_fw_actual else False
        results.append([psu1_sn, 'BMC<{}> PSU1 Version'.format(imm_num), psu_ver_expect, psu1_fw_actual, psu1_flash_req])
    
    table_settings = {'header': table_header, 'footer': False, 'str_is_str': True}
    logging.info(results, table=table_settings)
    
    result = 'PASS' if not any(each_result[-1] for each_result in results) else 'FAIL'
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
    sys.exit(main())
