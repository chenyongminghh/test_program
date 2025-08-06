#!/usr/bin/python3.5

import os
import os.path as osp
import sys
import time
import shlex
import logging
import datetime
import collections

testcode_path = osp.dirname(osp.dirname(osp.abspath(__file__)))
modules_path = osp.join(testcode_path, 'modules')
tables_path = osp.join(testcode_path, 'tables')
logs_path = osp.join(testcode_path, 'logs')
sel_ignore_file = osp.join(tables_path, "IGNORE.SEL")
sel_elist_ignore_file = osp.join(tables_path, "IGNORE.ESEL")
sys.path.append(modules_path)

import UTP
import FRU

MAX_RETRY_TIME = 60*6
IMMSELLogEntry = collections.namedtuple("IMMSELLogEntry", ("record_id", "record_time", "event_type", "event"))
IMMSELLogEntryElist = collections.namedtuple("IMMSELLogEntryElist", ("record_id", "record_time", "event_type", "event", "event_detail"))
class IMM:
    def __init__(self):
        self.imm_count = 1
        
        BMC_IP = UTP.get('BMC_IP', ['192.168.100.50', ''])
        if isinstance(BMC_IP, str) and BMC_IP.strip():
            self.imm_count = 1
            self.imm_info_sets = [{'IP': BMC_IP, 'username': 'admin', 'password': 'admin', 'ipmi_port': 623, 'ssh_port': 22, 'telnet_port': 23}]
        elif isinstance(BMC_IP, list) and len(BMC_IP)==2 and BMC_IP[0].strip() and BMC_IP[1].strip():
            self.imm_count = 2
            self.imm_info_sets = [{'IP': BMC_IP[0].strip(), 'username': 'admin', 'password': 'admin', 'ipmi_port': 623, 'ssh_port': 22, 'telnet_port': 23},
                                  {'IP': BMC_IP[1].strip(), 'username': 'admin', 'password': 'admin', 'ipmi_port': 623, 'ssh_port': 22, 'telnet_port': 23}]
        elif isinstance(BMC_IP, list) and BMC_IP[0].strip():
            self.imm_count = 1
            self.imm_info_sets = [{'IP': BMC_IP[0].strip(), 'username': 'admin', 'password': 'admin', 'ipmi_port': 623, 'ssh_port': 22, 'telnet_port': 23}]
        else:
            self.imm_count = 1
            self.imm_info_sets = [{'IP': '192.168.100.50', 'username': 'admin', 'password': 'admin', 'ipmi_port': 623, 'ssh_port': 22, 'telnet_port': 23}]
        
        try:
            self.detect_IMMs()
        except Exception as e:
            logging.info('Failed during detect IMM: Try to reset USB eth of IMM...')
            # the first time failed maybe the usb network didn't set correctly.
            # so we reset the network of usb eth.
            self.reinit_network(self.imm_count)
            logging.info('-----re-detect IMM------')
            self.detect_IMMs()

    def detect_IMMs(self):
        BMC_IP = UTP.get('BMC_IP', ['192.168.100.50', ''])
        if isinstance(BMC_IP, list) and len(BMC_IP)==2 and BMC_IP[1].strip():
            return 2
        else:
            return 1
    
    def get_bmc_ip(self):
        BMC_IP = UTP.get('BMC_IP', ['192.168.100.50', ''])
        if isinstance(BMC_IP, str) and BMC_IP.strip():
            return [BMC_IP, '']
        elif isinstance(BMC_IP, list):
            return BMC_IP
        else:
            return ['192.168.100.50', '']
        
    def reinit_network(self, count, viatype='usb', timeout=160):
        pass

    def run_ipmi(self, imm_num, ipmi_cmd, imm_ip=None, timeout=None, proc=False, inband=False, **keywords):
        """
            Use this function to run ipmitool commands on the UUT.
            @param ipmi_cmd is a string containing the 'raw' ipmi command
        """
        logging.debug('*** Run Ipmi Command ***')

        if inband:
            ipmitool_cmd = 'ipmitool -d{} '.format(imm_num)
        else:
            imm_info_sets = self.imm_info_sets
            assert imm_info_sets, 'IMM list is empty!'
            imm = imm_info_sets[imm_num]
            if not imm_ip:
                imm_ip = imm['IP']
            ipmitool_cmd = 'ipmitool -I lanplus -H {} -U {} -P {} '.format(imm_ip, imm['username'], imm['password'])
        cmd = ipmitool_cmd + ipmi_cmd
        #logging.info('{}'.format(cmd))
        if proc:
            return UTP.runproc(shlex.split(cmd), timeout=timeout, **keywords)
        else:
            max_time = time.time() + MAX_RETRY_TIME
            while 1:
                proc = UTP.runproc(shlex.split(cmd), timeout=timeout, **keywords)
                if proc.returncode and keywords.get('check', True):
                    if proc.stderr and b'Invalid command' in proc.stderr:
                        raise Exception('ipmi command [{}] has returned nonzero and cmd looks to be invalid'.format(cmd))
                    if time.time() < max_time:
                        logging.warning('Command {} has failed, will sleep and retry'.format(cmd))
                        time.sleep(15)
                        continue
                    raise Exception('ipmi command [{}] has returned nonzero and retry period has expired'.format(cmd))
                else:
                    # Good return code but .... ('fru' in cmd or 'sdr' in cmd)
                    if proc.stderr and ('fru' in cmd):
                        # don't allow any stderr for these two commands, fru has been shown to return zero
                        # and dump an incomplete FRU record.  If there are error messages, assum they failed
                        if time.time() < max_time:
                            logging.warning('impi command {} has some error output, retrying...'.format(cmd))
                            time.sleep(15)
                            continue
                        raise Exception('ipmi command {} wont run without error output and retry period has expired'.format(cmd))
                    if keywords.get('universal_newlines', True):
                        return proc.stdout.decode(errors='replace').strip()
                    else:
                        return proc.stdout

    def get_imm_code_level(self, imm_num=0):
        """! This function returns the formatted BMC FW version.
        # Ex. response = '20 00 00 0a 51 bf 02 00 00 03 00 4b 50 42 54'
        # Ex. response = '20 81 00 01 02 bf 00 00 00 90 02 01 00 00 00'
        """
        response = self.run_ipmi(imm_num, 'raw 6 1')
        fw = response.split()
        major_level = int(fw[2][0], 16) * 10
        major_level += int(fw[2][1], 16)
        minor_level = int(fw[3][0], 16) * 10
        minor_level += int(fw[3][1], 16)
        return '{:d}.{:02d}'.format(major_level, minor_level)

    def get_imm_code_test_level(self, imm_num=0):
        """! This function returns the formatted BMC FW test version.
        # Ex. response = '20 81 00 01 02 bf 00 00 00 90 02 01 00 00 00'
        """
        response = self.run_ipmi(imm_num, 'raw 6 1')
        fw = response.split()
        major_level = int(fw[2][0], 16) * 10
        major_level += int(fw[2][1], 16)
        minor_level = int(fw[3][0], 16) * 10
        minor_level += int(fw[3][1], 16)
        
        aux_level_a = int(fw[14][1], 16)
        aux_level_b = int(fw[13][1], 16)
        aux_level_c = int(fw[12][1], 16)
        aux_level_d = int(fw[11][1], 16)
        aux_level = '{:d}{:d}{:d}{:d}'.format(aux_level_a, aux_level_b, aux_level_c, aux_level_d)
        return '{:d}.{:02d}.{}'.format(major_level, minor_level, aux_level)
    
    def get_bmc_fw_level_image1(self, imm_num=0):
        """! This function returns the formatted BMC FW version.
        # Ex. response = ' 00 0b'
        0x08 01 -- Image1 level ; 0x09 01 -- Image1 full level
        0x08 02 -- Image2 level ; 0x09 02 -- Image2 full level
        byte1: major level
        byte2: minor level
        byte3~6: aux level
        """
        response = self.run_ipmi(imm_num, 'raw 0x32 0x8f 0x09 0x01')
        fw = response.split()
        major_level = convert_hex_to_int(fw[0])
        minor_level = convert_hex_to_int(fw[1])
        
        aux_level_a = convert_hex_to_int(fw[2])
        aux_level_b = convert_hex_to_int(fw[3])
        aux_level_c = convert_hex_to_int(fw[4])
        aux_level_d = convert_hex_to_int(fw[5])
        aux_level = '{:d}{:d}{:d}{:d}'.format(aux_level_a, aux_level_b, aux_level_c, aux_level_d)
        return '{:d}.{:02d}.{}'.format(major_level, minor_level, aux_level)
    
    def get_bmc_fw_level_image2(self, imm_num=0):
        """! This function returns the formatted BMC FW version.
        # Ex. response = ' 00 0b'
        0x08 01 -- Image1 level ; 0x09 01 -- Image1 full level
        0x08 02 -- Image2 level ; 0x09 02 -- Image2 full level
        byte1: major level
        byte2: minor level
        byte3~6: aux level
        """
        response = self.run_ipmi(imm_num, 'raw 0x32 0x8f 0x09 0x02')
        fw = response.split()
        major_level = convert_hex_to_int(fw[0])
        minor_level = convert_hex_to_int(fw[1])
        
        aux_level_a = convert_hex_to_int(fw[2])
        aux_level_b = convert_hex_to_int(fw[3])
        aux_level_c = convert_hex_to_int(fw[4])
        aux_level_d = convert_hex_to_int(fw[5])
        aux_level = '{:d}{:d}{:d}{:d}'.format(aux_level_a, aux_level_b, aux_level_c, aux_level_d)
        return '{:d}.{:02d}.{}'.format(major_level, minor_level, aux_level)
    
    def clear_sel_log(self, imm_num=0, retry_times=2):
        """ Clear all contents of the SEL. """
        logging.info("*** Clear all contents of the SEL ***")
        assert retry_times > 0, "retry times should be greater than 0"
        
        resp_bool = False
        for _ in range(retry_times):
            resp = self.run_ipmi(imm_num, "sel clear")
            logging.info('resp : {}'.format(resp))
            if resp.find("Clearing SEL") != -1:
                time.sleep(2)
                resp_bool = True
                break
            else:
                err_msg = "*ERROR:* clear SEL failed (resp: {})".format(resp)
                logging.error(err_msg)
        return resp_bool
        
        
    def get_sel_elist_log(self, imm_num=0):
        """ Get SEL elist Entry."""
        sel_logs = []
        proc = self.run_ipmi(imm_num, 'sel elist', proc=True)
        if proc.returncode:
            raise Exception('The response issue from IPMI get SEL elist')
        elif proc.stdout == "":
            logging.info('No SEL Log record entry. The returncode is pass --> {}'.format(proc.returncode))
            return sel_logs
        else:
            resp = proc.stdout.decode(errors='replace')
        
        for line in resp.split('\n'):
            line = line.strip()
            #print('-->', line)
            if line == '':
                continue
            elif len(line.split('|')) == 6:
                rec_id = line.split('|')[0].strip()
                rec_time = line.split('|')[1].strip() + ' ' + line.split('|')[2].strip()
                event_type = line.split('|')[3].strip()
                event = line.split('|')[4].strip() + ' | ' + line.split('|')[5].strip()
                event_detail = " "
                sel_logs.append(IMMSELLogEntryElist(record_id=rec_id, record_time=rec_time, event_type=event_type, event=event, event_detail=event_detail))
            elif len(line.split('|')) == 7:
                rec_id = line.split('|')[0].strip()
                rec_time = line.split('|')[1].strip() + ' ' + line.split('|')[2].strip()
                event_type = line.split('|')[3].strip()
                event = line.split('|')[4].strip() + ' | ' + line.split('|')[5].strip()
                event_detail = line.split('|')[6].strip()
                sel_logs.append(IMMSELLogEntryElist(record_id=rec_id, record_time=rec_time, event_type=event_type, event=event, event_detail=event_detail))
            else:
                logging.error('Found not supported sel entry format --> {}'.format(line))
                raise Exception('Found not supported sel entry format --> {}'.format(line))
        return sel_logs
    
    def get_sel_log(self, imm_num=0):
        """ Get SEL list Entry."""
        sel_logs = []
        proc = self.run_ipmi(imm_num, 'sel list', proc=True)
        if proc.returncode:
            raise Exception('The response issue from IPMI get SEL list')
        elif proc.stdout == "":
            logging.info('No SEL Log record entry. The returncode is pass --> {}'.format(proc.returncode))
            return sel_logs
        else:
            resp = proc.stdout.decode(errors='replace')
        
        for line in resp.split('\n'):
            line = line.strip()
            #print('-->', line)
            if line == '':
                continue
            elif len(line.split('|')) == 6:
                rec_id = line.split('|', 4)[0].strip()
                rec_time = line.split('|', 4)[1].strip() + ' ' + line.split('|', 4)[2].strip()
                event_type = line.split('|', 4)[3].strip()
                event = line.split('|', 4)[4].strip()
                sel_logs.append(IMMSELLogEntry(record_id=rec_id, record_time=rec_time, event_type=event_type, event=event))
            else:
               raise Exception('Found not supported sel entry format --> {}'.format(line))
        return sel_logs

    def get_sel_ignore_list(self, ignore_file = sel_ignore_file):
        """ Get SEL Ignore list from tables."""
        ignore_sel_list = []
        
        with open(ignore_file, mode="r", encoding="utf-8") as file:
            for line in file.readlines():
                line = line.strip()
                if line == '':
                    continue
                else:
                    ignore_sel_list.append(line)
        return ignore_sel_list
    
    def get_sel_ignore_elist(self, ignore_file = sel_elist_ignore_file):
        """ Get SEL Ignore list from tables."""
        ignore_sel_elist = []
        
        with open(ignore_file, mode="r", encoding="utf-8") as file:
            for line in file.readlines():
                line = line.strip()
                if line == '':
                    continue
                else:
                    ignore_sel_elist.append(line)
        return ignore_sel_elist
    
    def bmc_sel_check(self, imm_num, ignore_list):
        sel_pass = True
        fail_entries = []
        
        sel_list = self.get_sel_log(imm_num)
        for sel_entry in sel_list:
            sel_record = sel_entry.event_type + ' | ' + sel_entry.event
            if sel_record not in ignore_list:
                fail_entries.append("Unexpected BMC SEL entry : {} | {} | {}".format(sel_entry.record_id, sel_entry.record_time, sel_record))
                sel_pass = False
        
        if not sel_pass:
            for ea in fail_entries:
                logging.error('{}'.format(ea))
            msg = 'Error: BMC <{}> Unexpected SEL entries Found'.format(imm_num)
            logging.error('{}'.format(msg))
        return sel_pass
    
    def bmc_sel_elist_check(self, imm_num, ignore_list):
        sel_pass = True
        fail_entries = []
        
        sel_elist = self.get_sel_elist_log(imm_num)
        for sel_entry in sel_elist:
            sel_record = sel_entry.event_type + ' | ' + sel_entry.event
            if sel_record not in ignore_list:
                fail_entries.append("Unexpected BMC SEL entry : {} | {} | {} | {}".format(sel_entry.record_id, sel_entry.record_time, sel_record, sel_entry.event_detail))
                sel_pass = False
        
        if not sel_pass:
            for ea in fail_entries:
                logging.error('{}'.format(ea))
            msg = 'Error: BMC <{}> Unexpected SEL entries Found'.format(imm_num)
            logging.error('{}'.format(msg))
        return sel_pass
    
    def bmc_fan_mode_get(self, imm_num=0):
        rtn_proc = self.run_ipmi(imm_num, 'raw 0x3a 0x15 0x0e', proc=True)
        if rtn_proc.returncode:
            logging.error('Get fan mode failed with returncode : {}'.format(rtn_proc.returncode))
            return 'other'
        response = rtn_proc.stdout.decode(errors='replace').strip()
        if response.split()[0].strip() == '00':
            fan_mode = 'table'
        elif response.split()[0].strip() == '01':
            fan_mode = 'pid'
        else:
            fan_mode = 'other'
        return fan_mode
    
    def bmc_fan_mode_set(self, imm_num=0, pid=False):
        expect_fan_mode = 'table'
        write_cmd = 'raw 0x3a 0x15 0x0f 0x00'
        if pid:
            expect_fan_mode = 'pid'
            write_cmd = 'raw 0x3a 0x15 0x0f 0x01'
        rtn_proc = self.run_ipmi(imm_num, write_cmd, proc=True)
        if rtn_proc.returncode:
            logging.error('Set fan mode failed with returncode : {}'.format(rtn_proc.returncode))
            return False
        time.sleep(1)
        if self.bmc_fan_mode_get(imm_num) != expect_fan_mode:
            logging.error('Set fan mode failed with expect not equal actual')
            return False
        logging.info('Set fan <{}> mode success'.format('pid' if pid else 'table'))
        return True
    
    def get_bmc_macaddr(self, imm_num=0):
        """! This function returns the formatted IMM MAC Address
        """
        response = self.run_ipmi(imm_num, 'raw 0x0c 0x02 1 5 0 0')
        response = response.replace(' ', '')
        imm_mac = '{:x}'.format(int(response[2:], 16))
        return '{}'.format(imm_mac.lower().zfill(12))

    def set_sel_time(self, imm_num=0, date=None):
        """! Sets the SEL time to a date specified (otherwise use now())
        """
        if not date:
            date = datetime.datetime.now().strftime('%m/%d/%Y %H:%M:%S')
        logging.info('Set BMC SEL Time: {}'.format(date))
        return self.run_ipmi(imm_num, 'sel time set "{}"'.format(date))
        
    def check_sel_time(self, imm_num=0):
        """! Return SEL time
        """
        current_sel_time = self.run_ipmi(imm_num, 'sel time get').strip()
        return datetime.datetime.strptime(current_sel_time, '%m/%d/%Y %H:%M:%S')
        
    def get_sdr_list(self, imm_num=0):
        """ Return SDR List
        """
        response = self.run_ipmi(imm_num, 'sdr list', timeout=480)
        if not response:
            raise RunCommandError('Failed to collect SDR Data from BMC!')
        return response
    
    def get_ipmi_sensors_list(self, imm_num=0):
        """! Get the sensors list, put it in /tmp/ipmi<2>_sensors.log
        """
        response = self.run_ipmi(imm_num, 'sensor list')
        if not response:
            raise RunCommandError('No response from IMM!')
        return response

    def read_bmc_mac(self, imm_num=0):
        """! This function returns the formatted bmc mac address.
             Command: ipmitool raw 0x3a 0x88 0x08 0x00
             Response: 50 98 b8 15 57 5d
             Return: 50:98:b8:15:57:5d
        """
        response = self.run_ipmi(imm_num, 'raw 0x3a 0x88 0x08 0x00').strip()
        return ':'.join(response.split())

    def read_board_sn(self, imm_num=0):
        """! This function returns the serial number of MLU290 BA.
             Command: ipmitool raw 0x3a 0x88 0x20 0x00
             Response: hex string as 34 31 32 30 30 33 33 30 30 30 31 36
             Return: 412003300016
        """
        response = self.run_ipmi(imm_num, 'raw 0x3a 0x88 0x20 0x00').strip()
        return convert_hex_to_ascii(response)
    
    def read_board_pn(self, imm_num=0):
        """! Command: ipmitool raw 0x3a 0x88 0x60 0x00
             Response: hex string as 43 4d 58 2d 42 42 31
             Return: CMX-BB1
        """
        response = self.run_ipmi(imm_num, 'raw 0x3a 0x88 0x60 0x00').strip()
        return convert_hex_to_ascii(response)
    
    def read_product_sn(self, imm_num=0):
        """! This function returns the serial number of MLU290 Spider system.
             Command: ipmitool raw 0x3a 0x88 0x30 0x00
             Response: hex string as 34 32 32 30 30 33 33 30 30 30 31 36
             Return: 422003300016
        """
        response = self.run_ipmi(imm_num, 'raw 0x3a 0x88 0x30 0x00').strip()
        return convert_hex_to_ascii(response)
    
    def read_product_pn(self, imm_num=0):
        """! Command: ipmitool raw 0x3a 0x88 0x90 0x00
             Response: hex string as 44 53 32 39 30 30 31 30
             Return: DS290010
        """
        response = self.run_ipmi(imm_num, 'raw 0x3a 0x88 0x90 0x00').strip()
        return convert_hex_to_ascii(response)
    
    def read_product_model(self, imm_num=0):
        """! This function returns the product model of MLU290 Spider system.
             Command: ipmitool raw 0x3a 0x88 0x80 0x00
             Response: hex string as 53 70 69 64 65 72
             Return: ascii string as 'Spider'
        """
        response = self.run_ipmi(imm_num, 'raw 0x3a 0x88 0x80 0x00').strip()
        return convert_hex_to_ascii(response)
    
    def read_board_mfg_date(self, imm_num=0):
        """! This function returns the board mfg datetime .
             Command: ipmitool raw 0x3a 0x88 0x80 0x00
             Response: hex string as 53 70 69 64 65 72
             Return: ascii string as 'Spider'
        """
        response = self.run_ipmi(imm_num, 'raw 0x3a 0x88 0x14 0x00').strip()
        hex_string = ''.join(reversed(response.split()))

        diff_minutes = convert_hex_to_int(hex_string)
        diff_seconds = diff_minutes * 60 + 820425600
        timeArray = time.localtime(diff_seconds)
        timeFormatted = time.strftime("%Y-%m-%d %H:%M:%S", timeArray)
        logging.debug('Read board mfg date : {}'.format(timeFormatted))
        return timeFormatted
    
    def write_bmc_mac(self, bmc_mac, imm_num=0):
        logging.info('Write BMC MAC         : {}'.format(bmc_mac))  
        hex_list = []
        for item in bmc_mac.lower().split(':'):
            hex_list.append('0x' + item)
        hex_string = ' '.join(hex_list)
        logging.debug('hex_string : {}'.format(hex_string))
        
        write_cmd = 'raw 0x3a 0x89 0x08 0x00 ' + hex_string
        logging.debug('Write BMC MAC         : ipmitool {}'.format(write_cmd))
        response = self.run_ipmi(imm_num, write_cmd, proc=True)
        if response.returncode:
            logging.error('Write BMC MAC failed with returncode : {}'.format(response.returncode))
            raise Exception('ipmitool failed')
        logging.info('Write BMC MAC         : {} success'.format(bmc_mac))
        return True
    
    def write_board_mfg_date(self, imm_num=0, mfg_date=None):
        #logging.info('Write board mfg date  : {}'.format(mfg_date))
        diff_minutes = diffMinutes('1996-01-01 00:00:00', mfg_date)
        hex_date_string = convert_int_to_hex(diff_minutes)
        logging.debug('hex_date_string : {}'.format(hex_date_string))
        
        write_cmd = 'raw 0x3a 0x89 0x14 0x00 ' + hex_date_string
        logging.debug('Write board MFG date : ipmitool {}'.format(write_cmd))
        response = self.run_ipmi(imm_num, write_cmd, proc=True)
        if response.returncode:
            logging.error('Write board MFG date failed with returncode : {}'.format(response.returncode))
            raise Exception('ipmitool failed')
        logging.info('Write board mfg date      : {} success'.format(mfg_date))
        return True
    
    def write_board_sn(self, board_sn, imm_num=0):
        #logging.info('Write Board SN        : {}'.format(board_sn))
        assert len(board_sn) == 12, 'The length of board sn should be 12'
        hex_string = convert_ascii_to_hex(board_sn)
        logging.debug('hex_string : {}'.format(hex_string))
        
        write_cmd = 'raw 0x3a 0x89 0x20 0x00 ' + hex_string
        logging.debug('Write Board SN        : ipmitool {}'.format(write_cmd))
        response = self.run_ipmi(imm_num, write_cmd, proc=True)
        if response.returncode:
            logging.error('Write Board SN failed with returncode : {}'.format(response.returncode))
            raise Exception('ipmitool failed')
        logging.info('Write Board SN            : {} success'.format(board_sn))
        return True
    
    def write_board_pn(self, board_pn, imm_num=0):
        assert len(board_pn), 'Board PN should not empty'
        hex_string = convert_ascii_to_hex(board_pn)
        logging.debug('hex_string : {}'.format(hex_string))
        
        write_cmd = 'raw 0x3a 0x89 0x60 0x00 ' + hex_string
        logging.debug('Write Board PN        : ipmitool {}'.format(write_cmd))
        response = self.run_ipmi(imm_num, write_cmd, proc=True)
        if response.returncode:
            logging.error('Write Board PN failed with returncode : {}'.format(response.returncode))
            raise Exception('ipmitool failed')
        logging.info('Write Board PN            : {} success'.format(board_pn))
        return True
    
    def write_board_product_name(self, board_product, imm_num=0):
        assert len(board_product), 'Board Product Name should not empty'
        hex_string = convert_ascii_to_hex(board_product)
        logging.debug('hex_string : {}'.format(hex_string))
        
        write_cmd = 'raw 0x3a 0x89 0x50 0x00 ' + hex_string
        logging.debug('Write Board Product Name : ipmitool {}'.format(write_cmd))
        response = self.run_ipmi(imm_num, write_cmd, proc=True)
        if response.returncode:
            logging.error('Write Board Product Name failed with returncode : {}'.format(response.returncode))
            raise Exception('ipmitool failed')
        logging.info('Write Board Product Name  : {} success'.format(board_product))
        return True
    
    def write_board_manufacturer(self, board_manufacturer, imm_num=0):
        assert len(board_manufacturer), 'Board Manufacturer should not empty'
        hex_string = convert_ascii_to_hex(board_manufacturer)
        logging.debug('hex_string : {}'.format(hex_string))
        
        write_cmd = 'raw 0x3a 0x89 0x40 0x00 ' + hex_string
        logging.debug('Write Board Manufacturer : ipmitool {}'.format(write_cmd))
        response = self.run_ipmi(imm_num, write_cmd, proc=True)
        if response.returncode:
            logging.error('Write Board Manufacturer failed with returncode : {}'.format(response.returncode))
            raise Exception('ipmitool failed')
        logging.info('Write Board Manufacturer  : {} success'.format(board_manufacturer))
        return True
    
    def write_product_sn(self, product_sn, imm_num=0):
        #logging.info('Write Product SN      : {}'.format(product_sn))
        assert len(product_sn) == 12, 'The length of product sn should be 12'
        hex_string = convert_ascii_to_hex(product_sn)
        logging.debug('hex_string : {}'.format(hex_string))
        
        write_cmd = 'raw 0x3a 0x89 0x30 0x00 ' + hex_string
        logging.debug('Write Product SN      : ipmitool {}'.format(write_cmd))
        response = self.run_ipmi(imm_num, write_cmd, proc=True)
        if response.returncode:
            logging.info('Write Product SN failed with returncode : {}'.format(response.returncode))
            raise Exception('ipmitool failed')
        logging.info('Write Product SN      : {} success'.format(product_sn))
        return True
    
    def write_product_pn(self, product_pn, imm_num=0):
        #logging.info('Write Product PN      : {}'.format(product_pn))
        assert len(product_pn), 'Product PN should not empty'
        hex_string = convert_ascii_to_hex(product_pn)
        logging.debug('hex_string : {}'.format(hex_string))
        
        write_cmd = 'raw 0x3a 0x89 0x90 0x00 ' + hex_string
        logging.debug('Write Product PN      : ipmitool {}'.format(write_cmd))
        response = self.run_ipmi(imm_num, write_cmd, proc=True)
        if response.returncode:
            logging.info('Write Product PN failed with returncode : {}'.format(response.returncode))
            raise Exception('ipmitool failed')
        logging.info('Write Product PN      : {} success'.format(product_pn))
        return True
    
    def write_product_model(self, product_model, imm_num=0):
        #logging.info('Write Product Model   : {}'.format(product_model))
        assert len(product_model), 'The length of product model should not be empty'
        hex_string = convert_ascii_to_hex(product_model)
        logging.debug('hex_string : {}'.format(hex_string))
        
        write_cmd = 'raw 0x3a 0x89 0x80 0x00 ' + hex_string
        logging.debug('Write Product Model   : ipmitool {}'.format(write_cmd))
        response = self.run_ipmi(imm_num, write_cmd, proc=True)
        if response.returncode:
            logging.info('Write Product Model failed with returncode : {}'.format(response.returncode))
            raise Exception('ipmitool failed')
        logging.info('Write Product Model   : {} success'.format(product_model))
        return True
    
    def enable_vpd_write(self, imm_num=0):
        enable_cmd = 'raw 0x3a 0x8b 0x56 0x50 0x44 0xaa'
        
        response = self.run_ipmi(imm_num, enable_cmd).strip()
        if response == '00':
            logging.info('VPD EEPROM Write Disable, running enable command.')
            self.run_ipmi(imm_num, enable_cmd)
        return True
    
    def get_fru_log(self, imm_num=0):
        response = self.run_ipmi(imm_num, 'fru', universal_newlines=False)  # We want at byt stream output
        if not response:
            raise Exception('No response from BMC!')
        return response
    
    def write_eeprom(self, part_name, raw_cmd, part_sn, imm_num=0):
        hex_string = convert_ascii_to_hex(part_sn.strip())
        logging.debug('hex_string : {}'.format(hex_string))
        
        write_cmd = raw_cmd + ' ' + hex_string
        logging.info('Write {}: ipmitool {}'.format(part_name.ljust(16, ' '), write_cmd))
        response = self.run_ipmi(imm_num, write_cmd, proc=True)
        if response.returncode:
            logging.info('Write {} failed with returncode : {}'.format(part_name, response.returncode))
            raise Exception('ipmitool failed')
        logging.info('Write {}: {} success'.format(part_name.ljust(16, ' '), part_sn))
        return True
    
    def write_eeprom_extra(self, part_name, raw_cmd, part_sn, imm_num=0):
        if part_sn == '' or part_sn == 'EMPTY':
            logging.info('Write {}: Skip due to SN<{}> is empty'.format(part_name.ljust(16, ' '), part_sn))
            return True
        write_cmd = raw_cmd
        logging.debug('Write {}: ipmitool {}'.format(part_name.ljust(16, ' '), write_cmd))
        response = self.run_ipmi(imm_num, write_cmd, proc=True)
        if response.returncode:
            logging.info('Write {} failed with returncode : {}'.format(part_name, response.returncode))
            raise Exception('ipmitool failed')
        logging.info('Write {}: {} success'.format(part_name.ljust(16, ' '), part_sn))
        return True
    
    def read_eeprom_sn(self, raw_cmd, imm_num=0):
        response = self.run_ipmi(imm_num, raw_cmd)
        response = response.replace('ff', '').strip()
        return convert_hex_to_ascii(response).strip()
        
    def set_fan_speed(self, imm_num=0, speed=''):
        """! Sets the FAN speed
             0x00:Auto
             0x01:20%
             0x02:50%
             0x03:75%
             0x04:100%
        """
        fan_speed_dict = {'Auto':'0x00', '20%':'0x01', '50%':'0x02', '75%':'0x03', '100%':'0x04'}
        if speed:
            logging.info('Set BMC <{}> FAN Speed: {}'.format(imm_num, speed))
            ipmi_cmd = 'raw 0x3a 0x15 0x01 ' + fan_speed_dict[speed]
            return self.run_ipmi(imm_num, ipmi_cmd)
    
    def set_fan_speed_mfg(self, imm_num=0, speed=''):
        """! Sets the FAN speed at MFG
        """
        if speed:
            logging.info('Set BMC <{}> FAN Speed: {}%'.format(imm_num, speed))
            ipmi_cmd = 'raw 0x3a 0x15 0x03 ' + convert_int_to_hex(int(speed))
            #print('ipmi_cmd:', ipmi_cmd)
            return self.run_ipmi(imm_num, ipmi_cmd)
    
    def led_on(self, led_name, imm_num=0):
        """! Light on LED
        """
        ipmi_cmd = 'raw 0x3a 0x87 ' + led_name + ' 0x01'
        return self.run_ipmi(imm_num, ipmi_cmd)
    
    def led_off(self, led_name, imm_num=0):
        """! Light off LED
        """
        ipmi_cmd = 'raw 0x3a 0x87 ' + led_name + ' 0x00'
        return self.run_ipmi(imm_num, ipmi_cmd)
    
    def led_status(self, led_name, imm_num=0):
        """! Return LED Status
        """
        ipmi_cmd = 'raw 0x3a 0x86 ' + led_name
        led_status = self.run_ipmi(imm_num, ipmi_cmd).strip()
        if led_status == "00":
            return "OFF"
        elif led_status == "01":
            return "ON"
        elif led_status == "02":
            return "BLINK"
        else:
            return "FALSE"
    
    def bmc_warm_reset(self, imm_num=0):
        """! Warm reset
        """
        ipmi_cmd = 'mc reset warm'
        return self.run_ipmi(imm_num, ipmi_cmd)
    
    def bmc_cold_reset(self, imm_num=0):
        """! Cold reset
        """
        ipmi_cmd = 'mc reset cold'
        return self.run_ipmi(imm_num, ipmi_cmd)
    
    def set_psu_cold_backup(self, imm_num, psu0, psu1):
        psu_dict = {'0x00':'master', '0x02':'slave'}
        logging.info('Set BMC <{}> PSU Cold Backup --> PSU0 : {}  PSU1 : {}'.format(imm_num, psu_dict[psu0], psu_dict[psu1]))
        ipmi_cmd = 'raw 0x3a 0x13 0x01 {} {} 0x00 0x00'.format(psu0, psu1)
        return self.run_ipmi(imm_num, ipmi_cmd)
    
    def set_psu_status(self, imm_num, psu0, psu1):
        psu_dict = {'0xa0':'off', '0xa1':'on'}
        logging.info('Set BMC <{}> PSU0 : {}  PSU1 : {}'.format(imm_num, psu_dict[psu0], psu_dict[psu1]))
        ipmi_cmd = 'raw 0x3a 0x13 0x03 {} {} 0x00 0x00'.format(psu0, psu1)
        return self.run_ipmi(imm_num, ipmi_cmd)
    
    def get_ba_mcu_version(self, imm_num):
        ba_mcu_ver = ''
        fru_lookup = FRU.parse_fru_logs(imm_num)
        board_extra = FRU.get_fru_value(fru_lookup, 'Builtin FRU Device', 'Board Extra')
        for extra in board_extra:
            if 'MCU Version' in extra:
                ba_mcu_ver = extra.split(':')[1].strip()
        return ba_mcu_ver
    
    def get_mc_mcu_version(self, imm_num, card_num):
        mc_mcu_ver = ''
        fru_lookup = FRU.parse_fru_logs(imm_num)
        product_version = FRU.get_fru_value(fru_lookup, 'MezzCard{}'.format(card_num), 'Product Version')
        mc_mcu_ver = product_version.split('-')[1].strip()
        return mc_mcu_ver
    
    def get_psu_version(self, imm_num, psu_num):
        psu_version = ''
        fru_lookup = FRU.parse_fru_logs(imm_num)
        psu_version = FRU.get_fru_value(fru_lookup, 'PSU{}'.format(psu_num), 'Product Version')
        return psu_version.strip()
    
    def get_psu_mfg(self, imm_num, psu_num):
        psu_manufacture = ''
        fru_lookup = FRU.parse_fru_logs(imm_num)
        psu_manufacture = FRU.get_fru_value(fru_lookup, 'PSU{}'.format(psu_num), 'Product Manufacturer')
        return psu_manufacture.strip()
    
    def get_psu_sn(self, imm_num, psu_num):
        psu_sn = ''
        fru_lookup = FRU.parse_fru_logs(imm_num)
        psu_sn = FRU.get_fru_value(fru_lookup, 'PSU{}'.format(psu_num), 'Product Serial')
        return psu_sn.strip()
    
    def restore_default(self, imm_num=0):
        restore_cmd_list = ['raw 0x32 0x83 0x03 0x00', 'raw 0x32 0x83 0x04 0x00', 'raw 0x32 0x66']
        restore_result = True
        for cmd in restore_cmd_list:
            response = self.run_ipmi(imm_num, cmd, proc=True)
            logging.info('BMC<{}> running <{}> with returncode {}'.format(imm_num, cmd, response.returncode))
            if response.returncode:
                logging.error('BMC<{}> running <{}> with returncode {} FAILED'.format(imm_num, cmd, response.returncode))
                logging.error('ipmitool failed')
                restore_result = False
        #logging.info('BMC<{}> Restore Factory Default PASSED'.format(imm_num))
        return restore_result
    
def convert_ascii_to_hex(ascii_string):
    """! Converts an ASCII string to a string of Hex chunks.
    @param ascii_string Example: 'CMX100' -> '0x43 0x4d 0x58 0x31 0x30 0x30'
    """
    logging.debug('*** Converting <{}> ASCII to Hex ***'.format(ascii_string))
    assert isinstance(ascii_string, str), "ERROR!: 'ascii_input' should be a string!"
    return ' '.join([hex(ord(char)) for char in ascii_string])

def convert_hex_to_ascii(hex_string):
    """! Converts a string of Hex chunks to an ASCII string.
    @param hex_string Example: '0x43 0x4d 0x58 0x31 0x30 0x30' -> 'CMX100'
    """
    logging.debug('*** Convert <{}> Hex to Ascii ***'.format(hex_string))
    assert isinstance(hex_string, str), "ERROR!: 'hex_input' should be a string of Hex numbers!"
    hex_num = ''
    return ''.join([chr(int(hex_num, 16)) for hex_num in hex_string.split()])

def convert_hex_to_int(hex_string):
    """! Returns an int number from a hex string.
    """
    logging.debug('*** Convert <{}> Hex to Int ***'.format(hex_string))
    assert isinstance(hex_string, str), "ERROR!: 'hex_input' should be a string of Hex numbers!"
    return int(hex_string, 16)

def convert_int_to_hex(int_string):
    """! Returns a hex string from an int number.
    """
    logging.debug('*** Convert <{}> Int to Hex ***'.format(int_string))
    assert isinstance(int_string, int), "ERROR!: 'int_string' should be a int numbers!"
    
    temp_list = []
    for index,item in enumerate(list(hex(int_string)[2:])):
        if (index)%2 == 0:
            temp_list.append("0x")
        temp_list.append(item)
        if (index+1)%2 == 0:
            temp_list.append(" ")
    temp_list_str = ''.join(temp_list).strip()
    logging.debug('original hex list:{}'.format(temp_list_str.split()))
    return ' '.join(reversed(temp_list_str.split()))

def diffMinutes(startTime, endTime):
    """! Calculate the number of minutes between two time points.
    @param startTime 1996-01-01 00:00:00
    @param endTime 2020-05-20 10:50:00
    """
    startTime = datetime.datetime.strptime(startTime, "%Y-%m-%d %H:%M:%S")
    endTime = datetime.datetime.strptime(endTime, "%Y-%m-%d %H:%M:%S")
    total_seconds = (endTime - startTime).total_seconds()
    mins = total_seconds // 60
    return int(mins)





