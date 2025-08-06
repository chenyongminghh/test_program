#!/usr/bin/env python3

import os
import sys
import time
import logging
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
logs_path = osp.join(testcode_path, 'logs')

sys.path.append(modules_path)
import UTP
import CAM

def main():
    logging.info('Update variables', section=True)
    
    UTP.run(['cp', '{}'.format(osp.join(testcode_path, 'variables')), '{}/variables-{}'.format(logs_path, CAM.read_datetime())], log_stdout=logging.INFO)
    UTP.run(['cp', '-rf', '/spider_test/MLU370/mlu370_test/variables', '{}'.format(osp.join(testcode_path, 'variables'))], log_stdout=logging.INFO)
    
    return
    
if __name__ == '__main__':
    sys.exit(main())
