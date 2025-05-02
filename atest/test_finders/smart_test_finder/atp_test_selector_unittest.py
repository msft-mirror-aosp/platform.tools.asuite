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

import os
import subprocess
import unittest
from unittest import mock
from atest import constants
from atest.test_finders.smart_test_finder import atp_test_selector
from atest.test_finders.smart_test_finder import local_info_collector
from pyfakefs import fake_filesystem_unittest


_FAKE_CONSTANTS_CONTENT = """{
    "supported_device_target": [
        "device1",
        "device2"
    ]
}"""

_FAKE_ADB_OUTPUT = b"""List of devices attached
fake.ser.num1        product:device_product_1 model:not_important_model1 device:some_device1 transport_id:1
fake.ser.num2        device product:device_product_2 model:not_important_model2 device:some_device2 transport_id:2
matched.ser.num       product:matched_device_product model:not_important_model3 device:matched_device transport_id:3
aosp.matched.ser.num    product:aosp_cf_x86_64_only_phone model:not_important_model4 device:device2 transport_id:4
some_serial   device product:aosp_cf_x86_64_phone model:not_important_model5 device:some_device transport_id:5
"""

_FAKE_ADB_OUTPUT2 = b"""List of devices attached
matched.ser.num       device product:aosp_cf_x86_64_only_phone model:not_important_model3 device:matched_device transport_id:3
"""

_FAKE_LOOKUP_TABLE_CONTENT = """project,target,branch,names
Project/Name1,cf_x86_64_phone-trunk_staging-userdebug,git_main,"[""v2/android-test-harness-team/artifact/artifact_output_validation"",""v2/android-app-compat-engprod/csuite/top_100_app_launch_presubmit_partition_6""]"
Project/Name1,aosp_cf_x86_64_phone-trunk_staging-userdebug,git_main,"[""v2/android-gki/test_mapping_kernel_presubmit"",""v2/android-virtual-infra/test_mapping/presubmit-avd"",""v2/android-virtual-infra/test_mapping/presubmit-host""]"
Project/Name2,cf_x86_64_phone-trunk_staging-userdebug,git_main,"[""v2/android-test-harness-team/tradefed/test_mappings_validation_tests_with_device"",""v2/android-virtual-infra/test_mapping/presubmit-cf""]"
Project/Name2,aosp_cf_x86_64_phone-trunk_staging-userdebug,git_main,"[""v2/android-virtual-infra/test_mapping/presubmit-avd"",""v2/android-test-harness-team/tradefed/host_unit_tests_zip_validation""]"
Project/Name3,aosp_cf_x86_64_only_phone-trunk_staging-userdebug,git_main,"[""v2/android-virtual-infra/test_mapping/presubmit-large-avd"",""v2/android-test-harness-team/tradefed/host_unit_tests_zip_validation""]"
Project/Name4,aosp_cf_x86_64_only_phone-trunk_staging-userdebug,aosp-main,"[""v2/android-virtual-infra/test_mapping/presubmit-large-avd"",""v2/android-virtual-infra/test_mapping/presubmit-host""]"
"""


# pylint: disable=protected-access
class AtpTestSelectorUnittests(unittest.TestCase):
  """Unit tests for atp_test_selector.py."""

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
    self.assertEqual(os.environ.get('ANDROID_SERIAL'), 'matched.ser.num')

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

  def test_get_selected_atp_tests_return_empty_list_if_branch_is_not_main(self):
    input_change_info = local_info_collector.ChangeInfo(
        project='Project/Name2',
        branch='not-main',
        remote_hostname='some_hostname',
        user_key='some_user',
        changed_files=set(),
    )

    actual_selected_atp_tests = atp_test_selector.get_selected_atp_tests(
        input_change_info
    )

    self.assertCountEqual(actual_selected_atp_tests, [])


# pylint: disable=protected-access
class AtpTestSelectorFileSystemUnittests(fake_filesystem_unittest.TestCase):
  """Unit tests for atp_test_selector.py with file access."""

  def setUp(self):
    super().setUp()
    self.setUpPyfakefs()

    self.fake_constants_path = atp_test_selector._get_constants_path()
    self.fs.create_file(
        self.fake_constants_path,
        contents=_FAKE_CONSTANTS_CONTENT,
    )

    self.fake_lookup_table_path = atp_test_selector._get_lookup_table_path()
    self.fs.create_file(
        self.fake_lookup_table_path,
        contents=_FAKE_LOOKUP_TABLE_CONTENT,
    )

    self.mock_subprocess_check_output = self.enterContext(
        mock.patch('subprocess.check_output', return_value=_FAKE_ADB_OUTPUT)
    )

  @mock.patch.dict(
      'os.environ',
      {
          constants.ANDROID_SERIAL: 'some_serial',
          constants.ANDROID_TARGET_PRODUCT: 'aosp_cf_x86_64_phone',
      },
  )
  def test_get_selected_atp_tests_return_matched_tests_for_virtual_device(self):
    input_change_info = local_info_collector.ChangeInfo(
        project='Project/Name2',
        branch='main',
        remote_hostname='some_hostname',
        user_key='some_user',
        changed_files=set(),
    )
    # 'v2/android-test-harness-team/tradefed/host_unit_tests_zip_validation' is
    # not yet verified to be runnable, so it is not selected.
    expected_selected_atp_tests = [
        atp_test_selector.AtpTestInfo(
            name='v2/android-virtual-infra/test_mapping/presubmit-avd',
            target='aosp_cf_x86_64_phone-trunk_staging-userdebug',
            branch='git_main',
        ),
    ]

    actual_selected_atp_tests = atp_test_selector.get_selected_atp_tests(
        input_change_info
    )

    self.assertCountEqual(
        actual_selected_atp_tests, expected_selected_atp_tests
    )

  @mock.patch('subprocess.check_output', side_effect=[_FAKE_ADB_OUTPUT2, b''])
  @mock.patch.dict(
      'os.environ',
      {
          constants.ANDROID_SERIAL: '',
          constants.ANDROID_TARGET_PRODUCT: 'aosp_cf_x86_64_only_phone',
      },
  )
  def test_get_selected_atp_tests_return_matched_tests_for_real_device(
      self, mock_subprocess_check_output
  ):
    input_change_info = local_info_collector.ChangeInfo(
        project='Project/Name3',
        branch='main',
        remote_hostname='some_hostname',
        user_key='some_user',
        changed_files=set(),
    )
    # 'v2/android-test-harness-team/tradefed/host_unit_tests_zip_validation' is
    # not yet verified to be runnable, so it is not selected.
    expected_selected_atp_tests = [
        atp_test_selector.AtpTestInfo(
            name='v2/android-virtual-infra/test_mapping/presubmit-large-avd',
            target='aosp_cf_x86_64_only_phone-trunk_staging-userdebug',
            branch='git_main',
        ),
    ]

    actual_selected_atp_tests = atp_test_selector.get_selected_atp_tests(
        input_change_info
    )

    self.assertCountEqual(
        actual_selected_atp_tests, expected_selected_atp_tests
    )
    self.assertEqual(
        os.environ.get(constants.ANDROID_SERIAL), 'matched.ser.num'
    )
    mock_subprocess_check_output.assert_called_with(
        'adb -s matched.ser.num shell settings put global'
        ' package_verifier_user_consent -1',
        shell=True,
    )

  @mock.patch.dict(
      'os.environ',
      {
          constants.ANDROID_SERIAL: 'matched.ser.num',
          constants.ANDROID_TARGET_PRODUCT: 'unmatched_device_product',
      },
  )
  def test_get_selected_atp_tests_return_empty_list_only_if_no_matched_device(
      self,
  ):
    input_change_info = local_info_collector.ChangeInfo(
        project='Project/Name1',
        branch='main',
        remote_hostname='some_hostname',
        user_key='some_user',
        changed_files=set(),
    )

    actual_selected_atp_tests = atp_test_selector.get_selected_atp_tests(
        input_change_info
    )

    self.assertCountEqual(actual_selected_atp_tests, [])

  def test_get_selected_atp_tests_test_plan_not_selected_if_branch_not_git_main(
      self,
  ):
    input_change_info = local_info_collector.ChangeInfo(
        project='Project/Name4',
        branch='main',
        remote_hostname='some_hostname',
        user_key='some_user',
        changed_files=set(),
    )

    actual_selected_atp_tests = atp_test_selector.get_selected_atp_tests(
        input_change_info
    )

    self.assertCountEqual(actual_selected_atp_tests, [])


if __name__ == '__main__':
  unittest.main()
