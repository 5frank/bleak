
"""
Perform Bluetooth LE Scan.

macOS

Created on 2019-06-24 by kevincar <kevincarrolldavis@gmail.com>

"""

import logging
import asyncio
from asyncio.events import AbstractEventLoop
from typing import List

from plistlib import load as plist_load

from bleak.backends.corebluetooth import CBAPP as cbapp
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

logger = logging.getLogger(__name__)

async def __get_addr_from_CoreBluetoothCache():
    
    path = "/Library/Preferences/com.apple.Bluetooth.plist"
    try:
        with open(path, "rb") as f:
            plist = plist_load(f)
    except FileNotFoundError:
        logger.warning("{} do not exist".format(path))
        return {}

    if "CoreBluetoothCache" not in plist:
        logger.debug("No CoreBluetoothCache in {}".format(path))
        return {}

    cbcache = plist["CoreBluetoothCache"]  

    if cbcache is None:
        return {}

    uuid_to_addr = {}

    for devuuid, devinfo in cbcache.items():
        if "DeviceAddress" not in devinfo:
            continue

        addr = devinfo["DeviceAddress"]
        addr = addr.replace('-', ':')

        uuid_to_addr[devuuid] = addr

    return uuid_to_addr 

async def discover(
    timeout: float = 5.0, loop: AbstractEventLoop = None, **kwargs
) -> List[BLEDevice]:
    """Perform a Bluetooth LE Scan.

    Args:
        timeout (float): duration of scaning period
        loop (Event Loop): Event Loop to use

    """
    loop = loop if loop else asyncio.get_event_loop()

    devices = {}

    if not cbapp.central_manager_delegate.enabled:
        raise BleakError("Bluetooth device is turned off")

    scan_options = {"timeout": timeout}

    await cbapp.central_manager_delegate.scanForPeripherals_(scan_options)

    # CoreBluetooth doesn't explicitly use MAC addresses to identify peripheral
    # devices because private devices may obscure their MAC addresses. To cope
    # with this, CoreBluetooth utilizes UUIDs for each peripheral. We'll use
    # this for the BLEDevice address on macOS

    found = []

    peripherals = cbapp.central_manager_delegate.peripheral_list
    uuid_to_addr = await __get_addr_from_CoreBluetoothCache()

    for i, peripheral in enumerate(peripherals):
        devuuid = peripheral.identifier().UUIDString()
        if devuuid not in uuid_to_addr:
            logger.warning("Missing DeviceAddress for device {}".format(devuuid))
            continue # FIXME

        address = uuid_to_addr[devuuid]
        name = peripheral.name() or "Unknown"
        details = peripheral

        advertisementData = cbapp.central_manager_delegate.advertisement_data_list[i]
        manufacturer_binary_data = (
            advertisementData["kCBAdvDataManufacturerData"]
            if "kCBAdvDataManufacturerData" in advertisementData.keys()
            else None
        )
        manufacturer_data = {}
        if manufacturer_binary_data:
            manufacturer_id = int.from_bytes(
                manufacturer_binary_data[0:2], byteorder="little"
            )
            manufacturer_value = "".join(
                list(
                    map(
                        lambda x: format(x, "x")
                        if len(format(x, "x")) == 2
                        else "0{}".format(format(x, "x")),
                        list(manufacturer_binary_data)[2:],
                    )
                )
            )
            manufacturer_data = {manufacturer_id: manufacturer_value}

        found.append(
            BLEDevice(address, name, details, manufacturer_data=manufacturer_data)
        )

    return found
