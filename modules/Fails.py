#!/usr/local/bin/python35
# -*- coding: utf-8 -*-
#
# @module Fails
#
# Define a set of common exceptions used when UTP test process fail.
#

import logging
from enum import Enum, unique
import hashlib

logger = logging.getLogger(__name__)


@unique
class ItemType(Enum):
    # Devices
    system = 'system'
    chassis = 'chassis'
    mb = 'motherboard'
    psu = 'powersupply'
    bp = 'backplane'
    mp = 'midplane'
    riser = 'riser'
    mech = 'mechanism'
    cpu = 'cpu'
    mem = 'mem'
    hdd = 'hdd'  # hdd, ssd, nvme (Non-Volatile Memory Express)
    odd = 'opticaldisk'  # odd, tape
    pci = 'pci'  # PCI, PCIe
    nic = 'ethernetcard'  # nic, fc (fiber channel), ib (infiniband)
    hba = 'satacontroller'
    raid = 'raid'
    raidc = 'raidcontroller'
    switch = 'switch'  # nework switch
    phy = 'phy'  # Physical layer of OSI
    ml2 = 'ml2'
    m2 = 'm2'
    usb = 'usb'
    i2c = 'i2c'
    bios = 'bios'  # bios, uefi
    bmc = 'bmc'
    imm = 'imm'  # Integrated Management Module (imm), XClarity Controller (xcc)
    cmm = 'cmm'  # Chassis Management Module
    tpm = 'tpm'  # Trusted Platform/Cryptography Module - tpm, tcm
    me = 'me'  # Intel Management Engine
    fpga = 'fpga'
    cable = 'cable'  # USB Cable, I2C Cable, etc
    rtc = 'rtc'
    battery = 'battery'
    thermal = 'thermal'  # Fan, Voltage, Temperature
    led = 'led'
    rs232 = 'rs232'
    iboot = 'iboot'

    # Non-devices
    notfound = 'notfound'
    perm = 'permission'
    auth = 'auth'
    dhcp = 'dhcp'
    socket = 'socket'
    seq = 'sequence'
    itac = 'itac'
    git = 'git'
    ssh = 'ssh'
    http = 'http'
    stream = 'stream'
    tunnel = 'tunnel'
    console = 'console'
    ipmi = 'ipmi'
    redfish = 'redfish'
    rc = 'rc'  # return code (command fail)
    osboot = 'osboot'
    mtsnget = 'mtsnget'
    file = 'file'
    uwip = 'uwip'
    mcelog = 'mcelog'
    parts = 'parts'
    assert_ = 'assert'
    code = 'code'
    data = 'data'
    process = 'process'
    uncaught = 'uncaught'
    rabbitmq = 'rabbitmq'
    tool = 'tool'  # Tool installation failure, SegFault, etc
    activation_code = 'activation_code'
    mysql = 'mysql'
    websocket = 'websocket'

    # Other
    other = 'other'
    null = 'null'


def _pickle(cls, kwargs, *args):
    """! Called to create instance of cls when unpickling.
    """
    return cls(*args, **kwargs)


class Fail(Exception):
    """! Base class for all UTP test process related fails.
    """
    _ARGS = ('item', 'msg')

    def __init__(self, item, msg, **kwargs):
        """! Initialize this fail object.

        @param item: a brief description of device type associated with this fail.
        @param msg: description of fail, in which keyword placeholders for
        msg.format is supported.

        @remark: all keyword parameters, will be saved as attributes to the fail object.
        They can also be referenced in the msg parameter and will be passed as keywords
        like msg.format(**kwargs)
        """
        if isinstance(item, ItemType):
            item = item.value
        elif item not in [x.value for x in ItemType.__members__.values()]:
            logger.warning("item '{}' in {}(...) call is not in ItemType, "
                           "PLEASE FIX!!".format(item, self.__class__.__name__))

        if len(item) > 20:
            logger.warning("item '{}' in {}(...) call has len > 20, truncating, "
                           "PLEASE FIX!!".format(item, self.__class__.__name__))
            item = item[:20]

        kwargs.update(item=item, msg=msg)
        if len(msg) > 1024:
            logger.warning('msg in {}(...) call has len > 1024, will have to truncate for DB, '
                           'PLEASE FIX!!'.format(self.__class__.__name__))
        self.kwargs = kwargs
        self.fail_msg = msg.format(**kwargs)

        super().__init__(self.fail_msg)
        self.__dict__.update(kwargs)

    def __reduce__(self):
        kwargs = self.__dict__.copy()
        args = tuple(kwargs.pop(x, None) for x in self._ARGS)
        return _pickle, (type(self), kwargs, *args)

    @property
    def hash(self):
        hash_str = self.__class__.__name__ + self.item + self.msg
        return hashlib.sha1(hash_str.encode()).hexdigest()[:6]


class FileNotFoundFail(Fail, FileNotFoundError):
    def __init__(self, filename, msg=None, **kwargs):
        if msg is None:
            msg = 'No such file or directory: {filename}'

        super().__init__(ItemType.file, msg, filename=filename, **kwargs)
        # Revise filename attribute for base class of FileNotFoundError
        self.filename = filename

    __str__ = Fail.__str__

    def __reduce__(self):
        return _pickle, (type(self), {'msg': self.msg}, self.filename)


class FileNotSearchedFail(Fail):
    def __init__(self, filename, search_paths):
        msg = 'No such file or directory: {filename}'
        super().__init__(ItemType.file, msg, filename=filename, search_paths=search_paths)

    def __str__(self):
        return '\n'.join(('Searched:', *self.search_paths, self.args[0]))

    def __repr__(self):
        return '{}{!r}'.format(self.__class__.__name__, (self.filename, self.search_paths))

    def __reduce__(self):
        return _pickle, (type(self), {}, self.filename, self.search_paths)


class BootFail(Fail):
    pass


class UnexpectedBootFail(BootFail):
    pass


class InfoFail(Fail):
    """! Class for wrong data got from command output, file, etc. Wrongs may be:
        missing(notfound), extra, mismatch, format, length, unknown...
    """
    _ARGS = ('msg',)

    def __init__(self, msg, item=ItemType.data, **kwargs):
        super().__init__(item, msg, **kwargs)


class FileInfoFail(InfoFail):
    """! Class for wrong data got from file.
    """

    def __init__(self, msg, filename=None, **kwargs):
        kwargs.update(filename=filename)
        super().__init__(msg, ItemType.file, **kwargs)


class CheckFail(Fail):
    """! Class for some function, item check error, e.g. Fan speed, XCC I2C
    """
    pass


class SELCheckFail(CheckFail):
    """! Class for BMC/XCC SEL(System Event Log) check error.
    """
    pass


class FWFail(Fail):
    """! Class for component firmware related error.
    """
    pass


class FWCheckFail(FWFail):
    """! Class for component firmware check error.
    """

    def __init__(self, item, msg, expected, actual, **kwargs):
        kwargs.update(expected=expected, actual=actual)
        super().__init__(item, msg, **kwargs)


class CommandFail(Fail):
    """! Class for run command error, which return a non-zero exit status.
    """
    _ARGS = ('returncode', 'cmd')

    def __init__(self, returncode, cmd, output=None, stderr=None, msg=None, **kwargs):
        if msg is None:
            msg = 'command {cmd!r} returned non-zero exit status: {returncode:d}'

        super().__init__(ItemType.rc, msg,
                         returncode=returncode, cmd=cmd, output=output, stderr=stderr, **kwargs)

    @property
    def stdout(self):
        return self.output

    @stdout.setter
    def stdout(self, value):
        self.output = value


class NonZeroTestcaseFail(CommandFail):
    """! Class for run test case error, which return a non-zero exit status.
    """

    def __init__(self, returncode, cmd, **kwargs):
        kwargs.setdefault('msg', 'test case {cmd!r} returned non-zero exit status {returncode:d}')
        super().__init__(returncode, cmd, **kwargs)


class TimeoutFail(Fail):
    def __init__(self, item, msg, timeout=None, **kwargs):
        kwargs.update(timeout=timeout)
        super().__init__(item, msg, **kwargs)


class SettingFail(Fail):
    """! Class for do some settings fail, e.g. BMC, UEFI settings.
    """
    pass


class SetupFail(Fail):
    """! Class for setup of a tool or process (e.g., fail to install RPM)
    """
    pass


class APIFail(Fail):
    """! Class for failing API result
    """
    pass

    
class ConfigFail(Fail):
    """! Class for check component configure error, for example: CPU(s)
    installed in UUT compared with parts ordered.
    """

    def __init__(self, item, msg=None, wrong=None, missing=None, extra=None, **kwargs):
        if msg is None:
            msg = 'configuration for {item} does not match order, locations: ' \
                  'wrong={wrong}, missing={missing}, extra={extra}'
        kwargs.update(wrong=wrong, missing=missing, extra=extra)
        super().__init__(item, msg, **kwargs)


class StressFail(Fail):
    """! Class for run-in testing error, e.g. MPX.
    """
    pass


class PreloadFail(Fail):
    """! Class for OS preload error.
    """
    pass


class RuntimeFail(Fail):
    """! Raised when a failure is detected that doesn't fall in any of other categories.
    """
    pass


class PlatformFail(Fail):
    """! Raised when a failure is with platform
    """
    pass


class SocketFail(Fail):
    """! Raised when a failed condiiton happens with a socket
    """
    pass


class UnexpectedPauseFail(RuntimeFail):
    """! Raised when a taks takes longer than it should (but completes)
    """
    _ARGS = ('item', 'msg', 'pause_start', 'pause_end', 'pause_delay')

    def __init__(self, item, msg, pause_start, pause_end, pause_delay):
        super().__init__(item, msg, pause_start=pause_start, pause_end=pause_end, pause_delay=pause_delay)


class AssertFail(RuntimeFail):
    """! This class is used to replace the builtin exception of AssertError.
    """
    _ARGS = ('msg',)

    def __init__(self, msg, item=ItemType.assert_, **kwargs):
        super().__init__(item, msg, **kwargs)


class NotImplementedFail(RuntimeFail):
    _ARGS = ('msg',)

    def __init__(self, msg=None, item=ItemType.code, **kwargs):
        if msg is None:
            msg = 'not implemented'

        super().__init__(item, msg, **kwargs)


class PythonFail(RuntimeFail):
    """! This is a wrapper for built-in exception raised by python.
    """

    def __init__(self, exc):
        self.__dict__.update(item=exc.__class__.__name__, msg=str(exc), **exc.__dict__)
        self.args = (self.msg,)
        for attr in ('__cause__', '__context__', '__suppress_context__', '__traceback__'):
            setattr(self, attr, getattr(exc, attr))

            
__builtins__.update(ItemType=ItemType)

# Import Fail class and its subclasses here into builtins namespace, so that
# they can be referenced directly without module name specified.
__builtins__.update(
    {k: v for k, v in globals().items() if isinstance(v, type) and issubclass(v, Fail)})
