#!/usr/bin/env python3

import re
import os
import sys
import time
import logging
import argparse
import subprocess
import os.path as osp
import multiprocessing as mp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
utilities_path = osp.join(testcode_path, 'utilities')
logs_path = osp.join(testcode_path, 'logs')
sys.path.append(modules_path)
import UTP
import CAM

def get_nvme_list():
    nvme_list = []
    proc = UTP.runproc_rt('ls /dev/nvme*n*', shell=True, stderr=subprocess.STDOUT, check=False)
    return_context = proc.stdout.decode('utf-8').strip()
    nvme_list = return_context.split('\n')
    return nvme_list

def mt_run_nvme_test(nvme_list, rwType, blockSize, iodepth, volumeSize, runtime, workers, limitBW='', limitIOPS=''):
    logging.info('TestType:{} BlockSize:{} RunTime:{} numjobs:{} iodepth:{}'.format(rwType, blockSize, runtime, workers, iodepth))
    p_lst = []
    q = mp.Queue()
    for nvme in nvme_list:
        p = mp.Process(target=fio_test, args=(q, nvme, rwType, blockSize, iodepth, volumeSize, runtime, workers, limitBW, limitIOPS))
        p.start()
        p_lst.append(p)
    [ p.join() for p in p_lst]
    
    allPassed = True
    for nvme in nvme_list:
        res_result = q.get()
        if not res_result:
            allPassed = False
    return allPassed

def st_run_nvme_test(nvme_list, rwType, blockSize, iodepth, volumeSize, runtime, workers, limitBW='', limitIOPS=''):
    logging.info('TestType:{} BlockSize:{} RunTime:{} numjobs:{} iodepth:{}'.format(rwType, blockSize, runtime, workers, iodepth))
    q = mp.Queue()
    allPassed = True
    for nvme in nvme_list:
        p = mp.Process(target=fio_test, args=(q, nvme, rwType, blockSize, iodepth, volumeSize, runtime, workers, limitBW, limitIOPS))
        p.start()
        p.join()
        res_result = q.get()
        if not res_result:
            allPassed = False
    return allPassed

def fio_test(q, devName, rwType, blockSize, iodepth, volumeSize, runtime, workers, limitBW='', limitIOPS=''):
    fio_cmd = './fio -filename={} -rw={} --bs={} -iodepth={} '.format(devName, rwType, blockSize, iodepth)
    fio_cmd = fio_cmd + '-size={} -numjobs={} '.format(volumeSize, workers)
    if runtime and rwType not in ['write']:
        fio_cmd = fio_cmd + '-runtime={} '.format(runtime)
    fio_cmd = fio_cmd + '-ioengine=libaio -thread -direct=1 --buffered=0 -group_reporting -name=mytest '
    
    log_fname = osp.join(logs_path, '{}.log'.format(devName.split('/')[-1]))
    with open(log_fname, mode='a') as test_log:
        test_log.write('###{} Test Start on {}\n'.format(devName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
        test_log.write('TEST_CMD={}\n'.format(fio_cmd))
        test_log.flush()
        os.fsync(test_log.fileno())
    proc = UTP.runproc_rt(fio_cmd, log_stdout=log_fname, stderr=subprocess.STDOUT, shell=True, cwd=utilities_path)
    with open(log_fname, mode='a') as test_log:
        test_log.write('\n')
        test_log.write('TEST_RTN={}\n'.format(proc.returncode))
        test_log.write('###{} Test End on {}\n\n'.format(devName, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime())))
    if proc.returncode:
        logging.error('{} run <fio> command Failed with returncode {}'.format(devName, proc.returncode))
        return q.put(False)
    
    if rwType in ['read', 'randread']:
        start_string = 'read:'
    elif rwType in ['write', 'randwrite']:
        start_string = 'write:'
    else:
        logging.info('{} rwType {} not support'.format(devName, rwType))
        return q.put(False)
        
    iops = ''
    bw = ''
    return_context = proc.stdout.decode('utf-8').strip()
    for line in return_context.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith(start_string):
            match = re.match(".*(IOPS=)(.*)(k).*(BW=)(\d+)(MiB/s)\s\((.*)(MB/s)\).*", line)
            if match:
                iops = match.group(2)
                bw = match.group(7)
                break
                
    if limitBW:
        if int(bw) < int(limitBW):
            logging.error('{} IOPS={}k, BW={}MB/s Check Failed, expect {}MB/s'.format(devName, iops, bw, limitBW))
            return q.put(False)
        else:
            logging.info('{} IOPS={}k, BW={}MB/s, expect {}MB/s'.format(devName, iops, bw, limitBW))
            return q.put(True)
    elif limitIOPS:
        if int(iops) < int(limitIOPS):
            logging.error('{} IOPS={}k, BW={}MB/s Check Failed, expect {}k'.format(devName, iops, bw, limitIOPS))
            return q.put(False)
        else:
            logging.info('{} IOPS={}k, BW={}MB/s, expect {}k'.format(devName, iops, bw, limitIOPS))
            return q.put(True)
    else:
        logging.info('{} IOPS={}k, BW={}MB/s'.format(devName, iops, bw))
        return q.put(True)
    

def main(args):
    case_name = 'mlu370 DVT NVME Test'
    logging.info(case_name, section=True)
    
    nvmeTypeList = []
    contextA = UTP.run('lspci -d 1e3b:1098', shell=True, stderr=subprocess.STDOUT, check=False).strip()
    if contextA and len(contextA.split('\n')) > 0:
        nvmeTypeList.append('DapuStor')
    contextB = UTP.run('lspci -d 1d78:1512', shell=True, stderr=subprocess.STDOUT, check=False).strip()
    if contextB and len(contextB.split('\n')) > 0:
        nvmeTypeList.append('DERA')
    nvmeType = '-'.join(nvmeTypeList)
    logging.info('NVME Type: {}'.format(nvmeType))
    if nvmeType not in ['DapuStor', 'DERA']:
        logging.info('Not support NVME Type Failed')
        CAM.record_fail_case(case_name)
        raise Exception('Not support NVME Type FAILED')
    
    nvme_list = get_nvme_list()
    if len(nvme_list) != 4:
        logging.info('NVME Qty Check Failed')
        CAM.record_fail_case(case_name)
        raise Exception('NVME Qty Check FAILED')
    logging.info('NVME Devices:{}'.format(nvme_list))
    
    volumeSize = '100%'
    rwType = args.mode.strip() if args.mode in ['read', 'write', 'randread', 'randwrite'] else 'read'
    runtime = args.time.strip() if args.time else ''
    if nvmeType == 'DapuStor':
        workers =   {'read':'1',    'write':'1',    'randread':'4',   'randwrite':'4'  }.get(rwType)
        iodepth =   {'read':'256',  'write':'256',  'randread':'64',  'randwrite':'64' }.get(rwType)
        blockSize = {'read':'128k', 'write':'128k', 'randread':'4k',  'randwrite':'4k' }.get(rwType)
        limitBW =   {'read':'3100', 'write':'2400', 'randread':'',    'randwrite':''   }.get(rwType)
        limitIOPS = {'read':'',     'write':'',     'randread':'730', 'randwrite':'100'}.get(rwType)
    elif nvmeType == 'DERA':
        workers =   {'read':'1',    'write':'1',    'randread':'4',   'randwrite':'4'  }.get(rwType)
        iodepth =   {'read':'64',   'write':'64',   'randread':'64',  'randwrite':'64' }.get(rwType)
        blockSize = {'read':'128k', 'write':'128k', 'randread':'4k',  'randwrite':'4k' }.get(rwType)
        limitBW =   {'read':'3100', 'write':'1800', 'randread':'',    'randwrite':''   }.get(rwType)
        limitIOPS = {'read':'',     'write':'',     'randread':'675', 'randwrite':'140'}.get(rwType)
    
    loops = int(args.loops.strip()) if args.loops else 1
    
    result = 'PASS'
    for loop in range(loops):
        if int(loops) > 1:
            logging.info('Test Loop:{}'.format(loop+1))
        if rwType in ['write', 'randread', 'randwrite']:
            nvme_res = st_run_nvme_test(nvme_list, rwType, blockSize, iodepth, volumeSize, runtime, workers, limitBW=limitBW, limitIOPS=limitIOPS)
        else:
            nvme_res = mt_run_nvme_test(nvme_list, rwType, blockSize, iodepth, volumeSize, runtime, workers, limitBW=limitBW, limitIOPS=limitIOPS)
        if not nvme_res:
            result = 'FAIL'
            break
            
    nvme_list = get_nvme_list()
    logging.info('NVME Devices:{}'.format(nvme_list))
        
    if result == 'PASS':
        logging.info('{} PASSED'.format(case_name))
    elif UTP.get('FAIL_IGNORE', None):
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
    else:
        logging.info('{} FAILED'.format(case_name))
        CAM.record_fail_case(case_name)
        raise Exception('There are some card boot failed.')
    return
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', action='store', help='read, write, randread, randwrite')
    parser.add_argument('--time', action='store', help='stress test time')
    parser.add_argument('--loops', action='store', help='loops')
    args = parser.parse_args()
    sys.exit(main(args))
    