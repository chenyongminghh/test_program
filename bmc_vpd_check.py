#!/usr/bin/env python3

import sys
import time
import logging
import datetime
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
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
    case_name = 'BMC VPD Check'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    all_passed = True
    for imm_num in range(imm_qty):
        logging.info('BMC<{}> Starting VPD Info Check.'.format(imm_num))
        product_dict = FRU.get_expect_vpd(imm_num)
        
        expect_board_sn = product_dict['BA_SN']
        expect_board_mac = product_dict['BA_MAC'].lower()
        
        expect_product_sn = product_dict['PRODUCT_SN']
        # expect_product_pn = 'FS290013'
        # expect_product_model = 'MLU-X1001'
        
        expect_product_pn = product_dict['PRODUCT_PN']
        expect_product_model = product_dict['PRODUCT_MODEL']
        
        expect_pdb_sn = product_dict['PDB_SN']
        expect_ibb_sn = product_dict['IBB_SN']
        expect_linkb_sn = product_dict['LINKB_SN']
        expect_hdb0_sn = product_dict.get('HDB0_SN')
        expect_hdb1_sn = product_dict['HDB1_SN']
        
        fru_lookup = FRU.parse_fru_logs(imm_num)
        expect_psu0_sn = get_fru_sn(fru_lookup, 'PSU0')
        expect_psu1_sn = get_fru_sn(fru_lookup, 'PSU1')
        
        expect_mc0_sn = get_fru_sn(fru_lookup, 'MezzCard0')
        expect_mc1_sn = get_fru_sn(fru_lookup, 'MezzCard1')
        expect_mc2_sn = get_fru_sn(fru_lookup, 'MezzCard2')
        expect_mc3_sn = get_fru_sn(fru_lookup, 'MezzCard3')
        
        expect_ib0_sn = get_fru_sn(fru_lookup, 'IB0')
        expect_ib1_sn = get_fru_sn(fru_lookup, 'IB1')
        
        expect_hd0_sn = get_fru_sn(fru_lookup, 'HD0')
        expect_hd1_sn = get_fru_sn(fru_lookup, 'HD1')
        expect_hd2_sn = get_fru_sn(fru_lookup, 'HD2')
        expect_hd3_sn = get_fru_sn(fru_lookup, 'HD3')
        
        actual_board_sn = imm.read_board_sn(imm_num)
        actual_board_mac = imm.read_bmc_mac(imm_num)
        actual_product_sn = imm.read_product_sn(imm_num)
        actual_product_pn = imm.read_product_pn(imm_num)
        actual_product_model = imm.read_product_model(imm_num)
        actual_board_mfg_date = imm.read_board_mfg_date(imm_num)
        
        actual_dict = FRU.read_eeprom_sn(imm_num)
        actual_pdb_sn = actual_dict['pdb_sn']
        actual_ibb_sn = actual_dict['ibb_sn']
        actual_linkb_sn = actual_dict['linkb_sn']
        
        actual_psu0_sn = actual_dict['psu0_sn']
        actual_psu1_sn = actual_dict['psu1_sn']
        actual_mc0_sn = actual_dict['mc0_sn']
        actual_mc1_sn = actual_dict['mc1_sn']
        actual_mc2_sn = actual_dict['mc2_sn']
        actual_mc3_sn = actual_dict['mc3_sn']
        actual_ib0_sn = actual_dict['ib0_sn']
        actual_ib1_sn = actual_dict['ib1_sn']
        actual_hd0_sn = actual_dict['hd0_sn']
        actual_hd1_sn = actual_dict['hd1_sn']
        actual_hd2_sn = actual_dict['hd2_sn']
        actual_hd3_sn = actual_dict['hd3_sn']
    
        attributes_to_test = [
            ['Board SN', expect_board_sn, actual_board_sn],
            ['Board MAC', expect_board_mac, actual_board_mac],
            ['Product SN', expect_product_sn, actual_product_sn],
            ['Product PN', expect_product_pn, actual_product_pn],
            ['Product Model', expect_product_model, actual_product_model],
            ['PDB SN', expect_pdb_sn, actual_pdb_sn],
            ['IBB SN', expect_ibb_sn, actual_ibb_sn],
            ['LINKB SN', expect_linkb_sn, actual_linkb_sn],
            ['PSU0 SN', expect_psu0_sn, actual_psu0_sn],
            ['PSU1 SN', expect_psu1_sn, actual_psu1_sn],
            ['MezzCard0 SN', expect_mc0_sn, actual_mc0_sn],
            ['MezzCard1 SN', expect_mc1_sn, actual_mc1_sn],
            ['MezzCard2 SN', expect_mc2_sn, actual_mc2_sn],
            ['MezzCard3 SN', expect_mc3_sn, actual_mc3_sn],
            ['IB0 SN', expect_ib0_sn, actual_ib0_sn],
            ['IB1 SN', expect_ib1_sn, actual_ib1_sn],
            ['HDD0 SN', expect_hd0_sn, actual_hd0_sn],
            ['HDD1 SN', expect_hd1_sn, actual_hd1_sn],
            ['HDD2 SN', expect_hd2_sn, actual_hd2_sn],
            ['HDD3 SN', expect_hd3_sn, actual_hd3_sn],
        ]

        test_results = []
        for attribute in attributes_to_test:
            name, expected_value, actual_value = attribute
            fail = expected_value != actual_value
            test_results.append((name, expected_value, actual_value, '*FAIL*' if fail else ''))
        
        if any('FAIL' in res[-1] for res in test_results):
            logging_func = logging.error
        else:
            logging_func = logging.info
        
        logging_func(test_results, table={'header': ['Name', 'Expected', 'Actual', 'Fail?'], 'name': 'BMC VPD Test', 'str_is_str': True, 'footer': False})
        if logging_func == logging.error:
            all_passed = False
            logging.error('BMC<{}> VPD Check Failed'.format(imm_num))
        else:
            logging.info('BMC<{}> VPD Check Passed'.format(imm_num))
    
    result = 'PASS' if all_passed else 'FAIL'
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        CAM.record_fail_case(case_name)
        raise Exception('Some failure detected, please check the log.')
    
    return
    

if __name__ == '__main__':
    sys.exit(main())
