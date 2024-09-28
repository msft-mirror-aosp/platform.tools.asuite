# Copyright 2024, The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Module that detects device attributes and USB speed using adb commands."""

import enum
import logging
import subprocess
from typing import NamedTuple
from atest import atest_utils
from atest import constants


@enum.unique
class UsbAttributeName(enum.Enum):
  NEGOTIATED_SPEED = 'current_speed'
  MAXIMUM_SPEED = 'maximum_speed'


class DeviceIds(NamedTuple):
  manufacturer: str
  model: str
  name: str
  serial: str
  address: str


def verify_and_print_usb_speed_warning(
    device_ids: DeviceIds, negotiated_speed: int, max_speed: int
) -> bool:
  """Checks whether the connection speed is optimal for the given device.

  Args:
      device_ids: Identifiers allowing a user to recognize the device the usb
        speed warning is related to.
      negotiated_speed: The current speed of the device.
      max_speed: The maximum speed that the given device is capable of.

  Returns:
      True if the warning was printed, False otherwise.
  """
  # If a USB-2 is used with a USB-3 capable device, the speed will be
  # downgraded to 480 Mbps and never 12 Mbps, so this is the only case we
  # check.
  if negotiated_speed == 480 and negotiated_speed < max_speed:
    _print_usb_speed_warning(device_ids, negotiated_speed, max_speed)
    return True
  return False


def _print_usb_speed_warning(
    device_ids: DeviceIds, negotiated_speed: int, max_speed: int
):
  """Prints a warning about the device's operating speed if it's suboptimal.

  Args:
    device_ids: Identifiers allowing a user to recognize the device the usb
      speed warning is related to.
    negotiated_speed: The negotiated speed (in Mbits per seconds) the device is
      operating at.
    max_speed: The maximum speed (in Mbits per seconds) of which the device is
      capable.
  """
  atest_utils.colorful_print(
      f'Warning: The {device_ids.manufacturer} {device_ids.model} device ('
      f'{device_ids.name}) with address {device_ids.address} and serial '
      f'{device_ids.serial} is using '
      f'{_speed_to_string(negotiated_speed)} while '
      f'{_speed_to_string(max_speed)} capable. Check the USB cables/hubs.',
      constants.MAGENTA,
  )


def _speed_to_string(speed: int) -> str:
  """Converts a speed in Mbps to a string."""
  return {
      480: 'USB-2 (480 Mbps)',
      5000: 'USB-3.0 (5,000 Mbps)',
      10000: 'USB-3.1 (10,000 Mbps)',
      20000: 'USB-3.2 (20,000 Mbps)',
      40000: 'USB-4.0 (40,000 Mbps)',
  }.get(speed, f'{speed:,} Mbps')


def _string_to_speed(speed_str: str) -> int:
  return {
      'UNKNOWN': 0,
      'high-speed': 480,
      'super-speed': 5000,
      'super-speed-plus': 10000,
  }.get(speed_str, 0)


def get_udc_driver_usb_device_dir_name() -> str:
  """Reads the directory where the usb devices attributes are stored.

  Returns:
      A string corresponding to the directory name.
  """
  return _adb_read_file('/config/usb_gadget/g1/UDC')


def get_udc_driver_usb_device_attribute_speed_value(
    speed_dir_name: str,
    attr_name: UsbAttributeName,
) -> int:
  """Reads the usb speed string from the device and returns the numeric speed.

  Args:
      speed_dir_name: name of the directory where the usb driver attributes are
        located.
      attr_name: The attribute to read from the device.

  Returns:
      An int corresponding to the numeric speed value converted from the udc
      driver attribute value. 0 is returned if adb is unable to read the value.
  """
  speed_reading = _adb_read_file(
      '/sys/class/udc/' + speed_dir_name + '/' + attr_name.value
  )
  return _string_to_speed(speed_reading)


def _adb_read_file(file_path: str) -> str:
  cmd = [
      'adb',
      'shell',
      'su',
      '0',
      f'cat {file_path}',
  ]
  try:
    logging.debug('Running command: %s', cmd)
    result = subprocess.check_output(
        cmd,
        encoding='utf-8',
        stderr=subprocess.STDOUT,
    )
    return result.strip()
  except subprocess.CalledProcessError as cpe:
    logging.debug(
        f'Cannot read directory; USB speed will not be read. Error: %s', cpe
    )
  except OSError as ose:
    logging.debug(f'Cannot read usb speed from the device. Error: %s', ose)
  return ''


def get_adb_device_identifiers() -> DeviceIds | None:
  """Fetch the user-facing device identifiers."""
  if not atest_utils.has_command('adb'):
    return None

  device_serial = _adb_run_cmd(['adb', 'shell', 'getprop', 'ro.serialno'])
  if not device_serial:
    return None

  device_address_resp = _adb_run_cmd(['adb', 'devices'])
  try:
    device_addresses = device_address_resp.splitlines()
    for line in device_addresses:
      if 'device' in line:
        device_address = line.split()[0].strip()
  except IndexError:
    logging.debug('No devices are connected. USB speed will not be read.')
    return None

  device_manufacturer = _adb_run_cmd(
      ['adb', 'shell', 'getprop', 'ro.product.manufacturer']
  )
  device_model = _adb_run_cmd(['adb', 'shell', 'getprop', 'ro.product.model'])
  device_name = _adb_run_cmd(['adb', 'shell', 'getprop', 'ro.product.name'])

  return DeviceIds(
      manufacturer=device_manufacturer,
      model=device_model,
      name=device_name,
      serial=device_serial,
      address=device_address,
  )


def _adb_run_cmd(cmd: list[str]) -> str:
  try:
    logging.debug(f'Running command: %s.', cmd)
    result = subprocess.check_output(
        cmd,
        encoding='utf-8',
        stderr=subprocess.STDOUT,
    )
    return result.strip() if result else ''
  except subprocess.CalledProcessError:
    logging.debug(
        'Exception raised while running `%s`. USB speed will not be read.', cmd
    )
  except OSError:
    logging.debug('Could not find adb. USB speed will not be read.')
  return ''
