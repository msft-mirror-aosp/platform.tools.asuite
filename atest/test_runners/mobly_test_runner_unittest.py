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

import argparse
import os
import pathlib
import unittest
from unittest import mock

from atest import constants
from atest import result_reporter
from atest import unittest_constants
from atest.test_finders import test_info
from atest.test_runners import mobly_test_runner
from atest.test_runners import test_runner_base


TEST_NAME = 'SampleMoblyTest'
MOBLY_PKG = 'mobly/SampleMoblyTest'
REQUIREMENTS_TXT = 'mobly/requirements.txt'
APK_1 = 'mobly/snippet1.apk'
APK_2 = 'mobly/snippet2.apk'
RESULTS_DIR = 'atest_results/sample_test'
SERIAL_1 = 'serial1'
SERIAL_2 = 'serial2'
ADB_DEVICE = 'adb_device'
MOBLY_SUMMARY_FILE = os.path.join(
    unittest_constants.TEST_DATA_DIR, 'mobly', 'sample_test_summary.yaml')


class MoblyTestRunnerUnittests(unittest.TestCase):
    """Unit tests for MoblyTestRunner."""

    def setUp(self) -> None:
        self.runner = mobly_test_runner.MoblyTestRunner(RESULTS_DIR)
        self.tinfo = test_info.TestInfo(
            test_name=TEST_NAME,
            test_runner=mobly_test_runner.MoblyTestRunner.EXECUTABLE,
            build_targets=[],
        )
        self.reporter = result_reporter.ResultReporter()
        self.mobly_args = argparse.Namespace(testparam=[])

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
    @mock.patch('yaml.safe_dump')
    def test_generate_mobly_config_no_serials(self, yaml_dump, _) -> None:
        """Tests _generate_mobly_config with no serials provided."""
        self.runner._generate_mobly_config(self.mobly_args, None, [])

        expected_config = {
            'TestBeds': [{
                'Name': 'LocalTestBed',
                'Controllers': {
                    'AndroidDevice': '*',
                },
                'TestParams': {},
            }],
            'MoblyParams': {
                'LogPath': 'atest_results/sample_test/mobly_logs',
            },
        }
        self.assertEqual(yaml_dump.call_args.args[0], expected_config)

    @mock.patch('builtins.open')
    @mock.patch('yaml.safe_dump')
    def test_generate_mobly_config_with_serials(self, yaml_dump, _) -> None:
        """Tests _generate_mobly_config with serials provided."""
        self.runner._generate_mobly_config(
            self.mobly_args, [SERIAL_1, SERIAL_2], [])

        expected_config = {
            'TestBeds': [{
                'Name': 'LocalTestBed',
                'Controllers': {
                    'AndroidDevice': [SERIAL_1, SERIAL_2],
                },
                'TestParams': {},
            }],
            'MoblyParams': {
                'LogPath': 'atest_results/sample_test/mobly_logs',
            },
        }
        self.assertEqual(yaml_dump.call_args.args[0], expected_config)

    @mock.patch('builtins.open')
    @mock.patch('yaml.safe_dump')
    def test_generate_mobly_config_with_testparams(self, yaml_dump, _) -> None:
        """Tests _generate_mobly_config with custom testparams."""
        self.mobly_args.testparam = ['foo=bar']
        self.runner._generate_mobly_config(self.mobly_args, None, [])

        expected_config = {
            'TestBeds': [{
                'Name': 'LocalTestBed',
                'Controllers': {
                    'AndroidDevice': '*',
                },
                'TestParams': {
                    'foo': 'bar',
                }
            }],
            'MoblyParams': {
                'LogPath': 'atest_results/sample_test/mobly_logs',
            },
        }
        self.assertEqual(yaml_dump.call_args.args[0], expected_config)

    def test_generate_mobly_config_with_invalid_testparams(self) -> None:
        """Tests _generate_mobly_config with invalid testparams."""
        self.mobly_args.testparam = ['foobar']
        with self.assertRaisesRegex(mobly_test_runner.MoblyTestRunnerError,
                                    'Invalid testparam values'):
            self.runner._generate_mobly_config(self.mobly_args, None, [])

    @mock.patch('builtins.open')
    @mock.patch('yaml.safe_dump')
    def test_generate_mobly_config_with_test_apks(self, yaml_dump, _) -> None:
        """Tests _generate_mobly_config with test APKs."""
        test_apks = ['files/my_app1.apk', 'files/my_app2.apk']
        self.runner._generate_mobly_config(self.mobly_args, None, test_apks)

        expected_config = {
            'TestBeds': [{
                'Name': 'LocalTestBed',
                'Controllers': {
                    'AndroidDevice': '*',
                },
                'TestParams': {
                    'files': {
                        'my_app1': ['files/my_app1.apk'],
                        'my_app2': ['files/my_app2.apk'],
                    },
                }
            }],
            'MoblyParams': {
                'LogPath': 'atest_results/sample_test/mobly_logs',
            },
        }
        self.assertEqual(yaml_dump.call_args.args[0], expected_config)

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

    @mock.patch.object(
        mobly_test_runner.MoblyTestRunner, '_get_test_results_from_summary',
        return_value=())
    def test_run_and_handle_results_with_iterations(self, _) -> None:
        """Tests _run_and_handle_results with multiple iterations."""
        with mock.patch.object(
                mobly_test_runner.MoblyTestRunner, '_run_mobly_command',
                side_effect=(1, 1, 0, 0, 1)) as run_mobly_command:
            runner = mobly_test_runner.MoblyTestRunner(RESULTS_DIR)
            runner._run_and_handle_results(
                [], self.tinfo, self.reporter,
                mobly_test_runner.RerunOptions(5, False, False))
            self.assertEqual(run_mobly_command.call_count, 5)

    @mock.patch.object(
        mobly_test_runner.MoblyTestRunner, '_get_test_results_from_summary',
        return_value=())
    def test_run_and_handle_results_with_rerun_until_failure(self, _) -> None:
        """Tests _run_and_handle_results with rerun_until_failure."""
        with mock.patch.object(
                mobly_test_runner.MoblyTestRunner, '_run_mobly_command',
                side_effect=(0, 0, 1, 0, 1)) as run_mobly_command:
            runner = mobly_test_runner.MoblyTestRunner(RESULTS_DIR)
            runner._run_and_handle_results(
                [], self.tinfo, self.reporter,
                mobly_test_runner.RerunOptions(5, True, False))
            self.assertEqual(run_mobly_command.call_count, 3)

    @mock.patch.object(
        mobly_test_runner.MoblyTestRunner, '_get_test_results_from_summary',
        return_value=())
    def test_run_and_handle_results_with_retry_any_failure(self, _) -> None:
        """Tests _run_and_handle_results with retry_any_failure."""
        with mock.patch.object(
                mobly_test_runner.MoblyTestRunner, '_run_mobly_command',
                side_effect=(1, 1, 1, 0, 0)) as run_mobly_command:
            runner = mobly_test_runner.MoblyTestRunner(RESULTS_DIR)
            runner._run_and_handle_results(
                [], self.tinfo, self.reporter,
                mobly_test_runner.RerunOptions(5, False, True))
            self.assertEqual(run_mobly_command.call_count, 4)

    def test_get_test_results_from_summary_show_correct_names(self) -> None:
        """Tests _get_results_from_summary outputs correct test names."""
        test_results = self.runner._get_test_results_from_summary(
            MOBLY_SUMMARY_FILE, self.tinfo, 0, 1)

        result = test_results[0]
        self.assertEqual(result.runner_name, self.runner.NAME)
        self.assertEqual(result.group_name, self.tinfo.test_name)
        self.assertEqual(result.test_run_name, 'SampleTest')
        self.assertEqual(result.test_name, 'SampleTest.test_should_pass')

        test_results = self.runner._get_test_results_from_summary(
            MOBLY_SUMMARY_FILE, self.tinfo, 2, 3)

        result = test_results[0]
        self.assertEqual(result.test_name, 'SampleTest.test_should_pass (#3)')

    def test_get_test_results_from_summary_show_correct_status_and_details(
            self) -> None:
        """
        Tests _get_results_from_summary outputs correct test status and details.
        """
        test_results = self.runner._get_test_results_from_summary(
            MOBLY_SUMMARY_FILE, self.tinfo, 0, 1)

        # passed case
        self.assertEqual(
            test_results[0].status, test_runner_base.PASSED_STATUS)
        self.assertEqual(test_results[0].details, None)
        # failed case
        self.assertEqual(
            test_results[1].status, test_runner_base.FAILED_STATUS)
        self.assertEqual(test_results[1].details, 'mobly.signals.TestFailure')
        # errored case
        self.assertEqual(
            test_results[2].status, test_runner_base.FAILED_STATUS)
        self.assertEqual(test_results[2].details, 'Exception: error')
        # skipped case
        self.assertEqual(
            test_results[3].status, test_runner_base.IGNORED_STATUS)
        self.assertEqual(test_results[3].details, 'mobly.signals.TestSkip')

    def test_get_test_results_from_summary_show_correct_stats(self) -> None:
        """Tests _get_results_from_summary outputs correct stats."""
        test_results = self.runner._get_test_results_from_summary(
            MOBLY_SUMMARY_FILE, self.tinfo, 0, 1)

        self.assertEqual(test_results[0].test_count, 1)
        self.assertEqual(test_results[0].group_total, 4)
        self.assertEqual(test_results[0].test_time, '0:00:01')
        self.assertEqual(test_results[1].test_count, 2)
        self.assertEqual(test_results[1].group_total, 4)
        self.assertEqual(test_results[1].test_time, '0:00:00')


if __name__ == '__main__':
    unittest.main()
