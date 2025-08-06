#!/usr/local/bin/python35
import sys
import logging
import uuid
import hashlib
import os
import getpass
from contextlib import suppress

from Default import *

logger = logging.getLogger(__name__)

UWIP_TO_VAR = {
    'ShipDate': 'shipdate',
    'Shipdate': 'shipdate',
    'MONUMBER': 'mo',
    'MFG_SONUMBER': 'so',
    'SONUMBER': 'so',
    'SOLINEITEM': 'soline',
    'MFG_SOLINEITEM': 'soline',
    'Customer_name': 'custname',
    'Orderable_part': 'seo',
    'Order_qty': 'orderqty',
    'Ship_to_country': 'shipcountry',
    'ZCUPO': 'zcupo',
    'CUSNO': 'cusno'
}

def get_site():
    with suppress(FileNotFoundError), open(UTP_SITE_FILE) as fh:
        return fh.read().strip()

def get_debug(user=None, path=None, production=None):
    cwd = os.getcwd()
    if production is None:
        # start_utp.py sill set UTP_PRODUCTION, otherwise we have to be running via runseqs in /rt*
        production = (os.environ.get(UTP_PRODUCTION, False) or os.environ.get(RUNSEQS_PID, False)) \
            and cwd.split(os.sep)[-1].startswith('rt')
    if path is None:
        path= os.getcwd()
    if user is None:
        user = getpass.getuser()
    return{'user': user, 'path': path, 'production': production}


def get_sn(vars=None, uwip=None):
    """ Get the SN for this process
    The order of look-up is $cwd/variables, environ[UTP_SN], ../uwip.xml file
    """
    if vars is None:
        # Default to a low-risk variable read that does not use locking at all
        from Variable import readvars
        with open('variables') as fh:
            vars = readvars(fh)
    if vars and 'SN' in vars:
        return vars['SN']
    if UTP_SN in os.environ:
        return os.environ[UTP_SN]
    return (uwip or read_uwip('../uwip.xml'))[0]


def get_subloc(vars=None):
    """ Get the SN for this process
    The order of look-up is $cwd/variables, environ[UTP_SN]
    Note that if neither are set, the return value will be '' (empty string)
    """
    if vars is None:
        # Once again, use low-risk variable read
        from Variable import readvars
        with open('variables') as fh:
            vars = readvars(fh)
    return vars.get(MTSN_SUBLOCATION, '') or os.environ.get(MTSN_SUBLOCATION, '')


def get_mo(vars=None, uwip=None):
    """ Get the SN for this process
    The order of look-up is $cwd/variables, environ[UTP_SN], ../uwip.xml file
    """
    if vars is None:
        # Default to a low-risk variable read that does not use locking at all
        from Variable import readvars
        with open('variables') as fh:
            vars = readvars(fh)
    if vars and 'MONUMBER' in vars:
        return vars['MONUMBER']
    if UTP_MONUMBER in os.environ:
        return os.environ[UTP_MONUMBER]
    return (uwip or read_uwip('../uwip.xml'))[4]['mo']
    

def read_uwip(fname):
    import xml.etree.ElementTree as ET
    with open(fname, 'rb') as fh:
        content = fh.read()
    root = ET.fromstring(content.decode(errors='backslashreplace'))
    ones_name = root.findtext('.//filename')
    assert ones_name.startswith('1S') and ones_name.endswith('.xml')
    mtmsn = ones_name[2:-4]
    one_s = ones_name[:-4]
    if len(mtmsn) == 18:
        mt = mtmsn[:4]
        model=  mtmsn[4:10]
        sn = mtmsn[10:]
    else:
        mt = mtmsn[:4]
        model = mtmsn[4:7]
        sn = mtmsn[7:]
    ones_data = {'one_s': one_s}
    order_text= root.findtext('.//orderdata')
    order_data = {}
    for line in order_text.splitlines(False):
        line = line.strip()
        if line:
            key, *value = line.split(maxsplit=1)
            if key not in UWIP_TO_VAR:
                logger.warn('Skipping uwip order field: ' + line)
                continue
            order_data[UWIP_TO_VAR[key]] = value[0] if value else None

    vars_text= root.findtext('.//vars')
    vars_data = {}
    for line in vars_text.splitlines(False):
        line = line.strip()
        if line:
            key, value = line.split('=', maxsplit=1)
            vars_data[key.strip().upper()] = value

    mackit_text = root.findtext('.//kitmacs')
    kits = {}
    mac_data = {}
    for line in mackit_text.splitlines(False):
        line = line.strip()
        if not line:
            continue
        if line.startswith('MACKIT'):
            kit, mac_info = line.split('=', 1)
            kits[kit] = mac_info.lower().replace('23s', '')
        else:
            zstuff, kit_keys = line.split('=', 1)
            mac_data[zstuff] = [kits[x] for x in kit_keys.split(';')]
    order_data.update(ones_data)
    order_data['vars'] = vars_data
    order_data['mackit'] = mac_data
    site = get_site()
    order_data['udid'] = str(uuid.UUID(hashlib.sha1(content).hexdigest()[:32]))
    order_data['orderqty'] = int(order_data['orderqty'])
    return sn, mt, model, site, order_data
