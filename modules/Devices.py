#!/usr/bin/python3.5

import os
import sys
import collections
import re

class PCISlot(dict):
    """PCI slot terminology is taken from lspci -D -vmm  format

    Contains attributes: domain, bus, slot, function
    """

    def __init__(self, *bares, **kw):
        if not kw and len(bares) == 1:
            self.load_string(bares[0])
        else:
            self.load(*bares, **kw)

    def load_string(self, value):
        """ Load slot info from a string

        Value must match this format exactly:
        HHHH:HH:HH.H
        Where H is a hex digit (0-f)
        """
        m = re.match(r'([0-9a-f]+):([0-9a-f]+):([0-9a-f]+)\.([0-9a-f]+)$', value, re.I)
        if m:
            domain, bus, slot, function = [int(x, 16) for x in m.groups()]
        else:
            m = re.match(r'([0-9a-f]+):([0-9a-f]+)\.([0-9a-f]+)$', value, re.I)
            if m:
                bus, slot, function = [int(x, 16) for x in m.groups()]
                domain = 0
            else:
                raise Exception('invalid format of pci slot: {}'.format(value))

        self.load(bus, slot, function, domain=domain)

    def load(self, bus, slot, function, domain=0x0000):
        assert isinstance(bus, int) and bus <= 0xFF
        assert isinstance(slot, int) and slot <= 0x1F
        assert isinstance(function, int) and function <= 7
        assert isinstance(domain, int) and domain <= 0xFFFFFFFF
        self['domain'] = domain
        self['bus'] = bus
        self['slot'] = slot
        self['function'] = function

    def pretty_repr(self, indent=0, sep=','):
        """ print in a prettier format

        With defaults:
        {'domain': 0x0000, 'bus': 0x00, 'slot': 0x12, 'function': 0x7}

        The beginning curly brace is always with first key/value,
        closing curly is with last key/value.   Use a sep=','
        to print all on one line.  The whole thing will be
        and indented according to the in indent value
        """
        return "{{'domain':0x{domain:04x}{sep} 'bus':0x{bus:02x}{sep} 'slot':0x{slot:02x}{sep} 'function':0x{function:x}}}".format(
            **self, sep=sep)

    def short_repr(self, domain=False):
        return "'{}{:02x}:{:02x}.{:x}'".format(
            '{:04x}:'.format(self.domain) if domain else '', self.bus,
            self.slot, self.function)

    def __str__(self, domain=False):
        return '{}{:02x}:{:02x}.{:x}'.format(
            '{:04x}:'.format(self.domain) if domain else '', self.bus,
            self.slot, self.function)

    __repr__ = pretty_repr


    ## Allow fetching/setting values as attributes:  x = device.Slot
    __getattr__ = dict.__getitem__

    def __cmp__(self, other):
        return self.__str__(domain=True).__cmp__(other.__str__(domain=True))

    def __eq__(self, other):
        return self.__str__(domain=True).__eq__(other.__str__(domain=True))

    def __hash__(self):
        return self['function']|self['slot']<<3|self['bus']<<8|self['domain']<<16


class GenericDevice(collections.MutableMapping):
    def __init__(self, description, slave=False, *bares, **kw):
        self.data = {}
        super().__init__(*bares, **kw)
        self.description = description
        self.slave = slave

    def __getattr__(self, name):
        _name = name.lower() if isinstance(name, str) else name
        if _name in self.data:
            return self.data.__getitem__(_name)
        else:
            raise AttributeError("'{}' object has no attribute '{}'".format(type(self).__name__, name))

    def __delitem__(self, name):
        name = name.lower() if isinstance(name, str) else name
        return self.data.__delitem__(name)

    def  __getitem__(self, name):
        name = name.lower() if isinstance(name, str) else name
        return self.data.__getitem__(name)

    def __iter__(self):
        return self.data.__iter__()

    def __len__(self):
        return self.data.__len__()

    def __setitem__(self, name, value):
        name = name.lower() if isinstance(name, str) else name
        return self.data.__setitem__(name, value)

    def __setattr__(self, name, value):
        name = name.lower() if isinstance(name, str) else name
        if name == 'data':
            super().__setattr__(name, value)
        else:
            self.data[name] = value

    def __copy__(self):
        new_obj = type(self)()
        new_obj.data.update(self.data)
        return new_obj


class PCIDevice(GenericDevice):
    """ Base class for a PCI device
    Info is stored with keys, with the example format
    only vendor, device are guaranteed to be set

    slot:0000:80:05.4
    class:0800
    vendor:8086
    device:2f2c
    svendor:1d49
    sdevice:0a00
    rev:02
    progif:20

    Note that if slot is given it must be a string that matches this format

    HHHH:HH:HH.H

    Where H is a hex digit (0-f).   Or it must be a PCISlot object.  If
    given in string format, the slot value will be converted to PCISlot
    before storing and will always be returned as PCISlot object.
    """
    digits = {'class': 4,
              'vendor': 4,
              'device': 4,
              'svendor': 4,
              'sdevice': 4,
              'rev': 2,
              'progif': 2}

    priority = ['class', 'vendor', 'device', 'slot', 'svendor',
                'sdevice', 'rev', 'physlot', 'progif']

    def __init__(self, vendor, device, svendor=0, sdevice=0, *bares, vendor_pn=None, **keywords):
        super().__init__(*bares, **keywords)
        self.vendor = vendor
        self.device = device
        self.svendor = svendor
        self.sdevice = sdevice
        self.vendor_pn = None

    def pretty_repr(self, indent=0, sep=',\n'):
        """ print in a prettier format

        With defaults:

        {'ProgIf':0x20,
         '....':....,
         ...
         '....':....}
        ^
        |
        `---  space

        The beginning curly brace is always with first key/value,
        closing curly is with last key/value.   Use a sep=','
        to print all on one line.  The whole thing will be
        indented according to the in indent value: each line
        will start with indent number of spaces
        """
        key_values = []
        for k in self.priority:
            if not k in self:
                continue
            v = self[k]
            if isinstance(v, int):
                repr_v = '0x{}'.format('{:x}'.format(v).zfill(self.digits[k]))
            elif k == 'Slot':
                repr_v = v.short_repr(domain=True)
            elif hasattr(v, 'pretty_repr'):
                repr_v = v.pretty_repr()
            else:
                repr_v = repr(v)
            key_values.append(repr(k) + ':' + repr_v)

        the_sep = sep + ' '
        result = '{{{}}}'.format(the_sep.join(key_values))

        if indent:
            return '\n'.join(' ' * indent + x for x in result.splitlines())
        else:
            return result

    def __setitem__(self, key, value):
        key = key.lower()
        if key in ('rev', 'progif'):
            assert isinstance(value, int) and value <= 0xFF
        elif key in ('physlot',):
            assert isinstance(value, str)
        elif key == 'slot':
            if isinstance(value, str):
                value = PCISlot(value)
            elif isinstance(value, PCISlot):
                value = PCISlot(**value)
            else:
                raise Exception('Slot value must be str or PCISlot type')
        if key in ('class', 'vendor', 'device', 'svendor', 'sdevice'):
            assert isinstance(value, int) and value <= 0xFFFF

        return self.data.__setitem__(key, value)

class PCIDeviceList(list):
    """ A list() with some extened methods
    """

    def get_pci_by_key(self, key, value, default=None):
        """ Get first  PCI record that has a key == value
            Returns default [None by default] if there is no match
        """
        for record in self:
            if key in record and record[key] == value:
                return record
        return default

    def get_pci_by_slot(self, slot):
        """ Get first PCI record that has a matching slot
            Returns a PCIDevice or raises PCILookupError
        """
        assert isinstance(slot, (str, PCISlot)), 'Parameter slot ' + \
                                                 'must be a subclass of str or PCISlot'

        if isinstance(slot, str):
            slot = PCISlot(slot)

        for pci_device in self:
            if pci_device.Slot == slot:
                return pci_device

        raise Exception('Cannot find a UUT PCI record for Slot == {}'.format(slot))

class FRUDevice(dict):
    """ Base class for a FRU device

    This object is basically a dictionary with a special init
    """

    def __init__(self, id_):
        super().__init__()
        assert isinstance(id_, str) and len(id_), \
            'id_ must a string with at least one char'
        self.id = id_

class FRULookup(dict): pass

class SNDevice(dict):
    """ This object is basically a dictionary
    """
    def __init__(self, description=''):
        super().__init__()
        self.description = description

class SNDeviceList(list):
    """ A list with some extra methods tacked on """
    def get_device_by_sn(self, key, value, default=None):
        """ Find first DMIDevice record with record[key] == value
        @param key     The key of the value to check
        @param value   The value to compare
        @param default If not mathcing record found return default
                       (defaults to None)

        @return a SNDevice or default value
        """
        for record in self:
            if key in record and record[key] == value:
                return record
        return default


