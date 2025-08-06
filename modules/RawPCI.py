#!/usr/bin/python3.5
# -*- coding:utf-8 -*-
#
# @module RawPCI
# This module provide a class PCIDevice to access PCI device raw config space.
#

import os.path as osp
import logging
import re

import UTP

logger = logging.getLogger(__name__)

hex_digits = '[0-9a-fA-F]'
slot_pattern = r'(?:({0}+):)?({0}+):({0}+).({0}+)'.format(hex_digits)


class PCIDevice:
    """! A PCI device which is mainly used to access device config space.
    """
    _all_slots = None
    _bridges = None

    def __init__(self, bus=0, dev=0, func=0, domain=0, *, slot=None):
        if slot is not None:
            m = re.match(slot_pattern, slot.strip())
            if m:
                slot = [int(x, 16) for x in m.groups(0)]
            else:
                raise Exception('invalid slot number - {}'.format(slot))
        else:
            slot = [x if isinstance(x, int) else int(x, 16) for x in (domain, bus, dev, func)]
            print('###', slot)

        # restrict the value range for slot fields - domain, bus, dev, func
        names = ('domain', 'bus', 'device', 'function')
        max_values = (0xffffffff, 0xff, 0x1f, 7)
        for name, max_value, value in zip(names, max_values, slot):
            assert max_value >= value >= 0, 'invalid {} number - {}'.format(name, value)

        self.domain, self.bus, self.dev, self.func = slot

        self._config_space = self.get_config_space()
        if not self._config_space:
            raise Exception('###{}'.format(self.slot))

        self._caps = None

    def __str__(self):
        return self.slot

    def __getitem__(self, key):
        try:
            return self._config_space[key]
        except IndexError:
            if key < 64 or (self.is_express and key >= 4096) or (not self.is_express and key >= 256):
                raise
            elif key >= 256:
                self._config_space = self.get_config_space(part=2)
            elif key >= 64:
                self._config_space = self.get_config_space(part=1)

            return self._config_space[key]

    def get_config_space(self, part=0):
        """! Get PCI device config space.

        @param part: the part of config space.
            0 - standard (64 bytes)
            1 - whole (256 bytes)
            2 - extended (4096 bytes of PCIe)

        @return: bytes array of the config space.
        """
        cmd = ['lspci', '-Dn', '-s', self.slot]
        if part == 0:
            cmd.append('-x')
        elif part == 1:
            cmd.append('-xxx')
        elif part == 2:
            cmd.append('-xxxx')
        else:
            raise RuntimeFail(ItemType.pci,
                              'invalid part value - {part}, should be 0, 1 or 2', part=part)

        out = UTP.run(cmd)

        config_space = bytearray()
        last_offset = 0

        offset_re = re.compile(r'({0}?{0}0):\s+'.format(hex_digits))
        for line in out.splitlines():
            m = offset_re.match(line)
            if m:
                offset = int(m.group(1), 16)
                if offset < last_offset:
                    break

                start = len(m.group())
                config_line = bytes.fromhex(line[start:].strip())
                config_space.extend(config_line)
                last_offset = offset

        return memoryview(config_space)

    def word(self, offset=0, *, byteorder='little'):
        return int.from_bytes(self[offset:offset + 2], byteorder=byteorder)

    @property
    def capabilities(self):
        """! Get PCI device Capabilities List.

        @return: a dict which mapping from capability ID to 8 bit pointer in
        configuration space.
        """
        if self._caps is None:
            self._caps = {}
            if self[0x06] & 0x10:  # PCI Capabilities List bit(offset 06h, bit 4)
                cap_next = self[0x34]  # the initial capabilities pointer
                # The next capability pointer value of 0 indicate the last capability,
                # and the bottom two bits of it must be 00b.
                while cap_next != 0 and cap_next & 0x03 == 0:
                    cap_id = self[cap_next]
                    self._caps[cap_id] = cap_next
                    cap_next = self[cap_next + 1]

        return self._caps

    @property
    def is_express(self):  # is PCI Express?
        return self.capabilities.get(0x10, 0)  # PCI Express (10h)

    @property
    def slot(self):  # PCI Slot Number
        return '{:04x}:{:02x}:{:02x}.{:01x}'.format(self.domain, self.bus, self.dev, self.func)

    @property
    def vendor(self):  # Vendor ID
        return self.word(0)

    @property
    def device(self):  # Device ID
        return self.word(2)

    @property
    def svendor(self):  # Subsystem Vendor ID
        if self.header_type == 0:
            return self.word(0x2c)
        else:
            cap_ssid_offset = self.capabilities.get(0x0d, 0)  # PCI Bridge Subsystem Vendor ID (0Dh)
            if cap_ssid_offset:
                return self.word(cap_ssid_offset + 4)

    @property
    def sdevice(self):  # Subsystem ID
        if self.header_type == 0:
            return self.word(0x2e)
        else:
            cap_ssid_offset = self.capabilities.get(0x0d, 0)
            if cap_ssid_offset:
                return self.word(cap_ssid_offset + 6)

    @property
    def class_code(self):  # Class code
        return self.word(0x0a)

    @property
    def progif(self):  # register-level programming interface
        return self[9]

    @property
    def rev(self):  # Revision ID
        return self[8]

    @property
    def header_type(self):  # Header Type
        return self[0x0e] & 0x7f

    @property
    def bridge_buses(self):
        """! Return a tuple of primary, secondary and subordinate bus numbers
        for a PCI bridge device.
        """
        if self.header_type == 1:
            return self[0x18], self[0x19], self[0x1a]

    @property
    def functions(self):
        """! Return a list of functions which are all in this device.
        """
        pci_dev0 = self if self.func == 0 else __class__(self.bus, self.dev, 0, self.domain)
        func_list = [pci_dev0]
        if pci_dev0[0x0e] & 0x80:  # bit 7 is 1 -> the device has multiple functions
            for func in range(1, 8):
                try:
                    func_list.append(__class__(self.bus, self.dev, func, self.domain))
                except:
                    pass

        return func_list

    @property
    def physical_slot(self):
        """! Return the physical slot number attached to this port.
        """
        cap_express_offset = self.capabilities.get(0x10, 0)
        if cap_express_offset:
            func_type = self[cap_express_offset + 2] >> 4  # type of PCI Express function
            # downstream ports and slot implemented
            if func_type in (4, 6) and self[cap_express_offset + 3] & 0x01:
                return self.word(cap_express_offset + 0x16) >> 3

    @property
    def physical_slot_in(self):
        """! Return the physical slot number this device in.
        """
        domain, bus = self.domain, self.bus

        self.get_all_slots()
        if domain in self._bridges:
            domain_bridges = self._bridges[domain]
            if bus in domain_bridges:
                slot = domain_bridges[bus]
                bridge = __class__(*slot, domain)
                return bridge.physical_slot

    @property
    def path(self):
        """! Get PCI device path in PCI bus tree.

        @return: PCI device path which is concatenated from domain, via
        intermediate PCI-to-PCI bridges,and end with this device.

        @notes: considering the relative location of PCI devices, the bus number
        in PCI device path is otiose. In addition, PCI bus numbers may changed
        with system hardware updating - add a PCI bridge in particular.
        """
        domain, bus = self.domain, self.bus

        self.get_all_slots()
        domain_bridges = self._bridges.get(domain, {})

        dev_path = '{:02x}.{:01x}'.format(self.dev, self.func)
        while bus in domain_bridges:
            bridge_slot = domain_bridges[bus]
            dev_path = '{:02x}.{:01x}/{}'.format(bridge_slot[1], bridge_slot[2], dev_path)
            bus = bridge_slot[0]

        return '{:04x}:{:02x}/{}'.format(domain, bus, dev_path)

    @classmethod
    def get_all_slots(cls):
        """! Get slots information for all PCI devices.

        @return: a mapping from PCI domain to list of slots, the slot is tuple
        of PCI bus, dev, func, class code, secondary bus number(available for
        PCI-to-PCI bridge).
        """
        if cls._all_slots is None:
            cls._all_slots = {}
            cls._bridges = {}
            slot_re = re.compile(r'{}\s+({}+):'.format(slot_pattern, hex_digits))

            out = UTP.run(['lspci', '-Dn', '-d', 'cabc:'])
            for line in out.splitlines():
                m = slot_re.match(line)
                if m:
                    domain, *slot, cc = (int(x, 16) for x in m.groups())  # cc - Class Code
                    print('#####', cls._all_slots)
                    cls._all_slots.setdefault(domain, []).append(slot)
                    print('#####', cls._all_slots)

                    if cc == 0x0604:  # for PCI-to-PCI bridge, save the secondary bus number
                        bridge_buses = __class__(*slot, domain).bridge_buses
                        if bridge_buses:
                            cls._bridges.setdefault(domain, {})[bridge_buses[1]] = slot

        return cls._all_slots

    @classmethod
    def get_devices(cls, func=None):
        """! A generator which return each PCI device represented by this
        class object.

        @param func: if func is not None, return items for which func(item) is true,
        otherwise return all.
        """
        all_slots = cls.get_all_slots()
        for domain in all_slots:
            for slot in all_slots[domain]:
                pci_dev = __class__(*slot, domain)
                if func is None or func(pci_dev):
                    yield pci_dev


if __name__ == '__main__':
    for d in PCIDevice.get_devices():
        slot = d.physical_slot or ''
        slot_in = d.physical_slot_in or ''
        logger.info('{} {:04x}: {:04x}:{:04x} (path: {}, slot: {}, slot in: {})'.format(
            d, d.class_code, d.vendor, d.device, d.path, slot, slot_in))





