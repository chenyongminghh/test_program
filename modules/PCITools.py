#!/usr/bin/python3.5

from contextlib import suppress
import logging 
logger = logging.getLogger(__name__)

import UTP
import Devices
import RawPCI

pci_device_list = None

def clear_cache():
    pci_device_list = None

def get_pci_devices(only_mlu290=False):
    """ Run lspci and parse output into PCIDevice records """
    global pci_device_list
    if not pci_device_list:
        lspci_cmd = ['lspci', '-knDvmm']
        if only_mlu290:
            lspci_cmd = ['lspci', '-knDvmm', '-d', 'cabc:0290']
        content = UTP.run(lspci_cmd)
        devices = Devices.PCIDeviceList()
        info = {}
        for line in content.splitlines():
            logger.debug(line)
            line = line.strip()
            if not line:
                info.setdefault('vendor_pn', None)
                devices.append(Devices.PCIDevice(0,0,0,0,'UUT Generated Part'))
                # There will haven't subsytem IDs in the output of 'lspci -knDvmm' for PCI bridge, 
                # we can get it from PCI capability - PCI Bridge Subsystem Vendor ID (0Dh)
                if 'SVendor' not in info and 'SDevice' not in info:
                    pci_dev = RawPCI.PCIDevice(slot=info['Slot'])
                    info.update(SVendor=pci_dev.svendor or 0, SDevice=pci_dev.sdevice or 0)

                devices[-1].update(info)
                info = {}
            else:
                key, value = line.split(':', 1)
                ## assume value is hex string, otherwise save only as string
                ## Known exception is PhySlot which should be left as string
                try:
                    if key in ('PhySlot',):
                        info[key] = value.strip()
                    else:
                        info[key] = int(value.strip(), 16)  
                except ValueError:
                    info[key] = value.strip()

        # Run through all the devices and get a description
        # It would be great to use the vendor/device[/subvendor/subdevice]
        # to look up the part in pn.dat records
        # For now just get the info from lspci

        # create a lookup of slot -> desciptions
        slot_to_description = {}
        content = UTP.run(['lspci', '-D'])
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            slot, description = line.split(None, 1)
            slot_to_description[slot] = description


        for pci in devices:
            slot = pci.Slot.__str__(domain=True)
            if slot in slot_to_description:
                pci.description = slot_to_description[slot]
            
        pci_device_list = devices

    return pci_device_list


def get_bus_slots(pci_part, bdf_filter=(None, None, None)):
    """! Given a BasePart.PCI  object, return the PCISlot of any matching

    Note that if the pci_part defines secondary children, it may match parts that have
    have a super-set of secondary parts.  For example, if the pci_part has two secondary 
    children defined (typical of two port NIC), it may match the 4-port version of the part.
    Therefore, recommend if you find more than one matching pci_part, that you can eliminate
    all but the part with the longest secondary defined.

    @param pci_part   CommonBaseParts.PCI object: Only return PCSlots that have cards that match pci_part
    @param bdf_fuilter  tuple(int, int, int): Limit search to BUS(0):DEVICE(1).FUNCTION(2).  A value of None 
                        means match any. Default is to not limit: (None, None, None)

    @return list: of Deivces.PCISlot
    """
    import CommonBaseParts

    assert isinstance(pci_part, CommonBaseParts.PCI), \
        'get_bus_slots() requires one CommonBaseParts.PCI object parameter'

    found = []
    pci_devices = get_pci_devices()
    for pci in pci_devices:
        for index, value in enumerate((pci.slot.bus, pci.slot.slot, pci.slot.function)):
            if bdf_filter[index] is None:
                continue
            assert isinstance(bdf_filter[index], int), 'Param bdf_filter must be triple tuple of None or int'
                
            if bdf_filter[index] == value:
                continue
            break
        else:
            if at_address(pci.slot, '{:04x}:{:04x}'.format(pci_part.vendor, pci_part.device),
                          '{:04x}:{:04x}'.format(pci_part.svendor, pci_part.sdevice), 
                          pci_part.secondary):
                found.append(pci.slot)
            
    return found


def at_address(addr, vdid, svdid, secondary):
    """! Test the dmi_loc for the given PCI attributes 
    @return True or False
        
    Checks the vendor/device, subvendor/subdevice
    If those match, then checks the secondary devices 
    (vendor/device, svendor/sdevice) at each +bus, +dev, +func
    location.
    If all match, then returns True
    If any mismatch then immediately returns False
    """
    pcis = get_pci_devices()
    pci = pcis.get_pci_by_slot(addr)

    if not pci:
        logger.debug('Bus Address: {} not found'.format(dmi['Bus Address']))
        return False

    vendor, device  = [int(x, 16) for x in vdid.split(':')]
    svendor, sdevice  = [int(x, 16) for x in svdid.split(':')]

    if vendor != 0 and vendor != pci['vendor']:
        logger.debug('vendor mismatch UUT:{:04x} != PN:{:04x}'.format(pci['vendor'], vendor))
        return False

    if device != 0 and device != pci['device']:
        logger.debug('device mismatch UUT:{:04x} != PN:{:04x}'.format(pci['device'], device))
        return False

    if svendor != 0 and svendor != pci['svendor']:
        logger.debug('subvendor mismatch UUT:{:04x} != PN:{:04x}'.format(pci['svendor'], svendor))
        return False

    if sdevice != 0 and sdevice != pci['sdevice']:
        logger.debug('subdevice mismatch UUT:{:04x} != PN:{:04x}'.format(pci['sdevice'], sdevice))
        return False

    for child_info in secondary:
        if len(child_info) == 3:
            bus_offset, device_offset, function_offset =  child_info
            vd = vdid
            svd = svdid
        elif len(child_info) == 5:
            vd, svd, bus_offset, device_offset, function_offset =  child_info
        else:
            raise Exception('What?!')

        child_vendor, child_device = [int(x, 16) for x in vd.split(':')]
        child_svendor, child_sdevice = [int(x, 16) for x in svd.split(':')]
        child_bus = addr.bus + bus_offset
        child_slot = addr.slot + device_offset
        child_function = addr.function + function_offset
        child_slot_object = Devices.PCISlot(bus=child_bus, slot=child_slot, function=child_function)

        try:
            child_pci = pcis.get_pci_by_slot(child_slot_object)
        except:
            logger.debug('Child device not found @ {}'.format(child_slot_object))
            return False

        if child_pci.vendor != child_vendor:
            logger.debug('Child {} mismatch UUT:{:04x} != PN:{:04x}'.format('vendor', child_pci.vendor, 
                                                                            child_vendor))
            return False
        if child_pci.device != child_device:
            logger.debug('Child {} mismatch UUT:{:04x} != PN:{:04x}'.format('device', child_pci.device, 
                                                                            child_device))
            return False
        if child_svendor and child_pci.svendor != child_svendor:
            logger.debug('Child {} mismatch UUT:{:04x} != PN:{:04x}'.format('svendor', child_pci.svendor, 
                                                                            child_svendor))
            return False
        if child_sdevice and child_pci.sdevice != child_sdevice:
            logger.debug('Child {} mismatch UUT:{:04x} != PN:{:04x}'.format('sdevice', child_pci.sdevice, 
                                                                            child_sdevice))
            return False

    return True


def in_slot(slot, vendor, device, svendor, sdevice, secondary):
    """! Check whether or not the device in slot has the given IDs,
    subsystem IDs and secondary.
    """
    pci_dev = RawPCI.PCIDevice(slot=slot)
    dev_funcs = [(x.func, x.vendor, x.device, x.svendor, x.sdevice) for x in pci_dev.functions]

    part_funcs = [(0, vendor, device, svendor, sdevice)]
    for func_info in secondary:
        if len(func_info) == 3:
            bus_offset, dev_offset, func_offset = func_info
            assert bus_offset == 0 and dev_offset == 0 and 8 > func_offset > 0

            part_funcs.append((func_offset, vendor, device, svendor, sdevice))
        elif len(func_info) == 5:
            vendor_device, svendor_sdevice, bus_offset, dev_offset, func_offset = func_info
            assert bus_offset == 0 and dev_offset == 0 and 8 > func_offset > 0

            vendor1, device1 = [int(x, 16) for x in vendor_device.split(':')]
            svendor1, sdevice1 = [int(x, 16) for x in svendor_sdevice.split(':')]
            part_funcs.append((func_offset, vendor1, device1, svendor1, sdevice1))
        else:
            raise Exception('invalid function info in secondary - {}'.format(func_info))

    part_funcs.sort(key=lambda x: x[0])  # sort by PCI device function number
    dev_funcs.sort(key=lambda x: x[0])

    if len(part_funcs) <= len(dev_funcs):
        for p_func, d_func in zip(part_funcs, dev_funcs):
            if p_func[0] == d_func[0]:  # PCI device function number
                for i, item in enumerate(('vendor', 'device', 'svendor', 'sdevice'), 1):
                    if p_func[i] != 0 and p_func[i] != d_func[i]:
                        break
                else:
                    continue

            break
        else:
            return True




