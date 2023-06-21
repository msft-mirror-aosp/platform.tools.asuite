# Copyright 2023, The Android Open Source Project
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

"""Unittests for mobly_test_runner."""

# pylint: disable=protected-access
# pylint: disable=invalid-name

import pathlib
import unittest
from unittest import mock

from atest import constants
from atest.test_finders import test_info
from atest.test_runners import mobly_test_runner


TEST_NAME = 'SampleTest'
MOBLY_PKG = 'mobly/SampleTest'
REQUIREMENTS_TXT = 'mobly/requirements.txt'
APK_1 = 'mobly/snippet1.apk'
APK_2 = 'mobly/snippet2.apk'
RESULTS_DIR = 'atest_results/sample_test'
SERIAL_1 = 'serial1'
SERIAL_2 = 'serial2'
ADB_DEVICE = 'adb_device'


class MoblyTestRunnerUnittests(unittest.TestCase):
    """Unit tests for MoblyTestRunner."""

    def setUp(self) -> None:
        self.runner = mobly_test_runner.MoblyTestRunner(RESULTS_DIR)
        self.tinfo = test_info.TestInfo(
            test_name=TEST_NAME,
            test_runner=mobly_test_runner.MoblyTestRunner.EXECUTABLE,
            build_targets=[],
        )

    @mock.patch.object(pathlib.Path, 'is_file')
    def test_get_test_files_all_files_present(self, is_file) -> None:
        """Tests _get_test_files with all files present."""
        is_file.return_value = True
        files = [MOBLY_PKG, REQUIREMENTS_TXT, APK_1, APK_2]
        file_paths = [pathlib.Path(f) for f in files]
        self.tinfo.data[constants.MODULE_INSTALLED] = file_paths

        test_files = self.runner._get_test_files(self.tinfo)

        self.assertTrue(test_files.mobly_pkg.endswith(MOBLY_PKG))
        self.assertTrue(test_files.requirements_txt.endswith(REQUIREMENTS_TXT))
        self.assertTrue(test_files.test_apks[0].endswith(APK_1))
        self.assertTrue(test_files.test_apks[1].endswith(APK_2))

    @mock.patch.object(pathlib.Path, 'is_file')
    def test_get_test_files_no_mobly_pkg(self, is_file) -> None:
        """Tests _get_test_files with missing mobly_pkg."""
        is_file.return_value = True
        files = [REQUIREMENTS_TXT, APK_1, APK_2]
        self.tinfo.data[
            constants.MODULE_INSTALLED] = [pathlib.Path(f) for f in files]

        with self.assertRaisesRegex(mobly_test_runner.MoblyTestRunnerError,
                                    'No Mobly test package'):
            self.runner._get_test_files(self.tinfo)

    @mock.patch.object(pathlib.Path, 'is_file')
    def test_get_test_files_file_not_found(self, is_file) -> None:
        """Tests _get_test_files with file not found in file system."""
        is_file.return_value = False
        files = [MOBLY_PKG, REQUIREMENTS_TXT, APK_1, APK_2]
        self.tinfo.data[
            constants.MODULE_INSTALLED] = [pathlib.Path(f) for f in files]

        with self.assertRaisesRegex(mobly_test_runner.MoblyTestRunnerError,
                                    'Required test file'):
            self.runner._get_test_files(self.tinfo)

    @mock.patch('builtins.open')
    @mock.patch('json.dump')
    def test_generate_mobly_config_no_serials(self, json_dump, _) -> None:
        """Tests _generate_mobly_config with no serials provided."""
        self.runner._generate_mobly_config(None)

        expected_config = {
            'TestBeds': [{
                'Name': 'LocalTestBed',
                'Controllers': {
                    'AndroidDevice': '*',
                },
            }],
            'MoblyParams': {
                'LogPath': 'atest_results/sample_test/mobly_logs',
            },
        }
        self.assertEqual(json_dump.call_args.args[0], expected_config)

    @mock.patch('builtins.open')
    @mock.patch('json.dump')
    def test_generate_mobly_config_with_serials(self, json_dump, _) -> None:
        """Tests _generate_mobly_config with serials provided."""
        self.runner._generate_mobly_config([SERIAL_1, SERIAL_2])

        expected_config = {
            'TestBeds': [{
                'Name': 'LocalTestBed',
                'Controllers': {
                    'AndroidDevice': [SERIAL_1, SERIAL_2],
                },
            }],
            'MoblyParams': {
                'LogPath': 'atest_results/sample_test/mobly_logs',
            },
        }
        self.assertEqual(json_dump.call_args.args[0], expected_config)

    @mock.patch('atest.atest_utils.get_adb_devices', return_value=[ADB_DEVICE])
    @mock.patch('subprocess.check_call')
    def test_install_apks_no_serials(self, check_call, _) -> None:
        """Tests _install_apks with no serials provided."""
        self.runner._install_apks([APK_1], None)

        expected_cmds = [
            ['adb', '-s', ADB_DEVICE, 'install', '-r', '-g', APK_1]
        ]
        self.assertEqual(
            [call.args[0] for call in check_call.call_args_list], expected_cmds)

    @mock.patch('atest.atest_utils.get_adb_devices', return_value=[ADB_DEVICE])
    @mock.patch('subprocess.check_call')
    def test_install_apks_with_serials(self, check_call, _) -> None:
        """Tests _install_apks with serials provided."""
        self.runner._install_apks([APK_1], [SERIAL_1, SERIAL_2])

        expected_cmds = [
            ['adb', '-s', SERIAL_1, 'install', '-r', '-g', APK_1],
            ['adb', '-s', SERIAL_2, 'install', '-r', '-g', APK_1],
        ]
        self.assertEqual(
            [call.args[0] for call in check_call.call_args_list], expected_cmds)


if __name__ == '__main__':
    unittest.main()
