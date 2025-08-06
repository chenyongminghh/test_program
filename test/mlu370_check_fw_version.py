#!/usr/bin/env python3
import sys
import logging
import argparse
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')

sys.path.append(modules_path)
import UTP
import CAM

def main(args):
    case_name = 'mlu370 Check FW Version'
    logging.info('{}'.format(case_name), section=True)
    
    results = []
    mcPorts = CAM.detected_mlu370()
    for mcPort in range(mcPorts):
        mcPort = str(mcPort)
        mcSN = CAM.get_sn(mcPort)
        board_type = CAM.get_mlu370_type(mcPort)
        if mcSN.startswith('58'):
            board_type = '{}{}'.format(board_type, '_3U')
        mcu_version = CAM.get_mcu_ver(mcPort)
        expect_mcu_version = UTP.get('MCU_VERSION', '')[board_type].upper()
        if args.mcu:
            expect_mcu_version = args.mcu.strip().upper()
        mcu_flash_req = True if expect_mcu_version != mcu_version else False
        
        isse_m0_version, d2d_m0_version, ddr_m0_version = CAM.get_image_ver(mcPort)
        expect_isse_version = UTP.get('ISSE_VER', '')[board_type].upper()
        expect_d2d_version = UTP.get('D2D_VER', '')[board_type].upper()
        expect_ddr_version = UTP.get('DDR_VER', '')[board_type].upper()
        
        isse_flash_req = True if expect_isse_version != isse_m0_version else False
        d2d_flash_req = True if expect_d2d_version != d2d_m0_version else False
        ddr_flash_req = True if expect_ddr_version != ddr_m0_version else False
        
        results.append(['Card{} {}'.format(mcPort, mcSN), 'MCU Version', expect_mcu_version, mcu_version, mcu_flash_req])
        results.append(['Card{} {}'.format(mcPort, mcSN), 'ISSE Version', expect_isse_version, isse_m0_version, isse_flash_req])
        results.append(['Card{} {}'.format(mcPort, mcSN), 'D2D Version', expect_d2d_version, d2d_m0_version, d2d_flash_req])
        results.append(['Card{} {}'.format(mcPort, mcSN), 'DDR Version', expect_ddr_version, ddr_m0_version, ddr_flash_req])
                
    table_header = ['Slot', 'Firmware', 'Expected', 'Actual', 'Needs Flash']
    table_settings = {'header': table_header, 
                      'footer': False, 
                      'str_is_str': True
                     }
    logging.info(results, table=table_settings)
    
    result = 'PASS' if not any(each_result[-1] for each_result in results) else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
        raise Exception('Firmware validation failed! Review table for "Needs Flash" entries')
    return
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--mcu', action='store', help='please specify mcu version')
    args = parser.parse_args()
    sys.exit(main(args))
    
