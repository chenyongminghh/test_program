#!/usr/bin/python3.5
"""
Perform system restart actions
"""
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
    output=UTP.run("ps -ef | grep '{}' | grep -v grep".format(process_name), shell=True, check=False) 
    for line in output.splitlines():
        pid = line.split()[1].strip()
        #logging.info('{} --> {}'.format(line, pid))
        try:
            rec = os.kill(int(pid), signal.SIGKILL)
            logging.info('PID: {} has been killed.'.format(pid))
        except OSError:
            logging.info('PID: {} not exists now'.format(pid))

def main():
    logging.info('Kill the Gnome-Terminal related process', section=True)
    killPID('minicom -D /dev/tty')
    
if __name__ == '__main__':
    sys.exit(main())

