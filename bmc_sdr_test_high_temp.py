#!/usr/bin/python3.5
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
sttools_path = osp.join(testcode_path, 'sttools')
sys.path.append(modules_path)

Ignore_List = ["MC0_Inlet_Temp", "MC0_Outlet_Temp", "MC1_Inlet_Temp", "MC1_Outlet_Temp", "MC2_Inlet_Temp", "MC2_Outlet_Temp", "MC3_Inlet_Temp", "MC3_Outlet_Temp", "MC0_Temp", "MC1_Temp", "MC2_Temp", "MC3_Temp"]

import IMM

def main():
    imm = IMM.IMM()
    logging.info('Test SDR List', section=True)
    sdr_list = imm.get_sdr_list()
    logging.debug("sdr list is {}".format(sdr_list))
    with open('sdr.log', mode='w') as sdr_log:
        sdr_log.write(sdr_list)
    
    isFailed = 0
    for line in sdr_list.splitlines():
        isCheck = 0
        for ignore_i in Ignore_List:
            if line.startswith(ignore_i):
                isCheck = 1
                continue
        status = line.split("|", 3)[2].strip()
        if status not in ('ok', 'ns') and isCheck == 0:
            logging.info('Abnormal SDR record --> {}'.format(line))
            isFailed = 1
    if isFailed:
        raise Exception("The status in Sdr list is not ok, please confirm which status is not in ok/ns and check the related the hardware!")
    logging.info("Success! Sdr list status is OK")

if __name__ == '__main__':
    sys.exit(main())
