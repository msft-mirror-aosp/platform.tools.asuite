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

import unittest
from atest import usb_speed_detect
from packages.modules.adb.proto import adb_host_pb2


class UsbSpeedDetectTest(unittest.TestCase):

  def test_non_usb_device_doesnt_print(self):
    device = adb_host_pb2.Device()
    device.connection_type = adb_host_pb2.ConnectionType.SOCKET
    device.state = adb_host_pb2.ConnectionState.DEVICE

    self.assertFalse(
        usb_speed_detect.verify_and_print_usb_speed_warning(device)
    )

  def test_usb_device_expected_speed_doesnt_print(self):
    device = adb_host_pb2.Device()
    device.connection_type = adb_host_pb2.ConnectionType.USB
    device.state = adb_host_pb2.ConnectionState.DEVICE
    device.negotiated_speed = 5000
    device.max_speed = 5000

    self.assertFalse(
        usb_speed_detect.verify_and_print_usb_speed_warning(device)
    )

  def test_usb_device_slow_speed_prints_warning(self):
    device = adb_host_pb2.Device()
    device.connection_type = adb_host_pb2.ConnectionType.USB
    device.state = adb_host_pb2.ConnectionState.DEVICE
    device.negotiated_speed = 480
    device.max_speed = 5000

    self.assertTrue(usb_speed_detect.verify_and_print_usb_speed_warning(device))

  def test_adb_unavailable_doesnt_print(self):
    device = adb_host_pb2.Device()

    self.assertFalse(
        usb_speed_detect.verify_and_print_usb_speed_warning(device)
    )
