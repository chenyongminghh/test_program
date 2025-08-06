#!/usr/bin/env python3

import os
import sys
import logging
import os.path as osp

file_path = osp.abspath(__file__)
tests_path = osp.dirname(osp.abspath(__file__))
testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')

sys.path.append(modules_path)
import UTP
import IMM
import CAM
import FRU

def main():
    case_name = 'BMC Firmware Check'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    results = []
    table_header = ['Firmware', 'Expected', 'Actual', 'Needs Flash']
    for imm_num in range(imm_qty):
        image1_level = imm.get_bmc_fw_level_image1(imm_num)
        image1_flash_req = True if UTP.get('BMC_OKAY') != image1_level else False
        results.append(['BMC<{}> Image1 Version'.format(imm_num), UTP.get('BMC_OKAY'), image1_level, image1_flash_req])
        
        image2_level = imm.get_bmc_fw_level_image2(imm_num)
        image2_flash_req = True if UTP.get('BMC_OKAY') != image2_level else False
        results.append(['BMC<{}> Image2 Version'.format(imm_num), UTP.get('BMC_OKAY'), image2_level, image2_flash_req])
        
        ba_mcu_level = imm.get_ba_mcu_version(imm_num)
        ba_mcu_flash_req = True if UTP.get('BA_MCU_OKAY') != ba_mcu_level else False
        results.append(['BMC<{}> BA MCU Version'.format(imm_num), UTP.get('BA_MCU_OKAY'), ba_mcu_level, ba_mcu_flash_req])
        
        fru_lookup = FRU.parse_fru_logs(imm_num)
        fru_device = fru_lookup.get('Builtin FRU Device')
        board_extra_list = fru_device.get('Board Extra')
        actual_sw0_version = ''
        actual_sw1_version = ''
        for item in board_extra_list:
            if 'PCIe SW0 Version:' in item:
                actual_sw0_version = item.split(':')[1].strip()
            elif 'PCIe SW1 Version:' in item:
                actual_sw1_version = item.split(':')[1].strip()
        sw0_flash_req = True if UTP.get('PCIE_SW_OKAY') != actual_sw0_version else False
        sw1_flash_req = True if UTP.get('PCIE_SW_OKAY') != actual_sw1_version else False
        results.append(['BMC<{}> PCIE SW0 Version'.format(imm_num), UTP.get('PCIE_SW_OKAY'), actual_sw0_version, sw0_flash_req])
        results.append(['BMC<{}> PCIE SW1 Version'.format(imm_num), UTP.get('PCIE_SW_OKAY'), actual_sw1_version, sw1_flash_req])
        
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
