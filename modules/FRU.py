#!/usr/bin/python3.5
"""
# some fru functions.
"""

import re
import sys
import json
import logging
import os.path as osp
from contextlib import suppress

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
utilities_path = osp.join(testcode_path, 'utilities')
modules_path = osp.join(testcode_path, 'modules')

sys.path.append(modules_path)
import UTP
import IMM
import Devices

description_re = re.compile(r'(.*)\(ID (\d+)\)')

def create_fru_logs(imm_num):
    imm = IMM.IMM()
    fru_file = osp.join(testcode_path, 'fru.log')
    
    log = imm.get_fru_log(imm_num)
    with open(fru_file, mode='wb') as fh:
        fh.write(log)

def parse_fru_logs(imm_num):
    create_fru_logs(imm_num)
    fru_file = osp.join(testcode_path, 'fru.log')
    
    fru_lookup = Devices.FRULookup()
    
    with open(fru_file, mode='br') as fh:
        # Parse each structure into a record
        record = None
        
        for line in fh:
            line = line.decode(errors='replace').strip()
            if line.startswith('FRU Device Description'):
                if record is not None:
                    fru_lookup[record._location] = record
                    record = None
                
                label, description = line.split(':', 1)
                match = description_re.search(description)
                the_desc = match.group(1).strip()
                the_id = match.group(2)
                
                record = Devices.FRUDevice(id_=the_id)
                record._location = the_desc
                record._unkeyed_data = ''
            elif ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                if key in record:
                    if not isinstance(record[key], list):
                        record[key] = [record[key]]
                    record[key].append(value.strip())
                else:
                    record[key] = value.strip()
            elif not line:
                continue
            elif 'Device not present' in line:
                fru_lookup[record._location] = 'EMPTY'
                record = None
            elif 'Unsupported device' in line:
                fru_lookup[record._location] = 'UNSUPPORTED'
                record = None
            else:
                record._unkeyed_data += line
            
            # pick up last record
            if record is not None:
                fru_lookup[record._location] = record
    return fru_lookup

def get_fru_sn(fru_lookup, fru_location):
    fru_device = fru_lookup.get(fru_location)
    if fru_device == 'EMPTY':
        return ''
    
    fru_sn_value = fru_device.get('Product Serial')
    return fru_sn_value

def read_eeprom_sn(imm_num):
    imm = IMM.IMM()
    eeprom_sn_dict = {}
    
    eeprom_sn_dict['pdb_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0xa0 0x00', imm_num)
    eeprom_sn_dict['ibb_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0xc0 0x00', imm_num)
    eeprom_sn_dict['linkb_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0xb0 0x00', imm_num)
    
    eeprom_sn_dict['psu0_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0x00 0x03', imm_num)
    eeprom_sn_dict['psu1_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0x10 0x03', imm_num)
    
    eeprom_sn_dict['mc0_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0x00 0x02', imm_num)
    eeprom_sn_dict['mc1_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0x10 0x02', imm_num)
    eeprom_sn_dict['mc2_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0x20 0x02', imm_num)
    eeprom_sn_dict['mc3_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0x30 0x02', imm_num)
    
    eeprom_sn_dict['ib0_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0x40 0x03', imm_num)
    eeprom_sn_dict['ib1_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0x60 0x03', imm_num)
    
    eeprom_sn_dict['hd0_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0xc0 0x03', imm_num)
    eeprom_sn_dict['hd1_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0xd8 0x03', imm_num)
    eeprom_sn_dict['hd2_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0xf0 0x03', imm_num)
    eeprom_sn_dict['hd3_sn'] = imm.read_eeprom_sn('raw 0x3a 0x88 0x08 0x04', imm_num)
    
    for key in eeprom_sn_dict:
        if eeprom_sn_dict[key] == '':
            eeprom_sn_dict[key] = 'EMPTY'
    return eeprom_sn_dict

def get_expect_vpd(imm_num):
    imm = IMM.IMM()
    ba_sn = imm.read_board_sn(imm_num)
    assert len(ba_sn) == 12, 'Board SN <> format error.'.format(ba_sn)
    
    mfg_data_file = osp.join(utilities_path, 'mfgdata/{}.txt'.format(ba_sn))
    assert osp.exists(mfg_data_file), '{} not exists, please check.'.format(mfg_data_file)
    
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
    for key in product_dict:
        if product_dict[key] == '':
            product_dict[key] = 'EMPTY'
    
    return product_dict

def get_fru_value(fru_lookup, fru_location, fru_key):
    fru_device = fru_lookup.get(fru_location)
    if fru_device == 'EMPTY':
        return 'EMPTY'
    fru_value = fru_device.get(fru_key)
    return fru_value