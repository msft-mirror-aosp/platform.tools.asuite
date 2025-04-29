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

"""Provides utils to select ATP test plans based on local change infos."""

import collections
import csv
import dataclasses
import functools
import json
import logging
import os
import pathlib
import re
import subprocess
from typing import Dict
from typing import List
from atest import atest_utils
from atest import constants
from atest.test_finders.smart_test_finder import local_info_collector


_DEVICE_PRODUCT_REGEX = re.compile(r'device product:(?P<product>[^\s]+)')
_DEVICE_REGEX = re.compile(r'device:(?P<device>[^\s]+)')

_ENABLED_ATP_TEST_PLANS = [
    'v2/android-platinum/suite/test-mapping-platinum-presubmit',
    'v2/android-platinum/suite/test-mapping-platinum-presubmit-sysui-1',
    'v2/android-platinum/suite/test-mapping-platinum-presubmit-sysui-2',
    'v2/android-virtual-infra/test_mapping/presubmit-avd',
    'v2/android-virtual-infra/test_mapping/presubmit-host',
    'v2/android-virtual-infra/test_mapping/presubmit-large-avd',
]


def _get_constants_path() -> str:
  """Gets the file path of all constants specific to smart test selection."""
  return str(
      pathlib.Path(constants.SMART_TEST_SELECTION_ROOT_PATH) / 'constants.json'
  )


def _get_lookup_table_path() -> str:
  """Gets the look up table path."""
  return str(
      pathlib.Path(constants.SMART_TEST_SELECTION_ROOT_PATH)
      / 'lookup_tables/project_to_tests.csv'
  )


@functools.cache
def _get_supported_device_targets() -> List[str]:
  """Return supported device targets."""

  try:
    with open(_get_constants_path(), 'r') as file:
      data = json.load(file)
      return data['supported_device_target']
  except (FileNotFoundError, json.JSONDecodeError) as err:
    atest_utils.print_and_log_warning(
        'Failed to get supported device targets: %s', err
    )
    return []


@functools.cache
def _get_compatible_matrix() -> Dict[str, List[str]]:
  supported_device_target = _get_supported_device_targets()
  return {
      'aosp_cf_x86_64_only_phone-trunk_staging-userdebug': (
          [
              'aosp_cf_x86_64_only_phone',
              'aosp_cf_x86_64_phone',
              'cf_x86_64_phone',
          ]
          + supported_device_target
      ),
      'aosp_cf_x86_64_phone-trunk_staging-userdebug': (
          ['aosp_cf_x86_64_phone', 'cf_x86_64_phone'] + supported_device_target
      ),
      'cf_x86_64_phone-trunk_staging-userdebug': (
          ['cf_x86_64_phone'] + supported_device_target
      ),
  }


@dataclasses.dataclass(frozen=True)
class DeviceInfo:
  """Presents device info: serial, product and device."""

  serial: str
  product: str
  device: str


# Presents the information of an ATP test.
AtpTestInfo = collections.namedtuple(
    'AtpTestInfo', ['name', 'target', 'branch']
)


def _get_filtered_test_names_from_lookup_table(names: str) -> List[str]:
  """Get filtered test names from lookup table, removing brackets and quotes."""
  return names.replace('[', '').replace(']', '').replace('"', '').split(',')


# TODO(b/405156412): Re-implement this function with Treehugger APIs when they
# are ready.
def _get_candidate_atp_tests(
    change_info: local_info_collector.ChangeInfo,
) -> set[AtpTestInfo]:
  """Get the list of ATP tests triggered by Treehugger in presubmit.

  Args:
    change_info: info of all changed files.

  Returns:
    ATP test information, including test name, target and branch.
  """
  tests = set()
  if change_info.branch != 'main':
    atest_utils.print_and_log_warning(
        'Smart test selection is currently restricted to git_main. Will exit.'
    )
    return tests

  with open(_get_lookup_table_path(), 'r', newline='') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    for row in csv_reader:
      if row['project'] == change_info.project and row['branch'] == 'git_main':
        tests.update([
            AtpTestInfo(name=name, target=row['target'], branch=row['branch'])
            for name in _get_filtered_test_names_from_lookup_table(row['names'])
        ])
  return tests


def _get_all_connected_devices() -> List[DeviceInfo]:
  """Return all connected devices."""
  # TODO(b/408251250): Switch to the new method to find connected devices.
  command = 'adb devices -l'
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

  Returns:
      The name of matched device.
  """
  all_devices = _get_all_connected_devices()
  logging.info('All connected devices: %s', all_devices)
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
      atest_utils.print_and_log_info(
          'ANDROID_SERIAL is not set. Set it to %s', device.serial
      )
      os.environ[constants.ANDROID_SERIAL] = device.serial
      return device
  atest_utils.print_and_log_warning(
      f'Can not find a device that matches the lunch target {target_product}.'
      ' Available devices are:'
  )
  for device in all_devices:
    atest_utils.print_and_log_warning(f'{device}')

  return None


def get_selected_atp_tests(change_info: local_info_collector.ChangeInfo):
  """Based on changed file details, get selected ATP tests."""
  candidate_tests = _get_candidate_atp_tests(change_info)
  logging.info('Candidate ATP tests: %s', candidate_tests)
  if not candidate_tests:
    return []

  matched_device = get_matched_device()
  if not matched_device:
    atest_utils.print_and_log_warning(
        'No matched device connected, and no ATP tests are selected.'
    )
    return []

  android_serial = matched_device.serial
  try:
    logging.debug('Disabling the ADB verification of device %s', android_serial)
    subprocess.check_output(
        f'adb -s {android_serial} shell settings put global'
        ' package_verifier_user_consent -1',
        shell=True,
    )
  except subprocess.CalledProcessError as err:
    atest_utils.print_and_log_warning(
        'Failed to disable the ADB verification of devices %s. Error: %s',
        matched_device,
        err,
    )

  selected_atp_tests = []
  for test in candidate_tests:
    if (
        test.name in _ENABLED_ATP_TEST_PLANS
        and matched_device
        and matched_device.product
        in _get_compatible_matrix().get(test.target, [])
    ):
      selected_atp_tests.append(test)

  return selected_atp_tests
