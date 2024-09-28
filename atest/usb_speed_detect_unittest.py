# Copyright (C) 2024 The Android Open Source Project
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

import subprocess
import unittest
from unittest import mock

from atest import atest_utils
from atest import usb_speed_detect as usb


class UsbIgnoredSpeedPatterns(unittest.TestCase):

  def _usb_speed_assert_no_warning(self, negotiated_speed, max_speed):
    """Parametrized test to verify whether a usb speed warning is printed."""
    warning = usb.verify_and_print_usb_speed_warning(
        device_ids=usb.DeviceIds('', '', '', '', ''),
        negotiated_speed=negotiated_speed,
        max_speed=max_speed,
    )

    self.assertFalse(warning)

  def test_verify_print_speed_unknown_speed_doesnt_print(self):
    self._usb_speed_assert_no_warning(0, 0)

  def test_verify_print_speed_low_speed_doesnt_print(self):
    self._usb_speed_assert_no_warning(480, 480)

  def test_verify_print_speed_expected_speed_doesnt_print(self):
    self._usb_speed_assert_no_warning(5000, 5000)

  def test_verify_print_speed_high_speed_doesnt_print(self):
    self._usb_speed_assert_no_warning(5000, 10000)


class UsbSpeedDetectTest(unittest.TestCase):

  def test_verify_print_speed_slow_speed_prints_warning(self):
    warning = usb.verify_and_print_usb_speed_warning(
        device_ids=usb.DeviceIds('', '', '', '', ''),
        negotiated_speed=480,
        max_speed=10000,
    )

    self.assertTrue(warning)


class UdcDriverPatterns(unittest.TestCase):

  def _udc_driver_response(
      self, attr_name: usb.UsbAttributeName, expected_response: int
  ):
    """Parametrized test for handling the responses from the usb driver."""

    speed = usb.get_udc_driver_usb_device_attribute_speed_value('', attr_name)

    self.assertEqual(speed, expected_response)

  @mock.patch('subprocess.check_output', return_value='not found')
  def test_udc_driver_unexpected_subprocess_response_returns_0(
      self, mock_output
  ):
    self._udc_driver_response(usb.UsbAttributeName.MAXIMUM_SPEED, 0)

  @mock.patch('subprocess.check_output', return_value='UNKNOWN')
  def test_udc_driver_unknown_speed_returns_0(self, mock_output):
    self._udc_driver_response(usb.UsbAttributeName.MAXIMUM_SPEED, 0)

  @mock.patch('subprocess.check_output', return_value='wireless')
  def test_udc_driver_irrelevant_speed_returns_0(self, mock_output):
    self._udc_driver_response(usb.UsbAttributeName.NEGOTIATED_SPEED, 0)

  @mock.patch('subprocess.check_output', return_value='high-speed')
  def test_udc_driver_high_speed_returns_numeric_speed(self, mock_output):
    self._udc_driver_response(usb.UsbAttributeName.MAXIMUM_SPEED, 480)

  @mock.patch('subprocess.check_output', return_value='high-speed\n')
  def test_udc_driver_high_speed_output_has_newline_returns_numeric_speed(
      self, mock_output
  ):
    self._udc_driver_response(usb.UsbAttributeName.MAXIMUM_SPEED, 480)

  @mock.patch('subprocess.check_output', return_value='super-speed')
  def test_udc_driver_super_speed_returns_numeric_speed(self, mock_output):
    self._udc_driver_response(usb.UsbAttributeName.MAXIMUM_SPEED, 5000)

  @mock.patch('subprocess.check_output', return_value='super-speed-plus')
  def test_udc_driver_super_speed_plus_returns_numeric_speed(self, mock_output):
    self._udc_driver_response(usb.UsbAttributeName.MAXIMUM_SPEED, 10000)


class DeviceIdentifierPatterns(unittest.TestCase):

  @mock.patch.object(atest_utils, 'has_command', return_value=True)
  @mock.patch.object(subprocess, 'check_output')
  def test_get_adb_device_identifiers_port_fwd_device_returns_address(
      self, mock_output, mock_utils
  ):
    def check_output_side_effect_port_fwd_device(*args, **kwargs):
      for arg in args:
        if 'ro.serialno' in arg:
          return 'SERIAL'
        if all(cmd_arg in ['adb', 'devices'] for cmd_arg in arg):
          return 'List of devices\nlocalhost:27030     device'
        if any(
            cmd_arg
            in {
                'ro.product.manufacturer',
                'ro.product.model',
                'ro.product.name',
            }
            for cmd_arg in arg
        ):
          return ''

    mock_output.side_effect = check_output_side_effect_port_fwd_device

    device_ids = usb.get_adb_device_identifiers()

    self.assertEqual(device_ids.address, 'localhost:27030')

  @mock.patch.object(atest_utils, 'has_command', return_value=True)
  @mock.patch.object(subprocess, 'check_output')
  def test_get_adb_device_identifiers_tcp_device_returns_address(
      self, mock_output, mock_utils
  ):
    def check_output_side_effect_tcp_device(*args, **kwargs):
      for arg in args:
        if 'ro.serialno' in arg:
          return 'SERIAL'
        if all(cmd_arg in ['adb', 'devices'] for cmd_arg in arg):
          return (
              '* daemon not running; starting now at tcp:1111\n * daemon '
              'started successfully\n List of devices\n33a832a820  device'
          )
        if any(
            # If check_output is called with any of ('model', 'name',
            # 'manufacturer', return an empty placeholder value.
            cmd_arg
            in {
                'ro.product.manufacturer',
                'ro.product.model',
                'ro.product.name',
            }
            for cmd_arg in arg
        ):
          return ''

    mock_output.side_effect = check_output_side_effect_tcp_device

    device_ids = usb.get_adb_device_identifiers()

    self.assertEqual(device_ids.address, '33a832a820')

  @mock.patch.object(atest_utils, 'has_command', return_value=True)
  @mock.patch.object(subprocess, 'check_output')
  def test_get_adb_device_identifiers_multiple_devices_returns_none(
      self, mock_output, mock_utils
  ):
    def check_output_side_effect_multiple_devices(*args, **kwargs):
      for arg in args:
        # When multiple devices are connected, ADB will display an error "adb:
        # more than one device/emulator" and no serial will be returned.
        if 'ro.serialno' in arg:
          return None

    mock_output.side_effect = check_output_side_effect_multiple_devices

    device_ids = usb.get_adb_device_identifiers()

    self.assertIsNone(device_ids)
