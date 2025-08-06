#!/usr/local/bin/python35
##@package AmI
import subprocess
import os.path as osp

# This is low-level module that should not rely on UTP functions because UTP will use this module

def on_type():
    return 'uut'
    if osp.exists('/proc/cmdline'):
        with open('/proc/cmdline') as fh:
            content = fh.read()
            if 'BLADE' in content:
                return 'l1'
            ## TODO replace with check for 'UUT' once we add it to boot config
            if ' UUT ' in content:
                return 'uut'

    if osp.exists('/etc/hosts'):
        with open('/etc/hosts') as fh:
            if 'l2linux' in fh.read().lower():
                return 'l1'

    ifconfig_output = ''
    if osp.exists('/sbin/ifconfig'):
        ifconfig_output = subprocess.check_output('/sbin/ifconfig').decode()
        if 'inet addr:10.240.48.114' in ifconfig_output:
            return 'central'

    ## TODO replace this with /dfcact/utp when we switch the mapping
    if osp.exists('/dfcxact/dless'):
        l2_list = subprocess.check_output('cut -d, -f2 /dfcxact/dless/ww_l1.csv | sort -u',shell=True).decode().splitlines()
        for l2 in l2_list:
            l2 = l2.strip()
            if l2.startswith('#'):
                break
            if l2 in ifconfig_output:
                return 'l2'
        

    return 'OTHER'

if __name__ == '__main__':
    print('type: {}'.format(on_type()))
