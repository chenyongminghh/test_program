#!/usr/local/bin/python35
## @package CodeLink
# Functions for creating symbolic links to code.
#
# Main function is update_code_links
#
import os
import sys
import os.path as osp
import re
import logging
import hashlib
import subprocess
import shlex
from contextlib import suppress
import socket
import struct

import Misc
import Default
from Locations import LocalLocation, ORDER_ARGS, UTPFileNotFound
import IAm
import Helper

import Fails  # this will import all Fail classes and ItemType into builtins namespace

logger = logging.getLogger(__name__)

fail_on_bad_merge = False

L1_IP = None


def get_default_gateway():
    """! Return the default gateway (interface, mac, ip) directly from /proc.
    """
    with open("/proc/net/route") as fh:
        for line in fh:
            line = line.strip()
            if line:
                interface, destination, gateway, flags, *rest = line.split()
                if destination == '00000000' and int(flags, 16) & 2:
                    with open('/sys/class/net/{}/address'.format(interface)) as fh_addr:
                        mac = fh_addr.read().strip()
                    ip = socket.inet_ntoa(struct.pack("<L", int(gateway, 16)))
                    return interface, mac, ip


if IAm.on_type() == 'uut':
    try:
        with open('/proc/cmdline') as fh:
            cmdline = fh.read()

        m = re.search(r'BOOTIF=[0-9a-f]{2}((?:[-:][0-9a-f]{2}){6})', cmdline, re.I)
        if m:
            boot_mac = m.group(1)[1:].replace('-', ':')  # skip hardware type in BOOTIF
            default_gw = get_default_gateway()
            if default_gw and boot_mac == default_gw[1]:
                L1_IP = default_gw[2]
    except Exception:
        L1_IP = None


# Will dispatch the main git commands to run on L1 if we are on UUT. It can accelerate
# the code links creation
def git_run(cmd, *args, local=None, **kwargs):
    cwd = os.getcwd()
    if L1_IP and cwd.startswith(Default.WORKING_DIR):
        if not isinstance(cmd, str):
            cmd = ' '.join(map(shlex.quote, cmd))

        if cmd.startswith('git '):  # only for git command
            cmd = 'cd {} && {}'.format(shlex.quote(cwd), cmd)
            return Helper.ssh_run(cmd, L1_IP, 'root', 'passw0rd', timeout=180).stdout

    return local.run(cmd, *args, **kwargs)


def update_code_links(mt=None, model=None, sn=None, top='ORIGINAL.TOP', lcr_file=True):
    logger.debug('Setting up code links in {}'.format(os.getcwd()))

    # First we see if sandbox links need to be setup, if we set one up
    # for sanbox we will skip it later for the normal setup
    local = LocalLocation('.', 'local')
    variables = local.variables('variables')
    
    sandbox_links = []
    for v in variables:
        if v.startswith('sandbox.'):
            link_name = v[len('sandbox.'):]
            logger.debug('Found {}, linking {} to sandbox at {}'.format(
                    v, link_name, variables[v]))
            make_link(link_name, variables[v])
            sandbox_links.append(link_name)

    if mt is None or len(sandbox_links) == 3:
        assert 'product' in sandbox_links, 'Without a MT specified, '\
            'you must set the var sandbox.product'
        assert 'common' in sandbox_links, 'Without a MT specified, '\
            'you must set the var sandbox.common'
        assert 'platform' in sandbox_links, 'Without a MT specified, '\
            'you must set the var sandbox.platform'
        return

    if sn is None:
        sn = variables['SN']

    if lcr_file:
        import Pilot
        try:
            Pilot.create_lcr_files(sn=sn, mt=mt, model=model, top=top)
        except:
            if fail_on_bad_merge:
                raise
            import traceback
            logger.warning('Update of LCR files failed:\n{}'.format(traceback.format_exc()))

    for link, path in Misc.get_mtm_repos(mt, model).items():
        if link in sandbox_links:
            continue  # here is where we skip any links already made to sandbox
        link_repo(link, path)

        
def link_repo(name, repo):
    local = LocalLocation('.', 'local')
    repo_base = osp.basename(repo)
    lcr_file = '{}.lcr'.format(repo_base)
    try:
        with local.open_file(lcr_file, args=ORDER_ARGS, errors='replace') as fh:
            content = fh.read()
        logger.debug('LCR file {} found, parsing...'.format(lcr_file))
    except (UTPFileNotFound, FileNotFoundError):
        logger.debug('No LCR file {} found, assuming master'.format(lcr_file))
        content = 'current:\nrefs/heads/master'
        lcr_file = None

    merges, reverts = parse_lcr(repo, content, lcr_file)

    path, failed_merges, failed_reverts = create_working_dir_atomic(repo, merges=merges, reverts=reverts)

    if failed_merges or failed_reverts:
        # rewrite the LCR with the failed pilots or reverts commented out
        # otherwise we will rebuild the same working dir over and over
        if failed_merges:
            logger.warning('Disabling some broken merge commits: {}'.format(failed_merges))
        if failed_reverts:
            logger.warning('Disabling some broken reverts: {}'.format(failed_reverts))
        disable_pilots_or_reverts(repo, lcr_file, failed_merges, failed_reverts)
    
    make_link(name, path)

def disable_pilots_or_reverts(repo, lcr_file, disable_merges, disable_reverts, how='comment'):
    assert how in ('comment', 'remove')
    local = LocalLocation('.', 'local')
    with local.open_file(lcr_file, args=ORDER_ARGS, errors='replace') as fh:
        lines = fh.readlines()

    if not repo.endswith('.git'):
        repo += '/.git'

    current = None
    new_lines = []
    for oline in lines:
        line = oline.strip()

        if not line or line.startswith('#'):
            new_lines.append(oline)
            continue
        if line in ('current', 'recent:', 'pilot:'):
            new_lines.append(oline)
            current = line
            continue
        if current == 'recent:' and line.startswith('*revert*'):
            ref = line[len('*revert*'):].lstrip().split(None, 1)[0]
            if any(ref in x  for x in disable_reverts):
                if how == 'comment':
                    new_lines.append('#DISABLE ' + oline)
                else:
                    pass  # do not do include oline in new list
            else:
                new_lines.append(oline)
            continue
        if current == 'pilot:':
            assert not line.startswith('*revert*'), 'Cannot have a *revert* in pilot: section'
            ref = line.split(None, 1)[0]
            if any(ref in x  for x in disable_merges):
                if how == 'comment':
                    new_lines.append('#DISABLE ' + oline)
                else:
                    pass # do not include online in new list
            else:
                new_lines.append(oline)
            continue
        
        new_lines.append(oline)

    target_lcr = local.find_file(lcr_file, args=ORDER_ARGS)
    temp_lcr = '{}.{}'.format(target_lcr,os.getpid())

    with local.open_file(temp_lcr, args=None,  mode='w') as fh:
        fh.write(''.join(new_lines))
        
    local.run(['mv', '-f', temp_lcr, target_lcr])

def parse_lcr(repo, content, name=None):
    # name the working dir
    # do this in a content-addressable way
    # first, create a list of references to merge
    # second, a list of references to revert
    # get the short sha1 of each
    # name = '-'.join([('+'.join(merge_sha)] + revert_sha))
    # if len(name) > 50, then sha1 the whole thing and prepend a ~

    local = LocalLocation('.', 'local')

    if not repo.endswith('.git'):
        repo_try =  osp.join(repo, '.git')
        assert osp.exists(repo_try), 'repo parameter ' +\
            '{} does not look like a git repo'.format(repo)
        repo = repo_try

    here = False
    current = None
    revert_references = []
    pilot_references = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line == 'current:':
            here = current
            continue
        if line == 'recent:':
            here = revert_references
            continue
        if line == 'pilot:':
            here = pilot_references
            continue

        # Its a commit def
        if here is current:
            # current
            current = line.split(None, 1)[0]
        elif here is revert_references:
            # in recent section
            if line.startswith('*revert*'):
                revert_references.append(line[len('*revert*'):].lstrip().split(None, 1)[0])
        elif here is pilot_references:
            # in pilot section
            pilot_references.append(line.split(None, 1)[0])
        else:
            raise InfoFail("Syntax error, missing 'current:' heading'")

    assert current, 'Format problem: missing current: section'

    logger.debug('AS PARSED: current={}, revert={}, pilot={}'
                  .format(current, revert_references, pilot_references))
    # Convert all the references to short commit sha1s
    try:
        sha1_current = local.run(['git', '--git-dir', repo, 'rev-parse',
                                  '--short', current]).strip()
    except subprocess.CalledProcessError as e:
        raise CommandFail(e.returncode, e.args, e.stdout, e.stderr,
                          msg='Git reference <{current}>: Failed to de-reference: {cmd_err}', current=current, cmd_err=str(e)) from None

    pilot_shas = []
    for pilot_ref in pilot_references:
        cmd = ['git', '--git-dir', repo, 'rev-parse', '--short', pilot_ref]
        proc = local.runproc(cmd, log_stderr=False, universal_newlines=True)
        if proc.returncode:
            logger.warning('PILOT ref <{}> in LCR file <{}> not resolved, so SKIPPING\nRC:{} => {}'
                            .format(pilot_ref, name, proc.returncode, ' '.join(cmd)))
        else:
            pilot_shas.append((proc.stdout.strip(), pilot_ref))

    revert_shas = []
    for revert_ref in revert_references:
        cmd = ['git', '--git-dir', repo, 'rev-parse', '--short', revert_ref]
        proc = local.runproc(cmd, log_stderr=False, universal_newlines=True)
        if proc.returncode:
            logger.warning('REVERT ref <{}> in LCR file <{}> not resolved, so CANNOT revert\nRC:{} => {}'
                           .format(revert_ref, name, proc.returncode, ' '.join(cmd)))
        else:
            revert_shas.append((proc.stdout.strip(), revert_ref))

    logger.debug('FOUND COMMMTS: current={}, revert={}, pilot={}'
                  .format(sha1_current, revert_shas, pilot_shas))

    return [(sha1_current, current)] + pilot_shas, revert_shas

def create_working_dir_atomic(repo, merges, reverts):
    # Clone the repo in a tmpdir, merge the merges, revert the reverts
    # rename the tmpdir to the real name
    # Keep the tmpdir local to our eventual target and repo so we are sure
    # not to cross filesystems and loose the advantage of hardlink
    # and mv
    local = LocalLocation('.', 'local')

    os.makedirs(Default.WORKING_DIR, exist_ok=True)
    name = name_working_dir([x[0] for x in merges], [x[0] for x in reverts])
    target_name = osp.join(Default.WORKING_DIR, osp.basename(repo), name)

    if osp.exists(target_name):
        logger.debug('Working dir {} found, reusing'.format(target_name))
        with suppress(PermissionError):
            os.utime(target_name)  # update the modification time to show still in use
        return target_name, [], []

    if not osp.exists(osp.dirname(target_name)):
        os.mkdir(osp.dirname(target_name))

    assert name.find('/') == -1, 'name {} must be basename only'.format(name)
    assert merges, 'Must have at least one merge in list'

    actual_merges = []
    actual_reverts = []
    with Misc.InTmpDir(Default.WORKING_DIR):
        # clone
        git_run(['git', 'clone', repo, name], local=local, stderr=subprocess.STDOUT)

        with Misc.InDir(name):
            # reset to first merge
            git_run(['git', '--git-dir=.git', 'reset', '--hard', merges[0][0]], local=local,
                    stderr=subprocess.STDOUT)
            actual_merges.append(merges[0])

            # merge
            for merge_commit,merge_ref in merges[1:]:
                try:
                    git_run(['git', '--git-dir=.git', 'merge', merge_commit], local=local,
                            stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
                    actual_merges.append((merge_commit, merge_ref))
                except subprocess.CalledProcessError as e:
                    if fail_on_bad_merge:
                        logger.error(e.stdout)
                        raise
                    logger.warning('Merge of pilot <{}> for commit <{}> FAILED for following '
                                    'reason:\n{}\nSKIPPING {}'.format(merge_ref, merge_commit, e.output, merge_ref))
                    # reset the working dir to last good state
                    git_run(['git', '--git-dir=.git', 'reset', '--hard', 'HEAD'], local=local,
                            stderr=subprocess.STDOUT)
                    git_run(['git', 'clean', '-ffdx'], local=local, stderr=subprocess.STDOUT)
                    continue

            # revert
            for revert_commit, revert_ref in reverts:
                # determine if it's a merge commit or a regular
                # for merge commits use the -m 1 trick
                out = local.run(['git', '--git-dir=.git', 'log',  '--pretty=%P', '-n1', revert_commit])
                try:
                    if len(out.split()) > 1:
                        local.run(['git', '--git-dir=.git', 'revert', '--no-edit', '-m', '1', revert_commit],
                                     stderr=subprocess.STDOUT)
                    else:
                        local.run(['git', '--git-dir=.git', 'revert', '--no-edit', revert_commit],
                                     stderr=subprocess.STDOUT)
                    actual_reverts.append((revert_commit, revert_ref))
                except subprocess.CalledProcessError as e:
                    if fail_on_bad_merge:
                        logger.error(e.stdout)
                        raise
                    logger.warning('Revert of <{}>, commit <{}> FAILED for following '
                                    'reason, but ignoring:\n{}'.format(revert_ref, revert_commit, e.output))
                    # reset the working dir to last good state
                    local.run(['git', '--git-dir=.git', 'reset', '--hard', 'HEAD'], stderr=subprocess.STDOUT)
                    local.run(['git', 'clean', '-ffdx'], stderr=subprocess.STDOUT)
                    continue

        new_name = name_working_dir([x[0] for x in actual_merges], [x[0] for x in actual_reverts])
        new_target_name = osp.join(Default.WORKING_DIR, osp.basename(repo), new_name)
        # Its possible that another user is doing this at the same
        # time, so allow for that
        try:
            os.rename(name, new_target_name)
            logger.debug('Created working dir {}'.format(target_name))
        except OSError:
            # Beaten to the punch?  Assume yes if the target exists
            if not osp.exists(new_target_name):
                raise
            logger.debug('Working dir {} found, reusing'.format(new_target_name))

    with suppress(PermissionError):
        os.utime(new_target_name)  # update the modification time to show still in use

    return new_target_name, [x for x in merges if x not in actual_merges], \
        [x for x in reverts if x not in actual_reverts]

def name_working_dir(merges, reverts):
    name = '-'.join(['+'.join(merges)] + reverts)
    if len(name) > 250:
        hash = hashlib.sha1()
        hash.update(name.encode())
        name = '~{}'.format(hash.hexdigest())
    return name

def make_link(name, target):
    if osp.exists(name) and osp.islink(name) and os.readlink(name) == target:
        return

    logger.info('Creating new link {} -> {}'.format(name, target))

    os.symlink(target, str(os.getpid()), target_is_directory=True)
    os.rename(str(os.getpid()), name)
