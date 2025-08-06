## @package Misc
# This module provides helpful functions
#
import collections
import os
import os.path as osp
import shutil
import logging
import subprocess
import re
import tempfile
import time
import hashlib
import datetime
import getpass
import traceback
import uuid
from subprocess import PIPE
from contextlib import suppress
from math import ceil

import MediaTools
from Default import *
from UWIP import get_site

import Fails  # this will import all Fail classes and ItemType into builtins namespace

logger = logging.getLogger(__name__)

RE_COMPILED = re.compile('').__class__


def md5sum(string):
    return hashlib.md5(string.encode()).hexdigest()

def get_geo_ip():
    with suppress(FileNotFoundError), open(UTP_GEO_IP_FILE) as fh:
        return fh.read().strip()

class NotUTPEnabled(RuntimeFail):
    def __init__(self, msg, **kwargs):
        super().__init__(ItemType.other, msg, **kwargs)

class FIXME(Exception): pass


class FIXME_BY:
    """! Use with 'with' statement to execute a block of code until a date in the future
    If the FIXME has not been removed by the given date, a grace period of N days (default 5)
    will be given, where a warning will be logged and an artificial sleep will get
    progressively longer in an attempt to highlight the warning.  After the grace period
    expires, an exception will be thrown.  Example:
    @code
    with FIXME_BY(2017, 4, 1, warning='Still returning "OKAY" when we should be failing'):
       return 'OKAY'

     raise Exception('There is something wrong with the order')
    """
    def __init__(self, year, month, day, hour=0, minute=0, second=0,
                 grace=5,
                 warning='Contact TE, this code should have been removed by now!'):
        self.warn_datetime = datetime.datetime(year, month, day, hour, minute, second)
        self.fail_datetime = self.warn_datetime + (grace if isinstance(grace, datetime.timedelta)
                                                   else datetime.timedelta(days=grace))
        self.warning = warning

    def __enter__(self):
#        if datetime.datetime.now() > self.fail_datetime:
#            raise FIXME('Temporary code has expired and needs to be removed.  Contact a TE with this error')
        if datetime.datetime.now() > self.warn_datetime:
            import inspect
            logger.warning(self.warning)
            frame = inspect.stack()[1][0]
            logger.warning('file={}, line={}'.format(frame.f_code.co_filename, frame.f_lineno))
            logger.warning('Grace period will expire @ {}'.format(self.fail_datetime))
            # Sleep 20 sec so hopefully someone will see warning
            time.sleep(20)
        return self

    def __exit__(self, exc_type, exc_value, tb):
        return False


class InDir:
    """! Use with a 'with' statement to change directories

    Change to directory in a 'with' statement and return to the starting
    directory on exiting the 'with' block

    @b Usage
    @code
    with InDir('/var/tmp'):
        do_some_stuff()
    @endcode
    """

    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self.oldname = os.getcwd()
        os.chdir(self.name)
        return self.name

    def __exit__(self, etype, evalue, tb):
        os.chdir(self.oldname)
        return False


class InTmpDir:
    def __init__(self, parent_dir="/tmp"):
        self.parent_dir = parent_dir

    def __enter__(self):
        if (not osp.exists(self.parent_dir)):
            os.makedirs(self.parent_dir, 0o0770)

        self.tmp_dir = tempfile.mkdtemp(dir=self.parent_dir)
        self.oldname = os.getcwd()
        os.chdir(self.tmp_dir)
        return self.tmp_dir

    def __exit__(self, etype, evalue, tb):
        os.chdir(self.oldname)
        shutil.rmtree(self.tmp_dir)
        return False


def _run(command, check=True, timeout=None):
    """! A wrapper for run in case we want to call it remotely """
    assert isinstance(command, str), 'Command must string for shell'

    # The magic here is if the UT_RUN_REMOTE_IP is set, the command
    # will be run as root on the remote host
    host = os.environ.get('UTP_RUN_REMOTE_HOST', None)
    if host:
        cmd = ['/usr/bin/ssh', 'root@{}'.format(host), command]
        logger.debug('cmd: {}'.format(command))
        proc = subprocess.run(cmd, stdout=PIPE, stderr=PIPE, check=check,
                              timeout=timeout)
    else:
        logger.debug('cmd: {}'.format(command))
        proc = subprocess.run(command, shell=True, stdout=PIPE, stderr=PIPE,
                              check=check, timeout=timeout)
    return proc.stdout


def regex_glob(regex, globpattern):
    os.environ['UTP_SUPPRESS_LOG_HANDLERS'] = True
    import UTP

    """! Given a re.compile'ed expression, search files found with glob
    @param regex    A re.compile(...) result
    @param globpattern   This is a filename pattern as you would give for shell

    @returns A list of (file, match) for each match
    """
    assert isinstance(regex, RE_COMPILED), ('{} should be re.compile(...)ed'
                                            .format(regex))
    matches = []
    for flash_def in UTP.glob_file(globpattern):
        with UTP.open_file(flash_def) as fh:
            match = regex.search(fh.read())
            if match:
                matches.append((flash_def, match))

    return matches


class L2IPNotFound(Exception): pass


def get_l1_ip():
    with open(SITE_L1_IP_FILE) as fh:
        return fh.read().strip()

    
def get_l2_ip():
    """! Get the l2 IP address for the current environment

    Tries to figure out the L2 IP address trying each of the following (until one works)
    Reads the local 'variables' file for L2_IP
    Checks /dfcxact/site/L2srvr.txt on L1
    Checks /etc/hosts on the L1 for L2Linux (any case) definition
    If not found, raise an L2IPNotFound exception

    @return str, IP address of L2
    """
    os.environ['UTP_SUPPRESS_LOG_HANDLERS'] = '1'
    import UTP
    import Variable

    ip = Variable.FileBackedVariables().get('L2_IP', None)
    if ip is not None:
        logging.info('Found L2_IP in variables')
    elif UTP.exists(SITE_L2_FILE, scope='l1'):
        with UTP.open_file(SITE_L2_FILE, scope='l1') as fh:
            ip = fh.readline().strip()
        logging.info('Found L2 ip in {} on L1'.format(SITE_L2_FILE))
    else:
        out = _run(['grep', '-i', 'l2linux', '/etc/hosts'], scope='l1', check=False).strip().lower()
        if not out or 'l2linux' not in out:
            raise RuntimeFail(ItemType.other, 'Cannot figure out L2Linux IP:\n'
                              'NO L2_IP set in variables file\n'
                              'NO /dfcxact/site/L2srvr.txt on L1 {l1_ip}\n'
                              'NO L2Linux defined in /etc/hosts on L1 {l1_ip}', l1_ip=UTP.get('L1_IP'))
        ip = [x for x in out.splittlines() if 'l2linux' in x.lower()][0].split()[0]
        logging.info('Found L2Linux defined in /ectc/hosts on {}'.format(UTP.get('L1_IP')))

    logging.info('L2 server IP: {}'.format(ip))
    assert ip, 'The L2 IP address should not be empty string'
    return ip


def get_dhcp_lease(mac, lease_file='/var/lib/dhcp/dhcpd.leases'):
    """ Pass in a MAC and return the latest dhcp lease info as dict

    @param mac  The mac address.  Must be at least twelve chars long after any . or - have been removed

    @return None or {...}   None means the mac is not found in the lease file.  {...} would be the
                            dhcp record names and values.  Names can include:
                            'lease' -> str, ip address
                            'starts' -> str, ex:  2016/11/01 17:39:43
                            'ends' -> str, ex:  2016/11/01 17:49:43
                            'cltt' -> str, ex:  2016/11/01 17:39:43;
                            'binding state' ->  str, ex: active
                            'next binding state' -> str, ex:  free
                            'hardware ethernet' -> str, must match the input mac  6c:ae:8b:4b:4c:15;
                            'client-hostname' ->  str, ex: IMM2-6cae8b4b4c15
    """
    import IAm
    assert IAm.on_type() == 'l1', 'get_dhcp_lease can only run on L1'

    mac = mac.replace('-', '').replace(':', '').replace('.', '').lower()
    assert len(mac) == 12, 'After stripping - and . from mac, the number of chars must equal 12: got {}'.format(mac)
    mac = ':'.join(mac[i:i + 2] for i in range(0, 12, 2))

    with open(lease_file) as fh:
        lines = fh.readlines()

    record = {}
    last_matching_record = None
    for line in lines:
        line = line.strip()

        if not line:
            continue

        if line.startswith('lease'):
            record['lease'] = line.split()[1]
        elif line.startswith('}'):
            if 'hardware ethernet' in record and mac == record['hardware ethernet']:
                last_matching_record = record
            record = {}
        else:
            for name in ('starts', 'ends', 'tstp', 'tsfp', 'atsfp', 'cltt', 'binding state', 'next binding state',
                         'hardware ethernet', 'client-hostname', 'uid'):
                if line.startswith(name):
                    if name in ('starts', 'ends', 'tstp', 'tsfp', 'atsfp', 'cltt'):
                        if 'never' in line:
                            record[name] = datetime.datetime.max.timetuple()
                        else:
                            record[name] = time.strptime(line[len(name):].strip(' ;"'), '%w %Y/%m/%d %H:%M:%S')
                    else:
                        record[name] = line[len(name):].strip(' ;"')

    return last_matching_record


def get_all_dhcp_leases(lease_file='/var/lib/dhcp/dhcpd.leases'):
    """! Return the map of ip address and  dhcp lease info

    @return dict: ip address - lease str-key dict-value pairs. Names can include:
        key -> str, ip address
        'starts' -> str, ex:  2016/11/01 17:39:43
        'ends' -> str, ex:  2016/11/01 17:49:43
        'cltt' -> str, ex:  2016/11/01 17:39:43;
        'binding state' ->  str, ex: active
        'next binding state' -> str, ex:  free
        'hardware ethernet' -> str, must match the input mac  6c:ae:8b:4b:4c:15;
        'client-hostname' ->  str, ex: IMM2-6cae8b4b4c15
    """
    ip_lease_re = re.compile('lease\s*(?P<IP>[\d\.]+\d{1,3})\s*\{(?P<LEASE>[^\{\}]*[^\{])\}')
    os.environ['UTP_SUPPRESS_LOG_HANDLERS'] = '1'
    import UTP
    with UTP.open_file(lease_file, mode='r', scope='l1') as dhcp_lease_file:
        ip_lease_pairs = ip_lease_re.findall(dhcp_lease_file.read())

    assert ip_lease_pairs, 'Unable to parse <{}>!'.format(lease_file)
    lease_records = {}
    for dhcp_ip, lease_info in ip_lease_pairs:
        record = {}
        for line in lease_info.splitlines():
            line = line.strip()
            if not line:
                continue
            # looks like one of these
            # starts 1 2017/04/10 22:32:44;
            # ends 1 2017/04/10 22:42:44;
            # cltt 1 2017/04/10 22:32:44;
            # binding state active;
            # next binding state free;
            # hardware ethernet f0:76:1c:9d:14:7a;
            # uid "\001\360v\034\235\024z";
            # client-hostname "localhost";
            tokens = line.split()
            if tokens[0] in ('starts', 'ends', 'tstp', 'tsfp', 'atsfp', 'cltt'):
                try:
                    record[tokens[0]] = time.strptime(' '.join(tokens[1:4]).strip(';"'), '%w %Y/%m/%d %H:%M:%S')
                except:
                    record[tokens[0]] = None
            elif tokens[0] == 'binding':
                record[' '.join(tokens[:2])] = tokens[2].strip(';')
            elif tokens[0] == 'next':
                record[' '.join(tokens[:3])] = tokens[3].strip(';')
            elif tokens[0] == 'hardware':
                record[' '.join(tokens[:2])] = tokens[2].strip(';').replace(':', '')
            else:
                record[tokens[0]] = ' '.join(tokens[1:]).strip(';')
        lease_records[dhcp_ip] = record
    return lease_records


def get_dhcp_system_ip(mtsn_path=None):
    """ Only runs when in a rt*/ or debug_*/ dir and from the L1 or UUT

    Fetches the ../*.mac files and gathers all the possible macs.   Then checks the dhcp lease file
    and if there is an entry that does not have a client-hostname with 'IMM' in the name, it will
    consdier that IP.  In the case where there is more than on possible IP, it will return the best guess,
    which is the IP with the most recent lease start time (IMM will generally boot long before
    the system has booted an OS).

    @param mtsn_path   Full path to $MTSN dir.  If None (default) then derive the path from CWD.

    @return IP address (str) or None
    """
    return find_latest_ip(mtsn_path=mtsn_path, kind='uut')


def get_dhcp_imm_ip(mtsn_path=None):
    """ See get_uut_system_ip.  Similar, except it only returns a list of IP for IMM(s)

    @param mtsn_path  A full path to $MTSN or None (default).  If None, then it will be taken from CWD path.  It
                      is an error if mtsn_path=None and the CWD is not in an $MTSN path.
    @return list, A list of IP for zero, one, or more IMM IPs.   Can be empty if no IMM IP found in dhcp lease file
    """
    return [dhcp_ip for dhcp_ip, lease in find_latest_ip(mtsn_path=mtsn_path, kind='imm', return_with_lease=True)
            if lease.get('binding state') == 'active']


def is_imm_or_bmc_lease(lease):
    assert lease is not None, 'DHCP Lease dictionary cannot be None!'
    if lease.get('client-hostname', '').startswith('"minint'):
        return False
    return 'IMM' in lease.get('client-hostname', '') or 'uid' in lease or 'XCC' in lease.get('client-hostname', '') \
        or 'AdiRRCAtomBoard' in lease.get('client-hostname', '')


def find_latest_ip(mtsn_path=None, kind='uut', lease_file='/var/lib/dhcp/dhcpd.leases', return_with_lease=False):
    """ Search dhcp lease records for any MACs associated with given MTSN path
    @param mtsn_path:  str: Path to a directory containing *.mac files.  If None, use our current MTSN
    @param kind:       str: Given the lease attributes in a dictionary return False if the lease
                             is not one we are looking for, True if it fits.  Default is to return
                             IPs that do not look like XCC or BMC.
    @param lease_file: str: Alternate lease file. Default: '/var/lib/dhcp/dhcpd.leases'
    @param return_with_lease: If True, will yield the lease of the ip as well
    @return list or str or None    The first IP we find (searching more recent records first) or None if we
                                   never find a map; or list of IMM IPs
    """
    if mtsn_path is None:
        our_path = os.getcwd()
        assert our_path.startswith('/dfcxact/mtsn'), 'CWD must be within /dfcxact/mtsn dir structure'
        path_split = our_path.split(os.sep)[1:]
        assert len(path_split) >= 3
        mtsn_path = osp.join('/dfcxact/mtsn', path_split[2])

    system_macs = MediaTools.get_mac_list(mtsn_path)

    def is_uut(record):
        return not is_imm_or_bmc_lease(record)

    def always_true(record):
        return True

    if kind == 'uut':
        lease_filter = is_uut
    elif kind == 'imm':
        lease_filter = is_imm_or_bmc_lease
    elif kind == 'any':
        lease_filter = always_true
    elif callable(kind):
        lease_filter = kind
    else:
        raise InfoFail('parameter kind can only be "uut"|"imm"|"any"')

    imm_ip_addresses = []
    for dhcp_ip, lease in sorted(get_all_dhcp_leases(lease_file=lease_file).items(), 
                                 key=lambda x: x[1].get('starts'), reverse=True):
        lease_mac_address = lease.get('hardware ethernet')
        if lease_filter(lease) and any(mac == lease_mac_address for mac in system_macs):
            if kind == 'imm':
                imm_ip_addresses.append(dhcp_ip if not return_with_lease else (dhcp_ip, lease))
            else:
                return dhcp_ip if not return_with_lease else (dhcp_ip, lease)

    if kind == 'imm':
        return imm_ip_addresses


def get_link_local_ips(interfaces=[]):
    '''
    Discovers link local IPv6 IPs on specified or all interfaces
    @return a dictionary of interface -> list of IPs
    '''
    all_interfaces = get_network_interfaces()
    interface_to_ips = {}

    if not interfaces:
        interfaces = all_interfaces

    missing_interfaces = set(interfaces) - set(all_interfaces)
    assert not missing_interfaces, 'Invalid Interfaces <{}>'.format(missing_interfaces)

    import UTP
    from IP import IPv6LinkLocalAddress
    for interface in interfaces:
        if interface == 'lo':
            interface_to_ips['lo'] = []
            continue
        ping = UTP.runproc(['ping6', '-c3', 'ff02::1%{}'.format(interface)], scope='local').stdout.decode(errors='ignore')
        ips = re.findall('^\d+ +bytes +from +(\S+): +icmp_seq=', ping, re.M)
        interface_to_ips[interface] = [IPv6LinkLocalAddress(ip, interface) for ip in set(ips)]

    return interface_to_ips


def get_link_local_macs(addresses=[]):
    '''
    Determines MAC address for all IPv6LinkLocalAddress objects
    @return a dictionary of ip -> MAC
    '''
    return {ip: get_link_local_mac(ip) for ip in addresses}


def get_link_local_mac(address):
    '''
    Determines MAC address using an IPv6LinkLocalAddress object
    @return string representation of MAC with :'s (e.g. AB:CD:EF:01:23:45)
    '''
    import UTP
    from IP import IPv6LinkLocalAddress

    address_type = type(address)
    expected_type = IPv6LinkLocalAddress

    assert address_type == expected_type, 'Function only operates on {}, called with {}'.format(expected_type, address_type)

    UTP.runproc(['ping6', '-c1', address.with_interface], scope='local').stdout.decode(errors='ignore')
    neighbors = UTP.runproc(['ip', '-6', 'neigh', 'show', 'dev', address.interface, 'to', str(address)],
                            scope='local').stdout.decode(errors='ignore')

    match = re.search('^{} +lladdr +(\S+) '.format(address), neighbors)
    if match:
        return match.group(1).upper()
    else:
        interface_info = UTP.runproc(['ip', 'addr', 'show', 'dev', address.interface],
                                     scope='local').stdout.decode(errors='ignore')
        match = re.search('link/\w+ +(\S+) +brd.*inet6 +([^/]+)/64 +scope +link', interface_info, re.S)
        if match and str(address) == match.group(2):
            return match.group(1).upper()
        else:
            raise InfoFail('No MAC found for link local IP {address} on interface {interface}', address=address, interface=address.interface)


def get_network_interfaces():
    '''
    @return list of current interfaces on the local scope
    '''
    import UTP
    link_info = UTP.runproc(['ip', 'link', 'show'], scope='local').stdout.decode(errors='ignore')
    return re.findall('^\d+: *([^:]+):', link_info, re.M)


class MountFS:
    """! Use with a 'with' statement to mount a remote file system to a local directory

    This 'with' context is designed to mount something briefy, use the mounted file system, and umount.
    You pay a performance penalty for recreating the mount each time, but if you have a situation like
    1000s of UUT mounting the L2, you don't want to keep these up permanently or even semi-permanently.

    The mount is done to a temporary directory, guaranteed to be unique.  The temp dir name is returned
    for the 'as' statement in the 'with'

    @param remotefs   The target system and path to mount.  The format is specific to the mtype (see man pages)
    @param mtype      The type of mount being created (see -t param in 'man mount') DEFAULT: cifs
    @param moptions   A iterable like list or tuple.  Will be passed options in the -o param (see man pages for
                      the type of mount bing made) DEFAULT: options that work for most L1 or UUT cifs mounts
    @param scope      Where the mount actually happens: 'local'|'uut'|'l1'|'l2'|'l3'  DEFAULT: local
    @param umounterror  True/False  If False then a failure to umount will be flagged as warning only
                        DEFAULT: False

    @b Usage
    @code
    with MountFS('//172.17.2.1/dfcxact') as l2dfcxact:
        if os.path.exits(os.path.join(l2dfcxact, 'some/path')):
            with open(os.path.join(l2dfcxact, 'some/path')) as fh:
                fh.read() # etc
    @endcode
    """

    def __init__(self, remotefs, mtype='cifs', moptions=('username=l2plclient','password=L2client','sec=ntlmssp'),
                 scope='uut', umounterror=False):
        self.remotefs = remotefs
        self.scope = scope
        self.mtype = mtype
        self.moptions = moptions
        self.umounterror = umounterror

    def __enter__(self):
        os.environ['UTP_SUPPRESS_LOG_HANDLERS'] = '1'
        import UTP

        self.tempdir = mount(self.remotefs, '<TEMP>', scope=self.scope, mtype=self.mtype, moptions=self.moptions)
        return self.tempdir

    def __exit__(self, etype, evalue, tb):
        os.environ['UTP_SUPPRESS_LOG_HANDLERS'] = '1'
        import UTP

        if umount(self.tempdir, scope=self.scope, throw=self.umounterror):
            UTP.rmdir(self.tempdir, scope=self.scope)


def mount(remotefs, local_dir, mtype='cifs', moptions=('username=l2plclient','password=L2client','sec=ntlmssp'),
          scope='uut'):
    """! Mount a remote server's filesystem
    @param remotefs   The target system and path to mount.  The format is specific to the mtype (see man pages)
    @param local_dir  The local directory to contain the mount point.  If it doesn't exist it will be created.
                      The special value '<TEMP>' can be passed tempfile.mkdtemp wll be used to create a dir.
    @param mtype      The type of mount being created (see -t param in 'man mount') DEFAULT: cifs
    @param moptions   A iterable like list or tuple.  Will be passed options in the -o param (see man pages for
                      the type of mount bing made) DEFAULT: options that work for most L1 or UUT cifs mounts
    @param scope      Where the mount actually happens: 'local'|'uut'|'l1'|'l2'|'l3'  DEFAULT: local

    @return The name of the mounted directory
    """
    os.environ['UTP_SUPPRESS_LOG_HANDLERS'] = '1'
    import UTP

    local_dir = UTP.mkdtemp(scope=scope) if local_dir == '<TEMP>' else local_dir

    # There is a problem mounting the L2 with a RHEL7.6 ramdisk where Samba version is incompatible, so force v1
    if mtype == 'cifs' and 'username=l2plclient' in moptions and UTP.exists('/etc/redhat-release', scope=scope):
        with UTP.open_file('/etc/redhat-release', scope=scope) as rhelrel:
            try:
                rhel_ver = re.findall(r"release ([\d.-]+)", rhelrel.read())[0]
            except IndexError:
                logging.warning('Failed to determine a RHEL version from redhat-release file')
            else:
                rhel_ver = tuple(int(x) for x in rhel_ver.split('.'))
                if rhel_ver >= (7, 6) and 'vers=1.0' not in moptions:
                    logging.info('Adding vers=1.0 to default cifs options due to RHEL 7.6 on scope {}'.format(scope))
                    moptions = moptions + ('vers=1.0',)

    logging.info('Mounting {} -> {}'.format(remotefs, local_dir))

    assert isinstance(remotefs, str) and len(remotefs) > 8, 'param remotefs needs to be str and > 8 char'
    assert isinstance(local_dir, str), 'param  local_dir must be str'

    for retry in range(3):
        # See if the specified mount point already exists
        mounted_devices = UTP.runproc(['mount'], scope=scope).stdout.decode(errors='ignore')
        if remotefs not in mounted_devices or local_dir not in mounted_devices:
            # either there is mount or the wrong local_dir is mounted, so attempt to remount
            UTP.run(['umount', local_dir], scope=scope, check=False, log_stderr=False)
            UTP.run(['mkdir', '-p', local_dir], scope=scope)
            assert isinstance(moptions, (list, tuple))
            if mtype is not None:
                cmd = ['mount', '-t', mtype, remotefs, local_dir]
                if moptions:
                    cmd.insert(3, '-o{}'.format(','.join(moptions)))
            else:
                cmd = ['mount', remotefs, local_dir]
                if moptions:
                    cmd.insert(1, '-o{}'.format(','.join(moptions)))

            logging.info('Mount cmd: {}'.format(' '.join(cmd)))
            UTP.run(cmd, scope=scope)
            continue
        else:
            break
    else:
        raise RuntimeFail(ItemType.rc, 'ERROR!!! Failed to create mount point: {local_dir}', local_dir=local_dir)

    return local_dir


def umount(mount_dir, scope='uut', throw=True):
    """! umount the given mount point
    @param mount_dir The mount dir
    @param scope     Where to run the umount command: 'local'|'uut'|'l1'|'l2'|'l3'  DEFAULT: local
    @param throw     If True, raise an excepiton if the umount command fails, else log warning.  DEFAULT: True

    @return  True if the umount appeared to be successful, False otherwise (only returns if throw=False in this case)
    """
    os.environ['UTP_SUPPRESS_LOG_HANDLERS'] = '1'
    import UTP
    logging.info("umount'ing {} on {}".format(mount_dir, scope))
    if UTP.runproc(['umount', mount_dir], scope=scope).returncode == 0:
        return True
    elif throw:
        raise RuntimeFail(ItemType.rc, 'The umount of {mout_dir} on {scope} was not successful', mount_dir=mount_dir, scope=scope)
    else:
        logging.warning('The umount of {} on {} was not successful'.format(mount_dir, scope))
        return False


MountyEntry = collections.namedtuple('MountEntry', ('source', 'target', 'mount_type', 'options'))
_mount_entry_list = None


class MountEntryList(collections.UserList):
    def __contains__(self, mount_name):
        """! The usecase for this function is as follows:
        @code
        if '/dev/sda1' in get_mounted_devices():
            do_something()
        # Which translates to the following check:
        '/dev/sda1' == '/dev/sda1 on /boot type cifs (rw)'.split()[0]
        @endcode
        """
        for mount_point in self.data:
            if mount_name == mount_point.source:
                return True
        return False


def get_mounted_devices(scope='uut'):
    """! Run mount and parse output into MountEntries."""
    global _mount_entry_list
    if _mount_entry_list is None:
        os.environ['UTP_SUPPRESS_LOG_HANDLERS'] = '1'
        import UTP
        # NOTE The explanation for the output of mount is found in this StackOverflow article
        # NOTE http://unix.stackexchange.com/questions/256420/meaning-of-output-of-mount
        mount_point_regex = re.compile('(?P<source>.*)\s+on\s+(?P<target>.*)\s+type\s+(?P<mount_type>.*)\s+(?P<options>.*)')
        _mount_entry_list = MountEntryList()
        for mount_point in UTP.run(['mount'], scope=scope).splitlines():
            parsed_mount_point = mount_point_regex.search(mount_point)
            if parsed_mount_point:
                _mount_entry_list.append(MountyEntry(*parsed_mount_point.groups()))
    return _mount_entry_list


def get_this_server_utp_ip():
    with open(UTP_IP_FILE) as fh:
        return fh.read().strip()


def get_utp_l2_ip():
    if not osp.exists(UTP_L2_IP_FILE):
        return None
    with open(UTP_L2_IP_FILE) as fh:
        return fh.read().strip()


def diff_dict(old, new):
    """! Create a diff of two dictionaries

    @param old  dict: This is the 'from' dictionary
    @param new  dict: This is the 'to' dictionary

    Returns a list of operation that will transform the old
    dictionary to the new dictionary.  Each operation tuple 
    has three elements (action, key, value)
    For mapping old -> new action can be
    @code
    'u'  Update the given key with the new value
    'a'  Add the given key with the new value
    'd'  Delete the given key, the value is the old value

    @return list of: ('u'|'a'|'d', key, value)
    """
    old_set = set(old.keys())
    new_set = set(new.keys())
    
    return [('a', k, new[k]) for k in new_set - old_set] + [('d', k, old[k]) for k in old_set - new_set] \
        + [('u', k, new[k]) for k in old_set & new_set if new[k] != old[k]]
                  

def get_mtm_repos(mt, model):
    """! Given a MT and MODEL, return a mapping of generic link name to actual product specific repo mapping

    A MTSN/$RT dir must contain symbolicly directories to working directories of code.  
    The minimum for UTP is common/ product/ platform/,  but this is not a hard and fast rule 
    (although utp.git platform tools do assume this structure)

    @param mt  Machine type
    @param model  model

    @return  {link_name1: full_repo_path1, ...}  A mapping of symbolic link name to build to source repo (full path)
             to source the build.
    """
    # Lookup the MTM first, then MT, if one not found it's an error
    for mtm_info_dir in (osp.join(MTM_DIR, '{}{}'.format(mt, model)), osp.join(MTM_DIR, mt)):
        logger.debug('Checking {}'.format(mtm_info_dir))
        if osp.exists(mtm_info_dir):
            break
    else:
        raise NotUTPEnabled('Cannot find a repo definition for {mt}', mt=mt)

    generic_name_to_repo_path = {}
    override_name_to_repo_path = {}
    for x in os.listdir(mtm_info_dir):
        link = osp.join(mtm_info_dir, x)

        ## Look for repo_links.py
        ## if found, then exec() it and call get_repo_links() function which must return
        ## dict: { 'link_name', '../path/to/repo/dir', ...}
        ## path can be absolute (startswith /).  If not, then the dir where repo_links.py was found will be
        ## prepended and abspath() taken
        ## repo_links.py overrides any symbolic (legacy) link info
        if x == 'repo_links.py':
            try:
                with open(link) as fh:
                    c = compile(fh.read(), 'repo_links.py', 'exec')
                g = dict(globals())
                exec(c, g)
                overrides = g['get_repo_links']()
                if overrides is None:
                    continue
                for name, target in overrides.items():
                    assert isinstance(name, str)
                    assert isinstance(target, str)
                    if target.startswith('/'):
                        full_target_path = target
                    else:
                        full_target_path = osp.abspath(osp.join(mtm_info_dir, target))
                    if not osp.exists(full_target_path):
                        raise FileNotFoundFail(full_target_path, msg='repo_links.py path <{target}> resolving to <{filename}> is not found', target=target)
                    override_name_to_repo_path[name] = full_target_path
            except Exception as e:
                logger.warn('There is an problem with <{}>: {}: {}'.format(link, type(e).__name__, e.args[0]))
            continue
                
        if not osp.islink(link):
            logger.warn('Skipping entry mtm->repo mapping {} because it is not symbolic link'.format(x))
            continue

        target = os.readlink(link)
        target_path = osp.abspath(osp.join(mtm_info_dir, target))

        if not osp.exists(target_path):
            logger.warn('Not setting up code link {} per {} because the target {} does not exist'
                         .format(x, mtm_info_dir, target_path))
            continue

        if not osp.isdir(target_path):
            logger.warn('Not setting up code link {} per {} because the target {} is not a directory'
                         .format(x, mtm_info_dir, target_path))
            continue

        generic_name_to_repo_path[x] = target_path

    generic_name_to_repo_path.update(override_name_to_repo_path)

    return generic_name_to_repo_path



UNIT_SIZES = [(10**6, 'MB'),
              (10**9, 'GB'),
              (10**12, 'TB'),
              (10**15, 'PB')]


def normalize_drive_size(byte_count):
    for divider, units in UNIT_SIZES:
        result = round(byte_count / divider, 2)
        if result < 1000:
            ## deal with results like 899, which should be 900
            if result >= 100 and -1 <= (result - ceil(result/100.0)*100) <= 1:
                result = float(ceil(result/100.0)*100)
            elif result >= 10 and -0.1 <= (result - ceil(result/10.0)*10) <= 0.1:
                result = float(ceil(result/10.0)*10)
            elif result >= 1 and -0.01 <= (result - ceil(result)) <= 0.01:
                result = float(ceil(result))
                
            sresult = str(result)[:4]
            sresult = sresult.rstrip('0')
            sresult = sresult.rstrip('.')
            return sresult, units

    raise InfoFail('Size of drive is >= 10000 PB?')

def get_default_gateway():
    import socket, struct
    with open("/proc/net/route") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            interface, destination, gateway, flags, *rest = line.split()
            if destination != '00000000' or not int(flags, 16) & 2:
                continue

            return socket.inet_ntoa(struct.pack("<L", int(gateway, 16)))
