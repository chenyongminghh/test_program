#!/usr/bin/env python3
"""!Test case to check the SDR list status. 
    ok means the sensor is present and operating correctly. 
    ns means no sensor (corresponding reading will say disabled or Not Readable)
    nc means non-critical error regarding the sensor
    cr means critical error regarding the sensor
    nr means non-recoverable error regarding the sensor
"""
import sys
import logging
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import IMM
import UTP
import CAM

def main():
    case_name = 'BMC SDR List Test'
    logging.info('{}'.format(case_name), section=True)
    
    imm = IMM.IMM()
    imm_qty = imm.detect_IMMs()
    
    all_passed = True
    for imm_num in range(imm_qty):
        logging.info('BMC <{}> SDR Test'.format(imm_num))
        sdr_list = imm.get_sdr_list(imm_num)
        logging.debug("sdr list is {}".format(sdr_list))
        sdr_log_path = osp.join(logs_path, 'sdr{}.log'.format(imm_num))
        with open(sdr_log_path, mode='w') as sdr_log:
            sdr_log.write(sdr_list)
        
        isFailed = 0
        for line in sdr_list.splitlines():
            status = line.split("|", 3)[2].strip()
            if status not in ('ok', 'ns'):
                logging.info('Abnormal SDR record --> {}'.format(line))
                isFailed = 1
        if isFailed:
            all_passed = False
            logging.error("Please confirm which status is not in ok/ns and check the related the hardware!")
            logging.error('BMC <{}> SDR Test Failed'.format(imm_num))
        else:
            logging.info('BMC <{}> SDR Test Passed'.format(imm_num))
    
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
