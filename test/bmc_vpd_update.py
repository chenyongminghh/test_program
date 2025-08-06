#!/usr/bin/env python3

import sys
import json
import logging
import time
import os.path as osp
from contextlib import suppress

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
utilities_path = osp.join(testcode_path, 'utilities')
modules_path = osp.join(testcode_path, 'modules')

sys.path.append(modules_path)
import UTP
import IMM
import FRU
import CAM

def get_fru_sn(fru_lookup, fru_location):
    fru_device = fru_lookup.get(fru_location)
    if fru_device == 'EMPTY':
        return 'EMPTY'
    
    fru_sn_value = fru_device.get('Product Serial')
    return fru_sn_value
    
def main():
    case_name = 'BMC VPD Update'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    all_passed = True
    for imm_num in range(imm_qty):
        logging.info('BMC<{}> Starting VPD Info Update'.format(imm_num))
        don_flag = 'vpd_flashed_don_bmc{}'.format(imm_num)
        ba_sn = imm.read_board_sn(imm_num)
        assert len(ba_sn) == 12, 'Board SN <> format error.'.format(ba_sn)
        
        mfg_data_file = osp.join(utilities_path, 'mfgdata/{}.txt'.format(ba_sn))
        if not osp.exists(mfg_data_file):
            logging.error('{} not exists, please check.'.format(mfg_data_file))
            all_passed = False
            continue
        
        product_dict = {}
        with open(mfg_data_file, 'r') as fh:
            fh.seek(0)
            for line in fh:
                line = line.strip()
                if line == '' or line.startswith('#'):
                    continue
                with suppress(ValueError, json.decoder.JSONDecodeError):
                    name, value = line.split('=', 1)
                    product_dict[name.strip()] =  json.loads(value.strip())
                    continue
                break
        
        board_sn = product_dict['BA_SN']
        board_mac = product_dict['BA_MAC']
        
        product_sn = product_dict['PRODUCT_SN']
        # product_pn = 'FS290013'
        # product_model = 'MLU-X1001'
        
        product_pn = product_dict['PRODUCT_PN']
        product_model = product_dict['PRODUCT_MODEL']
        
        pdb_sn = product_dict['PDB_SN']
        ibb_sn = product_dict['IBB_SN']
        linkb_sn = product_dict['LINKB_SN']
        hdb0_sn = product_dict.get('HDB0_SN')
        hdb1_sn = product_dict['HDB1_SN']
        
        logging.info('{}: {}'.format('Board SN'.ljust(22, ' '), board_sn))
        logging.info('{}: {}'.format('Board MAC'.ljust(22, ' '), board_mac))
        logging.info('{}: {}'.format('Product SN'.ljust(22, ' '), product_sn))
        logging.info('{}: {}'.format('Product PN'.ljust(22, ' '), product_pn))
        logging.info('{}: {}'.format('Product Name'.ljust(22, ' '), product_model))
        
        logging.info('{}: {}'.format('Product PDB SN'.ljust(22, ' '), pdb_sn))
        logging.info('{}: {}'.format('Product IBB SN'.ljust(22, ' '), ibb_sn))
        logging.info('{}: {}'.format('Product LINKB SN'.ljust(22, ' '), linkb_sn))
        logging.info('{}: {}'.format('Product HDB0 SN'.ljust(22, ' '), hdb0_sn))
        logging.info('{}: {}'.format('Product HDB1 PN'.ljust(22, ' '), hdb1_sn))
        
        fru_lookup = FRU.parse_fru_logs(imm_num)
        
        psu0_sn = get_fru_sn(fru_lookup, 'PSU0')
        psu1_sn = get_fru_sn(fru_lookup, 'PSU1')
        logging.info('{}: {}'.format('PSU0 SN'.ljust(22, ' '), psu0_sn))
        logging.info('{}: {}'.format('PSU1 SN'.ljust(22, ' '), psu1_sn))
        
        mc0_sn = get_fru_sn(fru_lookup, 'MezzCard0')
        mc1_sn = get_fru_sn(fru_lookup, 'MezzCard1')
        mc2_sn = get_fru_sn(fru_lookup, 'MezzCard2')
        mc3_sn = get_fru_sn(fru_lookup, 'MezzCard3')
        logging.info('{}: {}'.format('MezzCard0 SN'.ljust(22, ' '), mc0_sn))
        logging.info('{}: {}'.format('MezzCard1 SN'.ljust(22, ' '), mc1_sn))
        logging.info('{}: {}'.format('MezzCard2 SN'.ljust(22, ' '), mc2_sn))
        logging.info('{}: {}'.format('MezzCard3 SN'.ljust(22, ' '), mc3_sn))
        
        ib0_sn = get_fru_sn(fru_lookup, 'IB0')
        ib1_sn = get_fru_sn(fru_lookup, 'IB1')
        logging.info('{}: {}'.format('IB0 SN'.ljust(22, ' '), ib0_sn))
        logging.info('{}: {}'.format('IB1 SN'.ljust(22, ' '), ib1_sn))
        
        hd0_sn = get_fru_sn(fru_lookup, 'HD0')
        hd1_sn = get_fru_sn(fru_lookup, 'HD1')
        hd2_sn = get_fru_sn(fru_lookup, 'HD2')
        hd3_sn = get_fru_sn(fru_lookup, 'HD3')
        logging.info('{}: {}'.format('HDD0 SN'.ljust(22, ' '), hd0_sn))
        logging.info('{}: {}'.format('HDD1 SN'.ljust(22, ' '), hd1_sn))
        logging.info('{}: {}'.format('HDD2 SN'.ljust(22, ' '), hd2_sn))
        logging.info('{}: {}'.format('HDD3 SN'.ljust(22, ' '), hd3_sn))
        
        if UTP.get(don_flag, None):
            logging.info('{}: {} exists, skip flash sn to eeprom'.format('*'*22, don_flag))
        else:
            logging.info('{}: Starting flash sn to eeprom'.format('*'*22))
            imm.enable_vpd_write(imm_num)
            imm.write_product_sn(product_sn, imm_num)
            imm.write_product_pn(product_pn, imm_num)
            imm.write_product_model(product_model, imm_num)
            imm.write_board_product_name('MLUX-BB1', imm_num)
            
            imm.write_eeprom('PDB SN', 'raw 0x3a 0x89 0xa0 0x00', pdb_sn, imm_num)
            imm.write_eeprom('IBB SN', 'raw 0x3a 0x89 0xc0 0x00', ibb_sn, imm_num)
            imm.write_eeprom('LINKB SN', 'raw 0x3a 0x89 0xb0 0x00', linkb_sn, imm_num)
            
            imm.write_eeprom_extra('PSU0 SN', 'raw 0x3a 0x89 0xff 0xff 0x01 0x00', psu0_sn, imm_num)
            imm.write_eeprom_extra('PSU1 SN', 'raw 0x3a 0x89 0xff 0xff 0x01 0x01', psu1_sn, imm_num)
            
            imm.write_eeprom_extra('MezzCard0 SN', 'raw 0x3a 0x89 0xff 0xff 0x02 0x00', mc0_sn, imm_num)
            imm.write_eeprom_extra('MezzCard1 SN', 'raw 0x3a 0x89 0xff 0xff 0x02 0x01', mc1_sn, imm_num)
            imm.write_eeprom_extra('MezzCard2 SN', 'raw 0x3a 0x89 0xff 0xff 0x02 0x02', mc2_sn, imm_num)
            imm.write_eeprom_extra('MezzCard3 SN', 'raw 0x3a 0x89 0xff 0xff 0x02 0x03', mc3_sn, imm_num)
            
            time.sleep(1)
            imm.write_eeprom_extra('IB0 SN', 'raw 0x3a 0x89 0xff 0xff 0x03 0x00', ib0_sn, imm_num)
            time.sleep(1)
            imm.write_eeprom_extra('IB1 SN', 'raw 0x3a 0x89 0xff 0xff 0x03 0x01', ib1_sn, imm_num)
            time.sleep(1)
            
            # imm.write_eeprom_extra('HDD0 SN', 'raw 0x3a 0x89 0xff 0xff 0x04 0x00', hd0_sn, imm_num)
            # imm.write_eeprom_extra('HDD1 SN', 'raw 0x3a 0x89 0xff 0xff 0x04 0x01', hd1_sn, imm_num)
            # imm.write_eeprom_extra('HDD2 SN', 'raw 0x3a 0x89 0xff 0xff 0x04 0x02', hd2_sn, imm_num)
            # imm.write_eeprom_extra('HDD3 SN', 'raw 0x3a 0x89 0xff 0xff 0x04 0x03', hd3_sn, imm_num)
            imm.write_eeprom('HDD0 SN', 'raw 0x3a 0x89 0xc0 0x03', hd0_sn, imm_num)
            imm.write_eeprom('HDD1 SN', 'raw 0x3a 0x89 0xd8 0x03', hd1_sn, imm_num)
            imm.write_eeprom('HDD2 SN', 'raw 0x3a 0x89 0xf0 0x03', hd2_sn, imm_num)
            imm.write_eeprom('HDD3 SN', 'raw 0x3a 0x89 0x08 0x04', hd3_sn, imm_num)
            UTP.set(don_flag, True)
            logging.info('BMC<{}> VPD Info Update PASSED.'.format(imm_num))
    
    result = 'PASS' if all_passed else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        CAM.record_fail_case(case_name)
        raise Exception('Some failure detected, please check the log.')


if __name__ == '__main__':
    sys.exit(main())
