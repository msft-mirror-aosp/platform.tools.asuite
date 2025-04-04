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

"""Unittests for atp_test_selector."""

# pylint: disable=invalid-name

import subprocess
import unittest
from unittest import mock
from atest import constants
from atest.test_finders.smart_test_finder import atp_test_selector


_FAKE_ADB_OUTPUT = b"""List of devices attached
fake.ser.num1        device product:device_product_1 model:not_important_model1 device:some_device1 transport_id:1
fake.ser.num2        device product:device_product_2 model:not_important_model2 device:some_device2 transport_id:2
matched.ser.num       device product:matched_device_product model:not_important_model3 device:matched_device transport_id:3
"""


# pylint: disable=protected-access
class AtpTestSelectorUnittests(unittest.TestCase):
  """Unit tests for atp_test_selector.py"""

  @mock.patch('subprocess.check_output', return_value=_FAKE_ADB_OUTPUT)
  @mock.patch.dict(
      'os.environ',
      {
          constants.ANDROID_SERIAL: 'matched.ser.num',
          constants.ANDROID_TARGET_PRODUCT: 'matched_device_product',
      },
  )
  def test_get_matched_device_android_serial_set_and_product_matched(self, _):
    expected_device_info = atp_test_selector.DeviceInfo(
        serial='matched.ser.num',
        product='matched_device_product',
        device='matched_device',
    )

    actual_device_info = atp_test_selector.get_matched_device()

    self.assertEqual(actual_device_info, expected_device_info)

  @mock.patch('subprocess.check_output', return_value=_FAKE_ADB_OUTPUT)
  @mock.patch.dict(
      'os.environ',
      {
          constants.ANDROID_SERIAL: 'matched.ser.num',
          constants.ANDROID_TARGET_PRODUCT: 'unmatched_device_product',
      },
  )
  def test_get_matched_device_android_serial_set_but_product_unmatched(self, _):
    actual_device_info = atp_test_selector.get_matched_device()

    self.assertIsNone(actual_device_info)

  @mock.patch('subprocess.check_output', return_value=_FAKE_ADB_OUTPUT)
  @mock.patch.dict(
      'os.environ',
      {
          constants.ANDROID_SERIAL: '',
          constants.ANDROID_TARGET_PRODUCT: 'matched_device_product',
      },
  )
  def test_get_matched_device_android_serial_unset_but_product_matched(self, _):
    expected_device_info = atp_test_selector.DeviceInfo(
        serial='matched.ser.num',
        product='matched_device_product',
        device='matched_device',
    )

    actual_device_info = atp_test_selector.get_matched_device()

    self.assertEqual(actual_device_info, expected_device_info)

  @mock.patch('subprocess.check_output', return_value=_FAKE_ADB_OUTPUT)
  @mock.patch.dict(
      'os.environ',
      {
          constants.ANDROID_SERIAL: 'matched.ser.num',
          constants.ANDROID_TARGET_PRODUCT: '',
      },
  )
  def test_get_matched_device_android_serial_set_but_product_unset(self, _):
    actual_device_info = atp_test_selector.get_matched_device()

    self.assertIsNone(actual_device_info)

  @mock.patch(
      'subprocess.check_output',
      side_effect=subprocess.CalledProcessError(
          returncode=1,
          cmd='adb devices -l',
      ),
  )
  def test_get_matched_device_failed_to_get_connected_devices(self, _):
    actual_device_info = atp_test_selector.get_matched_device()

    self.assertIsNone(actual_device_info)

  @mock.patch(
      'subprocess.check_output',
      return_value=b'List of devices attached',
  )
  def test_get_matched_device_no_connected_devices(self, _):
    actual_device_info = atp_test_selector.get_matched_device()

    self.assertIsNone(actual_device_info)


if __name__ == '__main__':
  unittest.main()
