#!/usr/bin/env python3
#
# Copyright 2025, The Android Open Source Project
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

from dataclasses import dataclass
import logging
import os
import re
import subprocess
from typing import List
from atest import atest_utils
from atest import constants


_DEVICE_PRODUCT_REGEX = re.compile('device product:(?P<product>[^\s]+)')
_DEVICE_REGEX = re.compile('device:(?P<device>[^\s]+)')


@dataclass(frozen=True)
class DeviceInfo:
  """Presents device info: serial, product and device."""

  serial: str
  product: str
  device: str


def _get_all_connected_devices() -> List[DeviceInfo]:
  """Return all connected devices."""
  # TODO(b/408251250): Switch to the new method to find connected devices.
  command = 'adb devices -l'
  list_result = []
  try:
    command_run_result = subprocess.check_output(
        command,
        shell=True,
    )
    list_result = command_run_result.strip().decode().splitlines()[1:]
  except subprocess.CalledProcessError as err:
    atest_utils.print_and_log_error(
        'Failed to get connected devices as command %s return error: %s',
        command,
        err,
    )
    return []

  device_infos = []
  for line in list_result:
    attrs = line.split()
    serial = attrs[0]

    product = ''
    device_product_match_result = _DEVICE_PRODUCT_REGEX.search(line)
    if device_product_match_result:
      product = device_product_match_result.group('product')

    device = ''
    device_match_result = _DEVICE_REGEX.search(line)
    if device_match_result:
      device = device_match_result.group('device')
    device_infos.append(
        DeviceInfo(serial=serial, product=product, device=device)
    )
  return device_infos


def get_matched_device() -> DeviceInfo:
  """Get the connected device matching the current environment variables.

  If the env var ANDROID_SERIAL is set, then both the match of serial and
  product is enforced. If ANDROID_SERIAL is not set, then only the match of
  product is enforced.
  """
  all_devices = _get_all_connected_devices()
  logging.info(f'All connected devices: {all_devices}')
  if not all_devices:
    # No device connected
    return None

  android_serial = os.environ.get(constants.ANDROID_SERIAL)
  target_product = os.environ.get(constants.ANDROID_TARGET_PRODUCT)
  if not target_product:
    atest_utils.print_and_log_warning(
        'Cannot find target product, have you done lunch?'
    )
    return None

  # 'ANDROID_SERIAL' is already set.
  if android_serial:
    for device in all_devices:
      if device.serial == android_serial:
        if device.product != target_product:
          atest_utils.print_and_log_warning(
              f'Device with configured ANDROID_SERIAL {android_serial} is not'
              ' aligned with the lunch target. Device target is:'
              f' {device.product} but lunch target is: {target_product}.'
          )
          return None
        else:
          return device
    atest_utils.print_and_log_warning(
        f'ANDROID_SERIAL is set to {android_serial} but can not find the device'
        ' with that serial.'
    )
    return None

  # 'ANDROID_SERIAL' is not set yet.
  for device in all_devices:
    if device.product == target_product:
      return device
  atest_utils.print_and_log_warning(
      'Can not find a device that matches the lunch target.'
  )
  return None
