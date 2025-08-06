#!/usr/bin/env python3
import os
import sys
import time
import shutil
import logging
import argparse
import os.path as osp

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
tests_path = osp.join(testcode_path, 'tests')
utilities_path = osp.join(testcode_path, 'utilities')
sys.path.append(modules_path)
import UTP
import CAM

autostart_folder = osp.join(utilities_path, 'autostart')
start_utp_file = osp.join(tests_path, 'start_utp.sh')
variables_file = osp.join(utilities_path, 'variables')

def check_env():
    check_status = True
    if osp.exists('/etc/X11/default-display-manager'):
        logging.info('/etc/X11/default-display-manager exists')
        with open('/etc/X11/default-display-manager', 'r') as rf:
            context = rf.readlines()
        if context[0].strip().split('/')[-1] == 'lightdm':
            logging.info('display-manager lightdm check pass')
        else:
            logging.error('display-manager lightdm check fail')
            check_status = False
    else:
        logging.error('/etc/X11/default-display-manager not exists')
        check_status = False
    if not osp.exists(autostart_folder):
        logging.error('Not exists {}'.format(autostart_folder))
        check_status = False
    if not osp.exists(start_utp_file):
        logging.error('Not exists {}'.format(start_utp_file))
        check_status = False
    return check_status
    
def setup_lightdm(username):
    lightdm_context = ["[Seat:*]\n", "autologin-user={}\n".format(username)]
    if osp.exists('/etc/lightdm/lightdm.conf'):
        logging.info('Auto Login had been set')
        return True
    else:
        with open('/etc/lightdm/lightdm.conf', 'w') as wf:
            wf.writelines(lightdm_context)
        logging.info('Auto Login Setting success')
        return True

def setup_autotest(username):
    autotest_path = '/home/{}/.config/autostart'.format(username)
    if osp.exists(autotest_path):
        logging.info('Auto Running had been set')
        return True
    else:
        shutil.copytree(autostart_folder, autotest_path)
        if username == 'cambricon_test':
            change_to_cambricon_test()
        
        cmd_chown = 'sudo chown -R {}:{} {}'.format(username, username, autotest_path)
        UTP.run(cmd_chown, shell=True)
        
        cmd_chmod = 'sudo chmod -R 755 /home/{}/.config/autostart/gnome-terminal.desktop'.format(username)
        UTP.run(cmd_chmod, shell=True)
        logging.info('Auto Running Setting success')
        return True    

def change_to_cambricon_test():
    context_list = [
                    '[Desktop Entry]\n', 'Type=Application\n', 
                    'Exec=gnome-terminal --geometry=145x30+80+80 -x /home/cambricon_test/start_utp.sh\n',
                    'Hidden=false\n', 'NoDisplay=false\n', 'X-GNOME-Autostart-enabled=true\n', 'Name[en_US]=startup_utp\n',
                    'Name=startup_utp\n', 'Comment[en_US]=AutoRun\n', 'Comment=AutoRun\n']
    file_path = '/home/cambricon_test/.config/autostart/gnome-terminal.desktop'
    with open(file_path, mode='w') as wf:
        wf.writelines(context_list)

def chmod_testcode(username):
    cmd_chown = 'sudo chown -R {}:{} {}'.format(username, username, testcode_path)
    UTP.run(cmd_chown, shell=True)
    
    cmd_chmod = 'sudo chmod -R 755 {}'.format(testcode_path)
    UTP.run(cmd_chmod, shell=True)

def clean_testcode():
    logging.info('Cleaning all logfiles')
    
    logs_path = osp.join(testcode_path, 'logs')
    
    test_log = osp.join(testcode_path, 'test.log')
    error_log = osp.join(testcode_path, 'error.log')
    errors_log = osp.join(testcode_path, 'errors.log')
    tester_log = osp.join(testcode_path, 'tester.log')
    onfail_log = osp.join(testcode_path, 'onfail.log')
    logdata_log = osp.join(testcode_path, 'logdata.utp')
    sequence_log = osp.join(testcode_path, 'sequence.json')
    rawtester_log = osp.join(testcode_path, 'rawtester.log')
    saved_log = osp.join(testcode_path, 'saved.log')
    
    file_path_list = []
    CAM.get_all_path(logs_path, file_path_list)
    
    file_path_list.append(test_log)
    file_path_list.append(error_log)
    file_path_list.append(errors_log)
    file_path_list.append(tester_log)
    file_path_list.append(onfail_log)
    file_path_list.append(logdata_log)
    file_path_list.append(sequence_log)
    file_path_list.append(rawtester_log)
    file_path_list.append(saved_log)
    
    for file_name in file_path_list:
        if 'monitor_log' in file_name:
            continue
        if osp.exists(file_name):
            os.unlink(file_name)
            logging.info('removed {}'.format(file_name))
    CAM.del_dvt_package()
    UTP.run(['rm -rf {}/*'.format(logs_path)], shell=True)
    logging.info('All logs have been removed.')

def chown_file(file_path, username):
    UTP.run('sudo chown -R {}:{} {}'.format(username, username, file_path), shell=True)
    UTP.run('sudo chmod -R 755 {}'.format(file_path), shell=True)
    
def alter_line(file_name, old_str, new_line):
    logging.info('Update {}'.format(osp.basename(file_name)))
    with open(file_name, "r", encoding="utf-8") as f1:
        context_list = f1.readlines()
    with open("{}.bak".format(file_name), "w", encoding="utf-8") as f2:
        for line in context_list:
            if old_str in line:
                logging.info('Old Line: {}'.format(line.strip()))
                line = new_line + '\n'
                logging.info('New Line: {}'.format(line.strip()))
            f2.write(line)
    os.remove(file_name)
    os.rename("{}.bak".format(file_name), file_name)

def main(args):
    logging.info('Autotest Environment Setting', section=True)
    username = CAM.get_system_username()
    if not username:
        logging.error('Detect username error, please exec "pwd" check')
        raise Exception('Detect username error')
    
    local_flag = '/home/{}/autotest.local'.format(username)
    if args.local:
        if not osp.exists(local_flag):
            logging.info('Local host test, create {}'.format(local_flag))
            UTP.run(['touch {}'.format(local_flag)], shell=True)
            chown_file(local_flag, username)
    else:
        logging.info('Multi host autotest, remove {}'.format(local_flag))
        if osp.exists(local_flag):
            os.remove(local_flag)
    
    if osp.exists(local_flag):
        alter_line(osp.join(tests_path, 'start_utp.sh'), 'STV_PATH=', 'STV_PATH="{}"'.format(testcode_path))
        alter_line(osp.join(tests_path, 'mlu370_host.sh'), 'STV_PATH=', 'STV_PATH="{}"'.format(testcode_path))
        chown_file(osp.join(tests_path, 'start_utp.sh'), username)
        chown_file(osp.join(tests_path, 'mlu370_host.sh'), username)
    
    if check_env():
        setup_lightdm(username)
        setup_autotest(username)
        clean_testcode()
        shutil.copy(start_utp_file, '/home/{}/start_utp.sh'.format(username))
        shutil.copy(variables_file, '{}/variables'.format(testcode_path))
        chown_file('/home/{}/start_utp.sh'.format(username), username)
        chown_file('{}/variables'.format(testcode_path), username)
    else:
        raise Exception('Autotest Environment Requirements Check FAILED')
    return

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--local', action='store_true', help='local host test')
    args = parser.parse_args()
    sys.exit(main(args))
