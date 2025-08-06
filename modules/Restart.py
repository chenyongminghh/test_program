#!/usr/bin/env python3

import logging
import time
import os

import UTP

logger = logging.getLogger(__name__)

def need_reboot(reason):
    value = UTP.get('reboot_required', [], scope='local')
    if reason not in value:
        value.append(reason)
        UTP.set('reboot_required', value, scope='local')

def need_imm_dccycle(reason):
    value = UTP.get('imm_dccycle_required', [], scope='local')
    if reason not in value:
        value.append(reason)
        UTP.set('imm_dccycle_required', value, scope='local')

def need_powercycle(reason):
    value = UTP.get('powercycle_required', [], scope='local')
    if reason not in value:
        value.append(reason)
        UTP.set('powercycle_required', value, scope='local')

def reboot_uut():
    with UTP.increment('reboot_count'):
        sys_hang = UTP.get('system_hang', None)
        if sys_hang:
            logger.info('Cleaning up system_hang ({})'.format(sys_hang))
        UTP.set('system_hang', 'Test Hang Flag')
        with UTP.set('system_hang', False, rollback=True):
            UTP.run('sync; sync; sleep 3', shell=True)
            UTP.delete('reboot_required', scope='local')
            UTP.run(['reboot', '-f'])
