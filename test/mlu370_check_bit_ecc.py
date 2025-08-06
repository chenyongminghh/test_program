#!/usr/bin/env python3
"""
Perform system restart actions
"""
import sys
import logging
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import CAM

def check_bit_ecc(caseName, log_path):
    allPassed = True
    rtn = UTP.run('cat {} |grep "bit ecc"'.format(log_path), shell=True, check=False)
    if not rtn:
        logging.info('There is no bit ecc in kern.log')
    else:
        mcPorts = CAM.detected_mlu370()
        for mcPort in range(mcPorts):
            mcPort = str(mcPort)
            mcSN = CAM.get_sn(mcPort)
            for line in rtn.split('\n'):
                if '[Card{}]'.format(mcPort) in line:
                    allPassed = False
                    logging.info(line)
                    failure_message = '{} Failed on Card{}'.format(caseName, mcPort)
                    CAM.record_card_fail(mcPort, mcSN, caseName, failure_message)
    return allPassed

def main():
    case_name = 'mlu370 dmesg Bit Ecc Check'
    logging.info('{}'.format(case_name), section=True)
   
    dmesg_log_path = osp.join(logs_path, 'dmesg.log')
    UTP.run('dmesg | tee {}'.format(dmesg_log_path), shell=True, check=False)
    
    if not osp.exists(dmesg_log_path):
        logging.error('Create dmesg.log Failed')
        raise Exception('Some failure detected, please check the log.')
    
    result = 'PASS' if check_bit_ecc(case_name, dmesg_log_path) else 'FAIL'
    if result == 'PASS':
        logging.info('{} successfully'.format(case_name))
    elif UTP.get('MFG_FAIL_MODE', None):
        logging.error('{} FAILED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
    else:
        logging.info('{} FAILED'.format(case_name))
        raise Exception('Some failure detected, please check the log.')
    
    
if __name__ == '__main__':
    sys.exit(main())

