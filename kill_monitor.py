#!/usr/bin/env python3

import os
import sys
import signal
import logging
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')

sys.path.append(modules_path)
import UTP

def killPID(process_name):
    output=UTP.run("ps -ef | grep {} | grep -v grep".format(process_name), shell=True, check=False) 
    for line in output.splitlines():
        pid = line.split()[1].strip()
        logging.info('{} --> {}'.format(line, pid))
        try:
            rec = os.kill(int(pid), signal.SIGKILL)
            logging.info('PID: {} has been killed.'.format(pid))
        except OSError:
            logging.info('PID: {} not exists now'.format(pid))

def main():
    logging.info('Kill the monitor.sh or bmc_sensor related process', section=True)
    killPID('./cnmon.sh')
    killPID('./monitor.sh')
    killPID('./monitor-dmesg.sh')
    killPID('bmc_sensor_monitor.py')
    
if __name__ == '__main__':
    sys.exit(main())

