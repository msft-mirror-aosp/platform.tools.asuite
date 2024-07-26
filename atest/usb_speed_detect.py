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

import logging
import subprocess
from atest import atest_utils
from atest import constants
from packages.modules.adb.proto import adb_host_pb2


def verify_and_print_usb_speed_warning(device: adb_host_pb2.Device) -> bool:
  """Checks whether the connection speed is optimal for the given device.

  Args:
      device: The proto representation of a device.

  Returns:
      True if the warning was printed, False otherwise.
  """
  if (
      device.connection_type != adb_host_pb2.ConnectionType.USB
      or device.state != adb_host_pb2.ConnectionState.DEVICE
  ):
    return False

  # If a USB-2 is used with a USB-3 capable device, the speed will be
  # downgraded to 480 Mbps and never 12 Mbps, so this is the only case we
  # check.
  if (
      device.negotiated_speed == 480
      and device.negotiated_speed < device.max_speed
  ):
    _print_usb_speed_warning(
        device.serial, device.negotiated_speed, device.max_speed
    )
    return True
  return False


def _print_usb_speed_warning(
    serial: str, negotiated_speed: int, max_speed: int
):
  """Prints a warning about the device's operating speed if it's suboptimal.

  Args:
    serial: The serial number of the device.
    negotiated_speed: The negotiated speed (in Mbits per seconds) the device is
      operating at.
    max_speed: The maximum speed (in Mbits per seconds) of which the device is
      capable.
  """
  atest_utils.colorful_print(
      f'Warning: The device with serial {serial} is using'
      f' {_speed_to_string(negotiated_speed)} while'
      f' {_speed_to_string(max_speed)} capable. Check the USB cables/hubs.',
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
  }.get(speed, f'{speed:,} Mbps') or f'{speed:,} Mbps'


def get_device_proto_binary() -> adb_host_pb2.Device:
  """Run `adb track-devices --proto-binary` to fetch the device info.

  Returns:
     A Device object with the attributes of the given device.
  """
  if not atest_utils.has_command('adb'):
    return adb_host_pb2.Device()
  proc = subprocess.Popen(
      ['adb', 'track-devices', '--proto-binary'],
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
  )
  devices = None
  try:
    devices = adb_host_pb2.Devices.FromString(
        proc.stdout.read(int(proc.stdout.read(4).decode('utf-8'), 16))
    )
  except ValueError as ve:
    logging.debug(
        'Exception raised while running `adb track-devices`. USB speed will'
        ' not be read. Error: %s',
        ve,
    )
  # Make sure the process is terminated even though an exception is thrown.
  proc.terminate()
  # When multiple devices are available, only one will be used.
  return (
      devices.device[0] if devices and devices.device else adb_host_pb2.Device()
  )
