#!/usr/local/bin/python35
import sys
import os
import string
import os.path as osp
import logging
import tempfile
import time
import subprocess
import shutil
import contextlib
import re
import io


# assumes we start in rt/ or rt_N/ or $debug/ or $debug_N/ which is subdir of mtsn
OUR_RT_DIR = os.getcwd()
OUR_REPO_DIR = osp.abspath(osp.dirname(osp.dirname(__file__))) # Our repo dir
OUR_MODULE_DIR = osp.join(OUR_REPO_DIR, 'modules') # Our repo/modules


from Default import *
import SSHTool
import IAm

import Fails  # this will import all Fail classes and ItemType into builtins namespace


log = logging.getLogger(__name__)

THIS_FILE = osp.abspath(__file__)


REMOTE_MTSN_MANAGER_TEMPLATE = """
if [ {mac} != None ]; then
    # Fetch by mac
    if [ -e {WHERE_DIR}/{mac}.mac ]; then
        cat {WHERE_DIR}/{mac}.mac
    elif [ -e {MACINUSE_DIR}/{mac}.mac ]; then
        cat {MACINUSE_DIR}/{mac}.mac
    fi
else
    # Fetch by sn
    if [ -e {expected_media_path} ]; then
        cd {expected_media_path}
        for mac in *.mac; do 
            cat {WHERE_DIR}/$mac && break
            cat {MACINUSE_DIR}/$mac && break
        done
    fi
fi
"""

class SSHMacinuseException(CommandFail): pass

class MTSNFileMissing(FileNotFoundFail): pass

# Some media helpers
def get_media_name(sn, mt):  
    """! Derive an MTSN directory name given the sn and mt
    @param  sn   Serial number of the order
    @param  mt   Machine type of the order

    At this time the MT is not required to form the MTSN name,
    but that could possible change in the future.
    """
    return sn.upper().zfill(8)


def get_media_path(media):
    """ ! Return the full path of our MTSN
    @return The full path of of an MTSN as it would be found on L1 or L2

    Requires variables SN and MT be set.
    """
    assert len(media)
    return osp.join(osp.join(MTSN_DIR, media))


def get_media_rt_path(media=None, index=None):
    """! Resolve the basename of media to a full path

    @param media  Base name of some media.  Defaults to None which means
                  the current directory MTSN
    @param index  If there is more than one process running under the same $MTSN, you can use index to indicate
                  which rt path to generate.   index=None is the default, and will retrieve "OUR" rt dir.
                  index=0 will return the rt/ directory, and any non-zero index x will return rt_x

    @return Full path to a runt time directory under an $MTSN
    """
    import Variable

    assert index is None or int(index) >= 0, 'Param index must be an int and must be >= 0'
    if media is None:
        ## check if we are in  /dfcxact/mtsn/*/*
        assert OUR_RT_DIR.startswith('/')
        our_rt_path_list = OUR_RT_DIR[1:].split(os.sep)
        if (OUR_RT_DIR.startswith(MTSN_DIR) and len(our_rt_path_list) == 4
            or os.environ.get('UTP_ALL_SCOPE_LOCAL', False)):
            ## Use our RT dir as the cwd
            if index is not None and not OUR_RT_DIR.endswith('rt'):
                media_rt_path = re.sub(r'({}/rt)(_\d+)'.format(osp.dirname(OUR_RT_DIR)), r'\1', OUR_RT_DIR) +\
                       ('' if index == 0 else '_{}'.format(index))
            elif index is None:
                media_rt_path = OUR_RT_DIR
            else:
                media_rt_path = OUR_RT_DIR + ('' if index == 0 else '_{}'.format(index))
        else:
            ## We could be anywhere, so rely on local variables
            # Force a local lookup of SN, MT, DEBUG_NAME
            local_vars = Variable.FileBackedVariables(osp.join(OUR_RT_DIR, 'variables'))
            media_path = get_media_path(get_media_name(local_vars['SN'], local_vars['MT']))
            media_rt_path = osp.join(media_path, local_vars['DEBUG_NAME'])
    else:
        other_media_path = get_media_path(media)
        rt_name = 'rt'
        with contextlib.suppress(FileNotFoundError):
            other_vars = Variable.FileBackedVariables(osp.join(other_media_path, 'variables'))
            rt_name = other_vars.get('DEBUG_NAME', rt_name)
        media_rt_path = osp.join(other_media_path, rt_name + ('_{}'.format(index) if index else ''))

    return media_rt_path


def get_id_info(mtsn_path):
    # first try variables
    info = {}
    for var_file in (osp.join(mtsn_path, 'rt', 'variables'), osp.join(mtsn_path, 'variables')):
        if osp.exists(var_file):
            with contextlib.suppress(FileNotFoundError, KeyError):
                try:
                    import Variable
                    variables = Variable.FileBackedVariables(var_file)
                    info['mtm'] = '{}{}'.format(variables['MT'], variables['MODEL'])
                    info['sn'] = variables['SN']
                except ValueError as e:
                    logging.error('Error: {} {}'.format(var_file,e))
                    continue
                return info

    # second try mac files
    mtsn = osp.basename(mtsn_path)
    for ea in os.listdir(mtsn_path):
        if ea.endswith(".mac"):
            mac_info = get_mac_info(osp.join(mtsn_path, ea))
            if mac_info.get('MTSN') == mtsn:
                mtm = mac_info.get('MTM')
                sn = mac_info.get('SN')
                if mtm and sn:
                    info.update(mtm=mtm, sn=sn)
                    return info

    id_file = osp.join(mtsn_path, 'ID.LOG')
    if not osp.exists(id_file):
        raise MTSNFileMissing([var_file, id_file])

    with open(id_file) as fh:
        line = fh.readline()
        if '=' in line:
            # Do it the new way  (key=value per line)
            while line:
                key,value = line.split('=', 1)
                info[key.strip().lower()] = value.strip()
                line = fh.readline()
        else:
            # Assume old way
            #9532AC1          ANDTBE4 1S9532AC1ANDTBE4        NO_CFGNUM
            mtm, sn, one_s, config_num = line.split(None, 3)
            info['mtm'] = mtm.upper()
            info['sn'] = sn.upper()
            info['one_s'] = one_s.upper()

    return info


def get_mac_info(mac_path):
    """! Read a mac file and return a dictionary of info
    @param mac_path   Full path to a mac file OR a file handle open for reading
    @return  info_dict   A dictionary of information for each key=value entry
    All keys are normalized to upper case.  If there is a MACS= entry, the
    value will be returned as a set() of macs
    """
    if isinstance(mac_path, str):
        with open(mac_path) as fh:
            lines = fh.readlines()
    else:
        lines = mac_path.readlines()

    mac_info = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, value = line.split('=', 1)
        key = key.strip().upper()
        value = value.strip()
        if key == 'MACS':
            mac_info['MACS'] = set(verify_mac_format(x) for x in value.split())
        else:
            mac_info[key] = value

    return mac_info
        


def create_mac_files(macs, mt, model, serial, path='.'):
    """! Create all the .mac files for give list of macs

    Defaults to making mac files in the current directory

    @param  macs      List of MAC address (12 digits each)
    @param  mt        Machine Type
    @param  model     Model
    @param  serial    Serial number
    @param  path      Write the MAC file in the given path (default: .)

    @return List of absolute paths to created files

    Creates each file in an atomic way by first creating a temporary file,
    writing to it, then hardlinking the final name.
    """
    assert macs, 'Cannot call create_mac_files with an empty list of macs'
    for mac in macs:
        verify_mac_format(mac)

    macs = [x.lower() for x in macs]

    mtm = mt + model

    fh, tmpfile = tempfile.mkstemp(dir=path)
    os.chmod(tmpfile, 0o666)
    mac_file_list = []
    try:
        os.write(fh, 'MACS={}\n'.format(' '.join(macs)).encode())
        os.write(fh, 'MTSN={}\n'.format(serial.upper().zfill(8)).encode())
        os.write(fh, 'MTM={}\n'.format(mtm.upper()).encode())
        os.write(fh, 'SN={}\n'.format(serial.upper()).encode())
        os.close(fh)

        for mac in macs:
            mac_file = osp.join(path, mac + '.mac')
            if osp.exists(mac_file):
                os.unlink(mac_file)
            os.link(tmpfile, mac_file)
            mac_file_list.append(osp.abspath(mac_file))
    finally:
        os.unlink(tmpfile)

    return mac_file_list


VERIFY_12D = True


def verify_mac_format(mac):
    """
    Jan 25 2018: now checking for hexdigits and acscii_letters so a rack mtsn 
                 that has no MAC address can use MT + SN as a MAC address.
                 This is allow the current tools in MFG to continue to work as is
    """
    assert not VERIFY_12D or len(mac) == 12, 'MAC [{}] not 12 digits'.format(mac)
    assert all(x in (string.hexdigits + string.ascii_letters) for  x in mac),  \
        'MAC [{}] has non-hex digit'.format(mac)
    return mac.lower()
                               

def get_mac_list(mtsn_path):
    """!
    Given the path to an existing MTSN dir return a set of  MAC

    It is possible for the MTSN to contain no MAC info, so it may return
    an empty set.

    @param mtsn_path  Full path to an existing MTSN dir

    @return set of 12D MAC addresses

    """
    assert osp.exists(mtsn_path),\
        'The given path {} does not exist'.format(mtsn_path)

    macs = set()
    # Find at least one .mac file from dir and retrieve MACS= list
    for ea in os.listdir(mtsn_path):
        if ea.endswith(".mac"):
            macs.update(get_mac_info(osp.join(mtsn_path, ea))['MACS'])
            if len(ea) == 12 + len('.mac'):
                macs.update([ea[0:12].lower()])
    return macs 


class MTSNManager (object):

    def __init__(self, base_dir=BASE_DIR, macinuse_dir=MACINUSE_DIR,
                 where_dir=WHERE_DIR,
                 product_dir=PRODUCT_DIR,
                 mtsn_parent_dir=MTSN_DIR):
        super().__init__()
        self.base_dir = base_dir
        self.macinuse_dir = macinuse_dir
        self.where_dir = where_dir
        self.product_dir = product_dir
        self.mtsn_parent_dir = mtsn_parent_dir


    def get_mtsn_path(self, mtsn):
        return osp.join(self.mtsn_parent_dir, mtsn)


    def macinuse_by_mac(self, mac):
        verify_mac_format(mac)
        for macinuse_file in (osp.join(self.where_dir, mac.lower() + '.mac'),
                              osp.join(self.macinuse_dir, mac.lower() + '.mac')):
            if osp.exists(macinuse_file):
                break
        else:
            return None

        return get_mac_info(macinuse_file)


    def macinuse_by_sn(self, sn):
        for d in (self.where_dir, self.macinuse_dir):
            with contextlib.suppress(FileNotFoundError):
                for macinuse_file in os.scandir(d):
                    if not macinuse_file.is_file():
                        continue
                    if not macinuse_file.name.endswith('.mac'):
                        continue
                    macinuse = get_mac_info(macinuse_file.path)
                    with contextlib.suppress(KeyError):
                        if macinuse['SN'].upper() == sn.upper():
                            return macinuse


    def find_mtsn_for_mac(self, mac):
        """! Return the mtsn for a given MAC
        @param mac   12 digit mac 
        @return  Full path of the MTSN for given MAC. Will return None if 
                 there is no known MTSN for the given MAC
        """
        verify_mac_format(mac)
        macinuse_file = osp.join(self.macinuse_dir, mac.lower() + '.mac')
        if not osp.exists(macinuse_file):
            return None

        info = get_mac_info(macinuse_file)
        assert 'MTSN' in info, 'Error in macninuse mac file ' + \
                        '{}: Cannot find "MTSN="'.format(macinuse_file)

        return osp.join(self.mtsn_parent_dir, info['MTSN'].upper())


    def find_l1_for_mtsn(self, mtsn, allow_cleanup=False):
        """!
        Given the basename of mtsn, return l1 where it is located

        @param mtsn   Name of the mtsn (basename only)
        @param allow_cleanup    If True, attempt to cleanup *other* MTSNs that are referenced by our MAC files

        @return  (l1_hostname, where_file) or None if the mtsn is only on L2
        The where_file is full path to the macinuse/where file found
        """
        assert '/' not in mtsn, 'Use only the mtsn name, and not full path'
        
        mtsn = mtsn.upper()
        mtsn_path = self.get_mtsn_path(mtsn)
        assert osp.exists(mtsn_path), \
            'MTSN directory [{}] does not exist'.format(mtsn_path)
        for mac in get_mac_list(mtsn_path):
            for m in (mac, mac[-8:]):
                mac_where_path = osp.join(self.where_dir, '{}.mac'.format(m))
                if osp.exists(mac_where_path):
                    where_file_mtsn = get_mac_info(mac_where_path)['MTSN']
                    if where_file_mtsn == mtsn.upper():
                        l1 = get_mac_info(mac_where_path)['L1']
                        log.info('L1 for MTSN {} is {} according to {}'.format(mtsn, l1, mac_where_path))
                        return l1, m
                    else:
                        log.warning('Found conflicting MTSN in <{mac_where_path}>! theirs: {where_file_mtsn} '
                                    '!= ours: {mtsn}'.format(**locals()))
                        if allow_cleanup:
                            log.warning('Cleaning up conflicting MTSN!')
                            temp_media_manager = MTSNManager()
                            temp_media_manager.move_mtsn_from_l1_to_l2(where_file_mtsn)

        return None


    def remove_mac(self, mac):
        """! Remove matching .mac files from macinuse/ and then MTSN

        It is an error if there is a macinuse/where file for the given 
        mac: you must have missed a step like move_mtsn_from_l1_to_l2()
        
        @param mac

        @return mtsn_path   Full path to MTSN that 'owned' MAC.   Returns
                            None if the mac is unknown or there is no
                            MTSN associated
        """
        mac = verify_mac_format(mac)
        macinuse_where = osp.join(self.where_dir, mac + '.mac')
        with contextlib.suppress(FileNotFoundError):
            os.unlink(macinuse_where)
            log.warning("Also removed orphaned 'where' mac: {}".format(macinuse_where))
            
        assert not osp.exists(macinuse_where), 'It is an error to remove '+\
            '{}.mac files while there is still an entry in macinuse/where'.\
            format(mac)

        macinuse = osp.join(self.macinuse_dir, mac + '.mac')
        
        mtsn_path = self.find_mtsn_for_mac(mac)

        try:
            os.unlink(macinuse)
            log.info('Removed mac <{macinuse}>'.format(**locals()))
        except FileNotFoundError:
            pass

        if mtsn_path:
            try:
                os.unlink(osp.join(mtsn_path, mac + '.mac'))
            except FileNotFoundError:
                pass

        return mtsn_path


    def remove_where_files_for_mtsn(self, mtsn):
        """! Given the mtsn name remove any macinuse/where files referencing it

        @param  mtsn   Basename of the mtsn

        @return set of L1

        For every /where file found, the L1 is recorded and returned in a
        set.   There should only be zero or one L1 in the set, but allow
        for this to be > 1 in case something has gone wrong.
        """
        l1_list = []
        result = self.find_l1_for_mtsn(mtsn)
        while result:
            l1_list.append(result[0])
            mac = '{}.mac'.format(osp.join(self.where_dir, result[1].lower()))
            log.info('Removing {} ...'.format(mac))
            os.unlink(mac)
            result = self.find_l1_for_mtsn(mtsn)

        return set(l1_list)


    def remove_mtsn_from_l1(self, mtsn, l1):
        """!
        Unconditionally removes any macinuse/* file that references the given
        MTSN and then removes the MTSN directory

        @note Don't call this method unless you have copied the MTSN
        to the L2 or to another L1 first!

        @param mtsn   The basename of the MTSN
        @param l1     IP or hostname of l1

        @return 0 if the removal was a success, non-zero otherwise.  If the
        MTSN was not present on the L1, the return will also be zero.
        """

        mtsn = mtsn.upper()

        cmd = """
        for mac_file in $(egrep -il 'MTSN\s*=\s*{}' {}/*.mac); do
             rm -f $mac_file || exit 1
        done
        if [ -e {} ]; then
            rm -fR {} || exit 2
        fi
        """.format(mtsn, self.macinuse_dir,
                     self.get_mtsn_path(mtsn),
                     self.get_mtsn_path(mtsn))

        log.debug('rm command for L1:\n{}'.format(cmd))
        rc, out = SSHTool.ssh(host=l1, cmd=cmd, password='passw0rd',
                              user='root')
        log.debug('rm results:\n{}'.format(out))

        return rc, out


    def create_macinuse_files(self, mtsn):
        """!
        For given MTSN, make sure there are macinuse files for each MAC

        @param mtsn  Basename of the MTSN
        """
        mtsn = mtsn.upper()

        mtsn_path = self.get_mtsn_path(mtsn)
        assert osp.exists(mtsn_path),\
            'The given MTSN {} does not exist'.format(mtsn)

        macs = get_mac_list(mtsn_path)
        if not macs:
            log.warn('No MAC files found for {}'.format(mtsn))
            return

        id_info = get_id_info(mtsn_path)
        macinuse_files = create_mac_files(macs, mt=id_info['mtm'][:4],
                                          model=id_info['mtm'][-3:],
                                          serial=id_info['sn'],
                                          path=self.macinuse_dir)

        return macinuse_files


    def move_mtsn_from_l1_to_l2(self, mtsn, allow_cleanup=False):
        """!
        Move the given MTSN directory (basename) from an L1 to the L2

        This function is designed to be run from the L2.  If the given MTSN
        is on an L1, it will rsync the MTSN from the L1 to the L2 and remove
        all traces and references to the MTSN from the L1 and update the L2
        so it correctly shows the MTSN not on any L1.

        Returns the full path to the mtsn and a full-path list of mac files in 
        macinuse/ which may be be empty.

        It is an error if the mtsn does not exist on the L2.
        It is not an error if the MTSN is not deployed to an L1.

        @param mtsn   Basename of the MTSN
        @param allow_cleanup    If True, will be passed into find_l1_for_mtsn to allow for cleanup if we stumble on
            a different MTSN. Note this happens when moving a slave ETH device between two different SNs without 
            properly cleaning up the original SN's where file pointer

        @return mtsn_path, [macinuse_file1, macinuse_file2, ...]
        """
        mtsn = mtsn.upper()

        ### find l1 (if any)
        result = self.find_l1_for_mtsn(mtsn, allow_cleanup=allow_cleanup)

        mtsn_path = self.get_mtsn_path(mtsn)


        if result:
            l1 = result[0]

            ### rsync mtsn from l1 -> l2
            cmd = ['rsync', '-a', '--exclude=code',  # we can remove after legacy is done
                   '--exclude=.*/',   # exclude any hidden directories (like .git)
                   '--chmod=Dug+rwx,Fug+rw',   # Force directories to rwx for user and group, files to to rw 
                   '-e', 'ssh -oConnectTimeout=5',
                   'root@{}:{}/'.format(l1, mtsn_path),
                   '{}/'.format(mtsn_path) ]

            log.info('rsync from L1 cmd: {}'.format(cmd))
            rc, out, err = SSHTool.run_cmd(cmd=cmd, password='passw0rd',
                                           combine_std_out_err=True)
            log.debug('rsync L1->L2:\n{}'.format(out))

            if rc:
                if 'ermission' in out or 'peration not permitted' in out:
                    # try to reset permissions on our end
                    cmds = ['sudo -n /bin/chown -R l2plclient /dfcxact/mtsn', 
                            'find {}'.format(mtsn_path) + ' -type d -exec chmod ug+x {} \;']
                    for permission_cmd in cmds:
                        proc = subprocess.run(permission_cmd, shell=True)
                        if proc.returncode != 0:
                            raise CommandFail(proc.returncode, proc.args, proc.stdout, proc.stderr, msg="Cannot run cmd: [{cmd}]:\n{output}")

                    log.warn('Reset permission on /dfcxact/mtsn, trying again...')

                    log.debug('rsync from L1 (2nd try) cmd: {}'.format(cmd))
                    rc, out, err = SSHTool.run_cmd(cmd=cmd, password='passw0rd', combine_std_out_err=True)
                    log.debug('rsync L1->L2 (2nd try):\n{}'.format(out))
                    if rc:
                        raise CommandFail(rc, cmd, out, err, msg='Tried fixing permissions with '
                                          '{cmd}, '
                                          'but still failed:\n{output}')
                elif 'No such file or directory' in out:
                    log.warn("MAC 'where' file says MTSN on L1 {}, but it "
                                 'is not ... pressing on anyways'.format(l1))
                else:
                    raise CommandFail(rc, cmd, out, err, msg='failed {cmd}:\n{output}')

        l1_remove_list = self.remove_where_files_for_mtsn(mtsn)
        for l1 in l1_remove_list:
            rc, out = self.remove_mtsn_from_l1(mtsn, l1)
            if rc:
                raise RuntimeFail(ItemType.rc, 'Remove of {mtsn} from {l1_ip} failed:\n{output}', mtsn=mtsn, l1_ip=l1, output=out)

        ### make sure macinuse files are all present
        macinuse_list = self.create_macinuse_files(mtsn)
        
        return mtsn_path, macinuse_list


    def move_mtsn_for_mac_from_l1_to_l2(self, mac):
        """!
        Move the MTSN directory for a given mac from the L1 to the L2

        This function is designed to be run from the L2.  Given a 12 digit
        MAC, it will find the MTSN directory that owns the MAC and if that
        MTSN is on an L1, it will copy the MTSN from the L1 to the
        L2 and remove all traces and references to the MTSN from
        the L1 and update the L2 so it correctly shows the MTSN not on any L1.

        It is not an error if the MTSN is not currently on an L1.
        It is not an error if mac does not correspond to an MTSN, but in this
        case the function which normally returns the full path to the MTSN
        will return None.

        @param mac   12 digit MAC

        @return full_mtsn_path, mac_list  
        Return tuple of full path to the MTSN as it sits on the L2 and list
        of MAC for the given MTSN.  If the given MAC does not match an MTSN, 
        None will be the returned value.
        """
        mtsn_path = self.find_mtsn_for_mac(mac)
        if mtsn_path == None:
            return None

        if not osp.exists(mtsn_path):
            # Found a case where $MTSN delete happened before the MAC file delete, we will clean these
            # mac files up
            for f in (osp.join(self.where_dir, mac + '.mac'), osp.join(self.macinuse_dir, mac + '.mac')):
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(f)
            return None

        return self.move_mtsn_from_l1_to_l2(osp.basename(mtsn_path))

    def replace_mtsn(self, mtsn, source_path):
        """!
        Given a newly created MTSN, but named something temporary, replace
        the existing one (if any) with it.

        This is more complicated than it looks.   What if  the scanned
        macs have changed?  Further, what if there is another MTSN with 
        the new macs (mb error or board swap?) already in existance.  
        This function deals with these scenarios.

        If the given mtsn already exists, tarball it and copy the 
        tarball into the MTSN.

        If there is a tarball to add, then extract the tester.log

        @param mtsn         Basename of the MTSN that is our intended target
        @param source_path  A full path to the new MTSN content
        """
        mtsn_path = self.get_mtsn_path(mtsn)
        mtsn_fetched = set()

        ### First, recall the targeted MTSN from any l1
        if osp.exists(mtsn_path):
            result = self.move_mtsn_from_l1_to_l2(mtsn, allow_cleanup=True)
            if result:
                mtsn_fetched.add(result[0])

        ### For all MAC in the new path, make sure any MTSN
        ### associated are recalled
        new_mac_list = get_mac_list(source_path)
        for mac in new_mac_list:
            result = self.move_mtsn_for_mac_from_l1_to_l2(mac)
            if result != None:
                mtsn_fetched.add(result[0])

        ## tarball the previous MTSN
        if osp.exists(mtsn_path):
            with contextlib.suppress(MTSNFileMissing):
                self.tarball_mtsn(osp.basename(mtsn_path))

        ###  Remove any mac files found in macinuse or MTSN for the new macs
        for mac in new_mac_list:
            self.remove_mac(mac)

        ### important we get the destination path correct so we don't 
        ### delete the entire /dfcxact/mtsn by mistake
        assert len(mtsn) == 8, 'mtsn name ' + \
            '{} does not look correct, should be 8 chars long'.format(mtsn)

        ### if our target path exists, then delete all associated macinuse
        ### (and only the macinuse files), tarball the existing MTSN,
        ### and then delete the target path
        if osp.exists(mtsn_path):
            for mac in get_mac_list(mtsn_path):
                macinuse = osp.join(self.macinuse_dir, mac + '.mac')
                try:
                    os.unlink(macinuse)
                except FileNotFoundError:
                    pass

            try:
                shutil.rmtree(mtsn_path)
            except:
                cmd = 'sudo -n /bin/chown -R l2plclient /dfcxact/mtsn'
                rc = os.system(cmd)
                if rc != 0:
                    raise CommandFail(rc, cmd, msg='Cannot run cmd: [{cmd}]')

                shutil.rmtree(mtsn_path)

        ### rename the given path to the target
        os.rename(source_path, mtsn_path)

        
        ### if there is a tarball for our mtm/sn then extact the tester.log and logdata.utp from rt/
        info = get_id_info(mtsn_path)
        tarball = self.find_latest_tarball(mtm=info['mtm'],
                                           serial=info['sn'])
        if tarball:
            for fname in ('./rt/tester.log', './rt/logdata.utp', './rt/errors.log', './rt/mem_config.log'):
                extract_command = 'tar -O -zxf {} {}'.format(tarball, fname)
                msg = 'Extract {}: {}'.format(fname, extract_command)
                p = subprocess.run(extract_command, shell=True, 
                                   cwd=mtsn_path,
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE)
                out = p.stdout.decode()
                if p.returncode:
                    if 'Not found in archive' in p.stderr.decode():
                        log.info('{} => NOT FOUND'.format(msg))
                    else:
                        raise CommandFail(p.returncode, p.args, out, p.stderr, msg='tar extraction of {fname} from {tarball} failed for unkown reason:\n{stderr}',
                                          fname=fname, tarball=tarball)
                else:
                    log.info('{} => Extracted'.format(msg))
                    now = time.strftime( '%y%m%d.%H%M%S', time.localtime())
                    os.makedirs(osp.join(mtsn_path, 'rt'), exist_ok=True)
                    with open(osp.join(mtsn_path, fname), 'w') as fh:
                        fh.write(out)
                        fh.write('\n\n#------------------------- Rebuild Media '
                        '-------{}-----------------\n\n'.format(now))

            os.rename(tarball, osp.join(mtsn_path, osp.basename(tarball)))
            

        ### Create the macinuse files for the new MTSN
        self.create_macinuse_files(mtsn)

        
    def tarball_mtsn(self, mtsn):
        mtsn_path = self.get_mtsn_path(mtsn)
        info = get_id_info(mtsn_path)
        
        now = time.strftime( '%y%m%d.%H%M%S', time.localtime())
        tarball_basename = '{}.{}'.format(info['mtm'], info['sn'])
        tarball_path = osp.join(self.mtsn_parent_dir, 
                                '{}.{}.tgz'.format(tarball_basename,
                                                   now))
        cmd = 'tar -cvzf {} .'.format(osp.abspath(tarball_path))
        log.info('Tarring up mtsn dir: {}'.format(cmd))
        p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, cwd=mtsn_path)
        if p.returncode != 0:
            raise CommandFail(p.returncode, cmd, p.stdout.decode(), p.stderr.decode(), msg='Command {cmd} had error\n: {output}')


    def find_latest_tarball(self, mtm, serial):
        tarball_basename = '{}.{}.'.format(mtm, serial)
        tarballs = []
        for name in os.listdir(self.mtsn_parent_dir):
            if not name.startswith(tarball_basename):
                continue
            if not name.endswith('.tgz'):
                continue
            tarballs.append(osp.join(self.mtsn_parent_dir, name))

        if not tarballs:
            log.info('No latest tarball found')
            return None

        latest_tarball = sorted(tarballs)[-1]
        log.info('Found latest tarball: {}'.format(latest_tarball))
        return latest_tarball


    def deal_with_8d_macs(self, source_path):
        global VERIFY_12D
        VERIFY_12D = False   # This is a kludge to allow us to reuse fucntions that verify 12d macs
        for mac in get_mac_list(source_path):
            mac8 = mac[-8:]

            mtsn_path = self.find_mtsn_for_mac(mac8)
            if mtsn_path is None:
                continue

            log.info('Found a 8D MAC <{mac8}> with MTSN=<{mtsn_path}>'.format(**locals()))
            if not osp.exists(mtsn_path):
                # Found a case where $MTSN delete happened before the MAC file delete, we will clean these
                # 8D mac files up
                log.info('MTSN <{mtsn_path}> does not exist, removing 8D macs '
                             'associated with it'.format(**locals()))
                for f in (osp.join(self.where_dir, mac8 + '.mac'), osp.join(self.macinuse_dir, mac8 + '.mac')):
                    with contextlib.suppress(FileNotFoundError):
                        os.unlink(f)
                continue

            ## MTSN path exits, open the 8d.mac and verify the 12d listed matches
            mac8_path = osp.join(mtsn_path, '{}.mac'.format(mac8))
            if osp.exists(mac8_path):
                with open(mac8_path) as fh:
                    macs = get_mac_info(fh)['MACS']
                if mac not in macs:
                    log.warning('SKIP removal of 8D mac {mac8} because {mac8_path} does not contain {mac}'
                                    .format(**locals()))
                    continue

                self.move_mtsn_from_l1_to_l2(osp.basename(mtsn_path))

            ###  Remove any mac files found in macinuse or MTSN for the new macs
            self.remove_mac(mac8)
           
        VERIFY_12D = True


def remote_macinuse(host, mac=None, sn=None, mt=None):
    assert mac or sn, 'You must call remote_macinuse with mac or sn != None'

    if mac:
        fname = 'macinuse_by_mac'
        param = repr(mac)
        expected_media_path = '?'
    else:
        fname = 'macinuse_by_sn'
        param = repr(sn)
        expected_media_path = get_media_path(get_media_name(sn, mt))
    cmd = ['ssh', '-q', 'l2plclient@l2linux', REMOTE_MTSN_MANAGER_TEMPLATE.format(**locals(), **globals())]
    rc, stdout, stderr = SSHTool.run_cmd(cmd, password='L2client')
    if rc:
        raise SSHMacinuseException(rc, cmd, stdout, stderr, msg='SSH session to fetch remote macinuse file failed '
                                   '<{cmd}>\n\nSTDERR:\n{stderr}\n\nSTDOUT:\n{output}')

    return get_mac_info(io.StringIO(stdout))


def main():
    import argparse

    logging.getLogger().setLevel(os.environ.get('UTP_LOG_LEVEL', 'WARN'))
    logging.basicConfig()

    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch_mtsn', metavar='MTSN', type=str,
                        help='Fetch an MTSN back from the L1')

    args = parser.parse_args()

    mtsn_manager = MTSNManager()
    if args.fetch_mtsn:
        mtsn_path, macinuse = \
            mtsn_manager.move_mtsn_from_l1_to_l2(args.fetch_mtsn)
        logging.info('Fetched {}'.format(mtsn_path))
        logging.info('macinuse {}'.format(macinuse))
        
if __name__ == '__main__':
    exit(main())
