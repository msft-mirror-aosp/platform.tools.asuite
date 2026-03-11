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

from atest import arg_parser
from atest import atest_configs
from atest import constants
from atest import result_reporter
from atest import result_reporter_unittest
from atest import unittest_constants
from atest.mobly.test_result_uploaders import ants_test_result_uploader
from atest.mobly.test_result_uploaders import resultdb_test_result_uploader
from atest.test_finders import test_info
from atest.test_runners import mobly_test_runner
from atest.test_runners import test_runner_base


TEST_NAME = 'SampleMoblyTest'
MOBLY_PKG = 'mobly/SampleMoblyTest'
REQUIREMENTS_TXT = 'mobly/requirements.txt'
APK_1 = 'mobly/snippet1.apk'
APK_2 = 'mobly/snippet2.apk'
MISC_FILE = 'mobly/misc_file.txt'
RESULTS_DIR = 'atest_results/sample_test'
SERIAL_1 = 'serial1'
SERIAL_2 = 'serial2'
ADB_DEVICE = 'adb_device'
MOBLY_LOGS_DIR = os.path.join(unittest_constants.TEST_DATA_DIR, 'mobly')
MOBLY_SUMMARY_FILE = os.path.join(
    unittest_constants.TEST_DATA_DIR, 'mobly', 'sample_test_summary.yaml'
)
MOCK_TEST_FILES = mobly_test_runner.MoblyTestFiles('', None, [], [])


class AntsTestResultUploaderUnittests(unittest.TestCase):
  """Unit tests for AntsTestResultUploader."""

  def setUp(self) -> None:
    self.patchers = [
        mock.patch(
            'atest.logstorage.logstorage_utils.credential_exists',
            return_value=True,
            autospec=True,
        ),
        mock.patch(
            'atest.logstorage.logstorage_utils.do_upload_flow',
            return_value=('creds', {'invocationId': 'I00001'}),
            autospec=True,
        ),
    ]
    self.mock_build_client = mock.patch(
        'atest.logstorage.logstorage_utils.BuildClient', autospec=True
    ).start()
    self.mock_build_client.return_value.client = mock.Mock()
    self.mock_build_client.return_value.insert_work_unit.return_value = {
        'id': 'WU00001',
        'runCount': 0,
    }
    self.patchers.append(self.mock_build_client)
    for patcher in self.patchers[:-1]:
      patcher.start()
    self.uploader = ants_test_result_uploader.AntsTestResultUploader(
        {}, user_enabled_upload=True,
    )
    self.uploader._root_workunit = {'id': 'WU00001', 'runCount': 0}
    self.uploader._current_workunit = {'id': 'WU00010'}

  def tearDown(self) -> None:
    mock.patch.stopall()

  def test_start_new_workunit(self):
    """Tests that start_new_workunit sets correct workunit fields."""
    self.uploader._build_client.insert_work_unit.return_value = {}
    self.uploader.start_new_workunit()

    self.assertEqual(
        self.uploader.current_workunit,
        {
            'type': mobly_test_runner.WORKUNIT_ATEST_MOBLY_TEST_RUN,
            'parentId': 'WU00001',
        },
    )

  def test_set_workunit_iteration_details_with_repeats(self):
    """Tests that set_workunit_iteration_details sets the run number for

    repeated tests.
    """
    rerun_options = mobly_test_runner.RerunOptions(3, False, False)
    self.uploader.set_workunit_iteration_details(1, rerun_options)

    self.assertEqual(self.uploader.current_workunit['childRunNumber'], 1)

  def test_set_workunit_iteration_details_with_retries(self):
    """Tests that set_workunit_iteration_details sets the run number for

    retried tests.
    """
    rerun_options = mobly_test_runner.RerunOptions(3, False, True)
    self.uploader.set_workunit_iteration_details(1, rerun_options)

    self.assertEqual(self.uploader.current_workunit['childAttemptNumber'], 1)

  def test_finalize_current_workunit(self):
    """Tests that finalize_current_workunit sets correct workunit fields."""
    workunit = self.uploader.current_workunit
    self.uploader.finalize_current_workunit()

    self.assertEqual(workunit['schedulerState'], 'completed')
    self.assertEqual(self.uploader._root_workunit['runCount'], 1)
    self.assertIsNone(self.uploader.current_workunit)

  def test_finalize_invocation(self):
    """Tests that finalize_invocation sets correct fields."""
    invocation = self.uploader.invocation
    root_workunit = self.uploader._root_workunit
    self.uploader.finalize_invocation()

    self.assertEqual(root_workunit['schedulerState'], 'completed')
    self.assertEqual(root_workunit['runCount'], 0)
    self.assertEqual(invocation['runner'], 'mobly')
    self.assertEqual(invocation['schedulerState'], 'completed')
    self.assertFalse(self.uploader.enabled)

  @mock.patch('atest.constants.RESULT_LINK', 'link:%s')
  def test_add_result_link(self):
    """Tests that add_result_link correctly sets the result link."""
    reporter = result_reporter.ResultReporter()

    reporter.test_result_link = ['link:I00000']
    self.uploader.add_result_link(reporter)
    self.assertEqual(reporter.test_result_link, ['link:I00000', 'link:I00001'])

    reporter.test_result_link = 'link:I00000'
    self.uploader.add_result_link(reporter)
    self.assertEqual(reporter.test_result_link, ['link:I00000', 'link:I00001'])

    reporter.test_result_link = None
    self.uploader.add_result_link(reporter)
    self.assertEqual(reporter.test_result_link, ['link:I00001'])


class ResultDBUploaderUnittests(unittest.TestCase):
  """Unit tests for ResultDBUploader."""

  def setUp(self) -> None:
    self.patchers = [
        mock.patch(
            'atest.mobly.test_result_uploaders.resultdb_test_result_uploader'
            '.resultdb_uploader_wrapper.enabled',
            return_value=True,
        ),
        mock.patch(
            'atest.mobly.test_result_uploaders.resultdb_test_result_uploader'
            '.resultdb_uploader_wrapper.upload'
        ),
    ]
    for patcher in self.patchers:
      patcher.start()
    self.upload_mock = (
        resultdb_test_result_uploader.resultdb_uploader_wrapper.upload
    )
    self.uploader = resultdb_test_result_uploader.ResultDBUploader(
        user_enabled_upload=True
    )
    self.uploader.set_ants_invocation_id('I00001')

  def tearDown(self) -> None:
    mock.patch.stopall()

  def test_enabled(self):
    """Tests the enabled property."""
    self.assertTrue(self.uploader.enabled)

    uploader_user_disabled = resultdb_test_result_uploader.ResultDBUploader(
        user_enabled_upload=False
    )
    self.assertFalse(uploader_user_disabled.enabled)

    resultdb_test_result_uploader.resultdb_uploader_wrapper.enabled.return_value = (
        False
    )
    uploader_wrapper_disabled = resultdb_test_result_uploader.ResultDBUploader(
        user_enabled_upload=True
    )
    self.assertFalse(uploader_wrapper_disabled.enabled)

  def test_add_test_result(self):
    """Tests that add_test_result adds a result to the test_results list."""
    test_result = {'ants_work_unit_id': 'WU00001', 'foo': 'bar'}
    self.uploader.add_test_result(test_result)
    self.assertEqual(len(self.uploader.test_results), 1)
    self.assertEqual(
        self.uploader.test_results[0],
        {'ants_work_unit_id': 'wu00001', 'foo': 'bar'},
    )

  def test_upload_success(self):
    """Tests that upload calls the wrapper with the correct arguments."""
    self.uploader.test_results = [{'foo': 'bar'}]
    self.upload_mock.return_value = True
    self.assertTrue(self.uploader.upload())
    self.upload_mock.assert_called_with(
        'i00001',
        [{'foo': 'bar'}],
        base_log_path=None,
        is_prod=False,
    )

  def test_upload_no_results(self):
    """Tests that upload returns False when there are no test results."""
    self.assertFalse(self.uploader.upload())
    self.upload_mock.assert_not_called()

  def test_upload_no_invocation_id(self):
    """Tests that upload returns False when ants_invocation_id is not set."""
    self.uploader.ants_invocation_id = None
    self.uploader.test_results = [{'foo': 'bar'}]
    self.assertFalse(self.uploader.upload())
    self.upload_mock.assert_not_called()

  def test_get_test_result_url_prod(self):
    """Tests that get_test_result_url returns the correct prod URL."""
    self.uploader.is_prod = True
    expected_url = (
        'https://ci.chromium.org/ui/test-investigate/invocations/u-ants-i00001'
    )
    self.assertEqual(self.uploader.get_test_result_url(), expected_url)

  def test_get_test_result_url_dev(self):
    """Tests that get_test_result_url returns the correct dev URL."""
    self.uploader.is_prod = False
    expected_url = (
        'https://luci-milo-dev.appspot.com/ui/test-investigate/invocations/'
        'u-ants-i00001'
    )
    self.assertEqual(self.uploader.get_test_result_url(), expected_url)

  @mock.patch(
      'atest.mobly.test_result_uploaders.resultdb_test_result_uploader'
      '.ResultDBUploader.get_test_result_url',
      return_value='link:I00001',
  )
  def test_add_result_link(self, _get_url):
    """Tests that add_result_link correctly sets the result link."""
    reporter = result_reporter.ResultReporter()

    reporter.test_result_link = ['link:I00000']
    self.uploader.add_result_link(reporter)
    self.assertEqual(reporter.test_result_link, ['link:I00000', 'link:I00001'])


class MoblyTestRunnerUnittests(unittest.TestCase):
  """Unit tests for MoblyTestRunner."""

  def setUp(self) -> None:
    self.patchers = [
        mock.patch(
            'atest.test_runners.mobly_test_runner.atest_sponge_client.AtestSpongeClient',
            autospec=True,
        ),
    ]
    self.mock_sponge_client_cls = self.patchers[0].start()
    self.runner = mobly_test_runner.MoblyTestRunner(RESULTS_DIR, extra_args={})
    self.tinfo = test_info.TestInfo(
        test_name=TEST_NAME,
        test_runner=mobly_test_runner.MoblyTestRunner.EXECUTABLE,
        build_targets=[],
    )
    self.reporter = result_reporter.ResultReporter()
    self.mobly_args = argparse.Namespace(config='', testbed='', testparam=[])

  def tearDown(self) -> None:
    mock.patch.stopall()

  @mock.patch('atest.test_runners.mobly_test_runner.os.readlink', side_effect=lambda x: x)
  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner,
      '_get_test_files',
      return_value=MOCK_TEST_FILES,
      autospec=True,
  )
  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner, '_setup_python_env', autospec=True
  )
  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner,
      '_get_cvd_serials',
      return_value=[],
      autospec=True,
  )
  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner, '_install_apks', autospec=True
  )
  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner, '_generate_mobly_config', autospec=True
  )
  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner, '_get_mobly_command', autospec=True
  )
  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner,
      '_run_mobly_command',
      return_value=0,
      autospec=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.ants_test_result_uploader.AntsTestResultUploader',
      autospec=True,
  )
  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner,
      '_process_test_results_from_summary',
      autospec=True,
  )
  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner, '_cleanup', autospec=True
  )
  def test_run_tests_with_multiple_modules(
      self, mock_cleanup, mock_process_results, mock_ants_uploader_cls, *unused_mocks
  ) -> None:
    """Tests run_tests with multiple test modules."""
    mock_ants_uploader = mock_ants_uploader_cls.return_value
    mock_ants_uploader.enabled = True
    tinfo1 = test_info.TestInfo('Test1', '', [])
    tinfo2 = test_info.TestInfo('Test2', '', [])
    test_infos = [tinfo1, tinfo2]
    extra_args = {}
    reporter = result_reporter.ResultReporter()

    result1 = result_reporter_unittest.RESULT_PASSED_TEST
    result2 = result_reporter_unittest.RESULT_PASSED_TEST_MODULE_2
    mock_process_results.side_effect = [[result1], [result2]]

    self.runner.run_tests(test_infos, extra_args, reporter)

    # Assert that logic for each test_info has run by checking for its
    # observable outcome (results being processed).
    self.assertIn(result1, reporter.all_test_results)
    self.assertIn(result2, reporter.all_test_results)

    # Assert that cleanup and finalization are called only once after all
    # tests have run.
    mock_cleanup.assert_called_once()
    mock_ants_uploader.finalize_invocation.assert_called_once()
    mock_ants_uploader.add_result_link.assert_called_once_with(reporter)

  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner, '_cleanup', autospec=True
  )
  @mock.patch(
      'atest.logstorage.logstorage_utils.update_upload_preference',
      return_value=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.ants_test_result_uploader.AntsTestResultUploader',
      autospec=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.resultdb_test_result_uploader.ResultDBUploader',
      autospec=True,
  )
  def test_run_tests_sponge_calls(
      self,
      _mock_resultdb_uploader_cls,
      _mock_ants_uploader_cls,
      _mock_update_upload,
      _mock_cleanup,
  ) -> None:
    """Tests that sponge client is called during run_tests."""
    # Avoid running any mobly tests.
    self.runner.run_tests([], {}, self.reporter)
    self.runner._sponge_client.preprocess_invocation.assert_called_once()
    self.runner._sponge_client.postprocess_invocation.assert_called_once()
    self.runner._sponge_client.add_result_link.assert_called_once_with(
        self.reporter
    )

  @mock.patch.object(pathlib.Path, 'is_file', autospec=True)
  def test_get_test_files_all_files_present(self, is_file) -> None:
    """Tests _get_test_files with all files present."""
    is_file.return_value = True
    files = [MOBLY_PKG, REQUIREMENTS_TXT, APK_1, APK_2, MISC_FILE]
    file_paths = [pathlib.Path(f) for f in files]
    self.tinfo.data[constants.MODULE_INSTALLED] = file_paths

    test_files = self.runner._get_test_files(self.tinfo)

    self.assertTrue(test_files.mobly_pkg.endswith(MOBLY_PKG))
    self.assertTrue(test_files.requirements_txt.endswith(REQUIREMENTS_TXT))
    self.assertTrue(test_files.test_apks[0].endswith(APK_1))
    self.assertTrue(test_files.test_apks[1].endswith(APK_2))
    self.assertTrue(test_files.misc_data[0].endswith(MISC_FILE))

  @mock.patch.object(pathlib.Path, 'is_file', autospec=True)
  def test_get_test_files_no_mobly_pkg(self, is_file) -> None:
    """Tests _get_test_files with missing mobly_pkg."""
    is_file.return_value = True
    files = [REQUIREMENTS_TXT, APK_1, APK_2]
    self.tinfo.data[constants.MODULE_INSTALLED] = [
        pathlib.Path(f) for f in files
    ]

    with self.assertRaisesRegex(
        mobly_test_runner.MoblyTestRunnerError, 'No Mobly test package'
    ):
      self.runner._get_test_files(self.tinfo)

  @mock.patch.object(pathlib.Path, 'is_file', autospec=True)
  def test_get_test_files_file_not_found(self, is_file) -> None:
    """Tests _get_test_files with file not found in file system."""
    is_file.return_value = False
    files = [MOBLY_PKG, REQUIREMENTS_TXT, APK_1, APK_2]
    self.tinfo.data[constants.MODULE_INSTALLED] = [
        pathlib.Path(f) for f in files
    ]

    with self.assertRaisesRegex(
        mobly_test_runner.MoblyTestRunnerError, 'Required test file'
    ):
      self.runner._get_test_files(self.tinfo)

  @mock.patch('builtins.open', autospec=True)
  @mock.patch('atest.test_runners.mobly_test_runner.os.makedirs', autospec=True)
  @mock.patch('atest.test_runners.mobly_test_runner.yaml.safe_dump', autospec=True
  )
  def test_generate_mobly_config_no_serials(self, yaml_dump, *_) -> None:
    """Tests _generate_mobly_config with no serials provided."""
    self.runner._generate_mobly_config(self.mobly_args, None, MOCK_TEST_FILES)

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

  @mock.patch('builtins.open', autospec=True)
  @mock.patch('atest.test_runners.mobly_test_runner.os.makedirs', autospec=True)
  @mock.patch('atest.test_runners.mobly_test_runner.yaml.safe_dump', autospec=True
  )
  def test_generate_mobly_config_with_serials(self, yaml_dump, *_) -> None:
    """Tests _generate_mobly_config with serials provided."""
    self.runner._generate_mobly_config(
        self.mobly_args, [SERIAL_1, SERIAL_2], MOCK_TEST_FILES
    )

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

  @mock.patch('builtins.open', autospec=True)
  @mock.patch('atest.test_runners.mobly_test_runner.os.makedirs', autospec=True)
  @mock.patch('atest.test_runners.mobly_test_runner.yaml.safe_dump', autospec=True
  )
  def test_generate_mobly_config_with_testparams(self, yaml_dump, *_) -> None:
    """Tests _generate_mobly_config with custom testparams."""
    self.mobly_args.testparam = ['foo=bar']
    self.runner._generate_mobly_config(self.mobly_args, None, MOCK_TEST_FILES)

    expected_config = {
        'TestBeds': [{
            'Name': 'LocalTestBed',
            'Controllers': {
                'AndroidDevice': '*',
            },
            'TestParams': {
                'foo': 'bar',
            },
        }],
        'MoblyParams': {
            'LogPath': 'atest_results/sample_test/mobly_logs',
        },
    }
    self.assertEqual(yaml_dump.call_args.args[0], expected_config)

  def test_generate_mobly_config_with_invalid_testparams(self) -> None:
    """Tests _generate_mobly_config with invalid testparams."""
    self.mobly_args.testparam = ['foobar']
    with self.assertRaisesRegex(
        mobly_test_runner.MoblyTestRunnerError, 'Invalid testparam values'
    ):
      self.runner._generate_mobly_config(self.mobly_args, None, [])

  @mock.patch('builtins.open', autospec=True)
  @mock.patch('atest.test_runners.mobly_test_runner.os.makedirs', autospec=True)
  @mock.patch('atest.test_runners.mobly_test_runner.yaml.safe_dump', autospec=True
  )
  def test_generate_mobly_config_with_test_files(self, yaml_dump, *_) -> None:
    """Tests _generate_mobly_config with test files."""
    test_apks = ['files/my_app1.apk', 'files/my_app2.apk']
    misc_data = ['files/some_file.txt']
    test_files = mobly_test_runner.MoblyTestFiles('', '', test_apks, misc_data)
    self.runner._generate_mobly_config(self.mobly_args, None, test_files)

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
                    'some_file.txt': ['files/some_file.txt'],
                },
            },
        }],
        'MoblyParams': {
            'LogPath': 'atest_results/sample_test/mobly_logs',
        },
    }
    self.assertEqual(yaml_dump.call_args.args[0], expected_config)

  @mock.patch('atest.atest_utils.get_adb_devices', autospec=True)
  def test_get_cvd_serials(self, get_adb_devices) -> None:
    """Tests _get_cvd_serials returns correct serials."""
    global_args = arg_parser.create_atest_arg_parser().parse_args([])
    global_args.acloud_create = True
    with mock.patch.object(atest_configs, 'GLOBAL_ARGS', global_args):
      devices = ['localhost:1234', '127.0.0.1:5678', 'AD12345']
      get_adb_devices.return_value = devices

      self.assertEqual(self.runner._get_cvd_serials(), devices[:2])

  @mock.patch('atest.atest_utils.get_adb_devices', return_value=[ADB_DEVICE], autospec=True)
  @mock.patch('atest.test_runners.mobly_test_runner.subprocess.check_call', autospec=True)
  def test_install_apks_no_serials(self, check_call, _) -> None:
    """Tests _install_apks with no serials provided."""
    self.runner._install_apks([APK_1], None)

    expected_cmds = [['adb', '-s', ADB_DEVICE, 'install', '-r', '-g', APK_1]]
    self.assertEqual(
        [call.args[0] for call in check_call.call_args_list], expected_cmds
    )

  @mock.patch('atest.atest_utils.get_adb_devices', return_value=[ADB_DEVICE], autospec=True)
  @mock.patch('atest.test_runners.mobly_test_runner.subprocess.check_call', autospec=True)
  def test_install_apks_with_serials(self, check_call, _) -> None:
    """Tests _install_apks with serials provided."""
    self.runner._install_apks([APK_1], [SERIAL_1, SERIAL_2])

    expected_cmds = [
        ['adb', '-s', SERIAL_1, 'install', '-r', '-g', APK_1],
        ['adb', '-s', SERIAL_2, 'install', '-r', '-g', APK_1],
    ]
    self.assertEqual(
        [call.args[0] for call in check_call.call_args_list], expected_cmds
    )

  def test_get_test_cases_from_spec_with_class_and_methods(self) -> None:
    """Tests _get_test_cases_from_spec with both class and methods defined."""
    self.tinfo.data = {
        'filter': frozenset({
            test_info.TestFilter(
                class_name='SampleClass', methods=frozenset({'test1', 'test2'})
            )
        })
    }

    self.assertCountEqual(
        self.runner._get_test_cases_from_spec(self.tinfo),
        ['SampleClass.test1', 'SampleClass.test2'],
    )

  def test_get_test_cases_from_spec_with_class_only(self) -> None:
    """Tests _get_test_cases_from_spec with only test class defined."""
    self.tinfo.data = {
        'filter': frozenset({
            test_info.TestFilter(class_name='SampleClass', methods=frozenset())
        })
    }

    self.assertCountEqual(
        self.runner._get_test_cases_from_spec(self.tinfo), ['SampleClass']
    )

  def test_get_test_cases_from_spec_with_method_only(self) -> None:
    """Tests _get_test_cases_from_spec with only methods defined."""
    self.tinfo.data = {
        'filter': frozenset({
            test_info.TestFilter(
                class_name='.', methods=frozenset({'test1', 'test2'})
            )
        })
    }

    self.assertCountEqual(
        self.runner._get_test_cases_from_spec(self.tinfo), ['test1', 'test2']
    )

  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner,
      '_process_test_results_from_summary',
      return_value=(),
      autospec=True,
  )
  @mock.patch('atest.test_runners.mobly_test_runner.os.readlink', side_effect=lambda x: x)
  @mock.patch(
      'atest.mobly.test_result_uploaders.resultdb_test_result_uploader.ResultDBUploader',
      autospec=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.ants_test_result_uploader.AntsTestResultUploader',
      autospec=True,
  )
  def test_run_and_handle_results_with_iterations(
      self, mock_ants_uploader_cls, mock_resultdb_uploader_cls, _readlink, _process_results
  ) -> None:
    """Tests _run_and_handle_results with multiple iterations."""
    mock_ants_uploader = mock_ants_uploader_cls.return_value
    mock_resultdb_uploader = mock_resultdb_uploader_cls.return_value
    self.runner._sponge_client = self.mock_sponge_client_cls.return_value
    self.runner._sponge_client.enabled = True

    with mock.patch.object(
        self.runner,
        '_run_mobly_command',
        side_effect=(1, 1, 0, 0, 1),
        autospec=True,
    ) as run_mobly_command:
      self.runner._run_and_handle_results(
          [],
          self.tinfo,
          mobly_test_runner.RerunOptions(5, False, False),
          self.mobly_args,
          self.reporter,
          mock_ants_uploader,
          mock_resultdb_uploader,
      )
      self.assertEqual(run_mobly_command.call_count, 5)

  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner,
      '_process_test_results_from_summary',
      return_value=(),
      autospec=True,
  )
  @mock.patch('atest.test_runners.mobly_test_runner.os.readlink', side_effect=lambda x: x)
  @mock.patch(
      'atest.mobly.test_result_uploaders.resultdb_test_result_uploader.ResultDBUploader',
      autospec=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.ants_test_result_uploader.AntsTestResultUploader',
      autospec=True,
  )
  def test_run_and_handle_results_with_rerun_until_failure(
      self, mock_ants_uploader_cls, mock_resultdb_uploader_cls, _readlink, _process_results
  ) -> None:
    """Tests _run_and_handle_results with rerun_until_failure."""
    mock_ants_uploader = mock_ants_uploader_cls.return_value
    mock_resultdb_uploader = mock_resultdb_uploader_cls.return_value
    self.runner._sponge_client = self.mock_sponge_client_cls.return_value
    self.runner._sponge_client.enabled = True

    with mock.patch.object(
        self.runner,
        '_run_mobly_command',
        side_effect=(0, 0, 1, 0, 1),
        autospec=True,
    ) as run_mobly_command:
      self.runner._run_and_handle_results(
          [],
          self.tinfo,
          mobly_test_runner.RerunOptions(5, True, False),
          self.mobly_args,
          self.reporter,
          mock_ants_uploader,
          mock_resultdb_uploader,
      )
      self.assertEqual(run_mobly_command.call_count, 3)

  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner,
      '_process_test_results_from_summary',
      return_value=(),
      autospec=True,
  )
  @mock.patch('atest.test_runners.mobly_test_runner.os.readlink', side_effect=lambda x: x)
  @mock.patch(
      'atest.mobly.test_result_uploaders.resultdb_test_result_uploader.ResultDBUploader',
      autospec=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.ants_test_result_uploader.AntsTestResultUploader',
      autospec=True,
  )
  def test_run_and_handle_results_with_retry_any_failure(
      self, mock_ants_uploader_cls, mock_resultdb_uploader_cls, _readlink, _process_results
  ) -> None:
    """Tests _run_and_handle_results with retry_any_failure."""
    mock_ants_uploader = mock_ants_uploader_cls.return_value
    mock_resultdb_uploader = mock_resultdb_uploader_cls.return_value
    self.runner._sponge_client = self.mock_sponge_client_cls.return_value
    self.runner._sponge_client.enabled = True

    with mock.patch.object(
        self.runner,
        '_run_mobly_command',
        side_effect=(1, 1, 1, 0, 0),
        autospec=True,
    ) as run_mobly_command:
      self.runner._run_and_handle_results(
          [],
          self.tinfo,
          mobly_test_runner.RerunOptions(5, False, True),
          self.mobly_args,
          self.reporter,
          mock_ants_uploader,
          mock_resultdb_uploader,
      )
      self.assertEqual(run_mobly_command.call_count, 4)

  @mock.patch(
      'atest.test_runners.mobly_test_runner.resultdb_test_result_uploader'
  )
  @mock.patch(
      'atest.test_runners.mobly_test_runner.ants_test_result_uploader'
  )
  @mock.patch('atest.test_runners.mobly_test_runner.logstorage_utils')
  def test_run_tests_uploader_creation_with_ants_invocation(
      self,
      mock_logstorage,
      mock_ants_uploader,
      mock_resultdb_uploader,
  ):
    """Tests that ResultDBUploader uses ANTS invocation ID if available."""
    mock_logstorage.update_upload_preference.return_value = True
    mock_ants_uploader.AntsTestResultUploader.return_value.invocation = {
        'invocationId': 'I00000'
    }

    # empty test_infos to avoid mobly command execution.
    self.runner.run_tests([], {}, self.reporter)

    mock_resultdb_uploader.ResultDBUploader.return_value.set_ants_invocation_id.assert_called_with(
        'I00000'
    )

  @mock.patch('atest.test_runners.mobly_test_runner.uuid.uuid4')
  @mock.patch(
      'atest.test_runners.mobly_test_runner.resultdb_test_result_uploader'
  )
  @mock.patch(
      'atest.test_runners.mobly_test_runner.ants_test_result_uploader'
  )
  @mock.patch('atest.test_runners.mobly_test_runner.logstorage_utils')
  def test_run_tests_uploader_creation_without_ants_invocation(
      self,
      mock_logstorage,
      mock_ants_uploader,
      mock_resultdb_uploader,
      mock_uuid,
  ):
    """Tests that ResultDBUploader uses a UUID if ANTS invocation is not
    available.
    """
    mock_logstorage.update_upload_preference.return_value = True
    mock_ants_uploader.AntsTestResultUploader.return_value.invocation = None
    mock_uuid.return_value = 'some-uuid'

    # empty test_infos to avoid mobly command execution.
    self.runner.run_tests([], {}, self.reporter)

    mock_resultdb_uploader.ResultDBUploader.return_value.set_ants_invocation_id.assert_called_with(
        'some-uuid'
    )

  @mock.patch(
      'atest.mobly.test_result_uploaders.resultdb_test_result_uploader.ResultDBUploader',
      autospec=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.ants_test_result_uploader.AntsTestResultUploader',
      autospec=True,
  )
  def test_process_test_results_from_summary_show_correct_names(
      self, mock_ants_uploader_cls, mock_resultdb_uploader_cls
  ) -> None:
    """Tests _process_results_from_summary outputs correct test names."""
    ants_uploader = mock_ants_uploader_cls.return_value
    resultdb_uploader = mock_resultdb_uploader_cls.return_value
    self.runner._sponge_client = self.mock_sponge_client_cls.return_value
    self.runner._sponge_client.enabled = True
    test_results = self.runner._process_test_results_from_summary(
        MOBLY_LOGS_DIR, MOBLY_SUMMARY_FILE, self.tinfo, 0, 1, ants_uploader, resultdb_uploader
    )

    result = test_results[0]
    self.assertEqual(result.runner_name, self.runner.NAME)
    self.assertEqual(result.group_name, TEST_NAME)
    self.assertEqual(result.test_run_name, 'SampleTest')
    self.assertEqual(result.test_name, 'SampleTest.test_should_pass')

    test_results = self.runner._process_test_results_from_summary(
        MOBLY_LOGS_DIR, MOBLY_SUMMARY_FILE, self.tinfo, 2, 3, ants_uploader, resultdb_uploader
    )

    result = test_results[0]
    self.assertEqual(result.test_run_name, 'SampleTest (#3)')
    self.assertEqual(result.test_name, 'SampleTest.test_should_pass (#3)')

  @mock.patch(
      'atest.mobly.test_result_uploaders.resultdb_test_result_uploader.ResultDBUploader',
      autospec=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.ants_test_result_uploader.AntsTestResultUploader',
      autospec=True,
  )
  def test_process_test_results_from_summary_show_correct_status_and_details(
      self, mock_ants_uploader_cls, mock_resultdb_uploader_cls
  ) -> None:
    """Tests _process_results_from_summary outputs correct test status and

    details.
    """
    ants_uploader = mock_ants_uploader_cls.return_value
    resultdb_uploader = mock_resultdb_uploader_cls.return_value
    self.runner._sponge_client = self.mock_sponge_client_cls.return_value
    self.runner._sponge_client.enabled = True
    test_results = self.runner._process_test_results_from_summary(
        MOBLY_LOGS_DIR, MOBLY_SUMMARY_FILE, self.tinfo, 0, 1, ants_uploader, resultdb_uploader
    )

    # passed case
    self.assertEqual(test_results[0].status, test_runner_base.PASSED_STATUS)
    self.assertIsNone(test_results[0].details)
    # failed case
    self.assertEqual(test_results[1].status, test_runner_base.FAILED_STATUS)
    self.assertEqual(test_results[1].details, 'mobly.signals.TestFailure')
    # errored case
    self.assertEqual(test_results[2].status, test_runner_base.FAILED_STATUS)
    self.assertEqual(test_results[2].details, 'Exception: error')
    # skipped case
    self.assertEqual(test_results[3].status, test_runner_base.IGNORED_STATUS)
    self.assertEqual(test_results[3].details, 'mobly.signals.TestSkip')

  @mock.patch(
      'atest.mobly.test_result_uploaders.resultdb_test_result_uploader.ResultDBUploader',
      autospec=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.ants_test_result_uploader.AntsTestResultUploader',
      autospec=True,
  )
  def test_process_test_results_from_summary_show_correct_stats(
      self, mock_ants_uploader_cls, mock_resultdb_uploader_cls
  ) -> None:
    """Tests _process_results_from_summary outputs correct stats."""
    ants_uploader = mock_ants_uploader_cls.return_value
    resultdb_uploader = mock_resultdb_uploader_cls.return_value
    self.runner._sponge_client = self.mock_sponge_client_cls.return_value
    self.runner._sponge_client.enabled = True
    test_results = self.runner._process_test_results_from_summary(
        MOBLY_LOGS_DIR, MOBLY_SUMMARY_FILE, self.tinfo, 0, 1, ants_uploader, resultdb_uploader
    )

    self.assertEqual(test_results[0].test_count, 1)
    self.assertEqual(test_results[0].group_total, 4)
    self.assertEqual(test_results[0].test_time, '0:00:01')
    self.assertEqual(test_results[1].test_count, 2)
    self.assertEqual(test_results[1].group_total, 4)
    self.assertEqual(test_results[1].test_time, '0:00:00')

  @mock.patch(
      'atest.mobly.test_result_uploaders.resultdb_test_result_uploader.ResultDBUploader',
      autospec=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.ants_test_result_uploader.AntsTestResultUploader',
      autospec=True,
  )
  def test_process_test_results_from_summary_create_correct_uploader_result(
      self, mock_ants_uploader_cls, mock_resultdb_uploader_cls
  ) -> None:
    """Tests _process_results_from_summary creates correct result for the

    uploader.
    """
    ants_uploader = mock_ants_uploader_cls.return_value
    resultdb_uploader = mock_resultdb_uploader_cls.return_value
    self.runner._sponge_client = self.mock_sponge_client_cls.return_value
    self.runner._sponge_client.enabled = True
    ants_uploader.enabled = True
    ants_uploader.invocation = {'invocationId': 'I12345'}
    ants_uploader.current_workunit = {'id': 'WU12345'}
    self.runner._process_test_results_from_summary(
        MOBLY_LOGS_DIR,
        MOBLY_SUMMARY_FILE,
        self.tinfo,
        0,
        1,
        ants_uploader,
        resultdb_uploader,
    )

    expected_results = {
        'invocationId': 'I12345',
        'workUnitId': 'WU12345',
        'testIdentifier': {
            'module': TEST_NAME,
            'testClass': 'SampleTest',
            'method': 'test_should_error',
        },
        'testStatus': mobly_test_runner.TEST_STORAGE_ERROR,
        'timing': {'creationTimestamp': 1000, 'completeTimestamp': 2000},
        'debugInfo': {'errorMessage': 'error', 'trace': 'Exception: error'},
    }

    self.assertEqual(
        ants_uploader.record_test_result.call_args_list[2].args[0],
        expected_results,
    )

  @mock.patch('atest.test_runners.mobly_test_runner.os.path.relpath', side_effect=lambda x, _: os.path.basename(x))
  @mock.patch('atest.test_runners.mobly_test_runner.os.walk')
  @mock.patch(
      'atest.mobly.test_result_uploaders.resultdb_test_result_uploader.ResultDBUploader',
      autospec=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.ants_test_result_uploader.AntsTestResultUploader',
      autospec=True,
  )
  def test_process_test_results_from_summary_create_correct_resultdb_result(
      self, mock_ants_uploader_cls, mock_resultdb_uploader_cls, mock_os_walk, _
  ):
    """Tests that _process_test_results_from_summary creates correct result for
    ResultDB.
    """
    mock_ants_uploader = mock_ants_uploader_cls.return_value
    mock_resultdb_uploader = mock_resultdb_uploader_cls.return_value
    self.runner._sponge_client = self.mock_sponge_client_cls.return_value
    self.runner._sponge_client.enabled = True
    mock_ants_uploader.enabled = True
    mock_ants_uploader.current_workunit = {'id': 'WU12345'}
    mock_resultdb_uploader.enabled = True
    mock_os_walk.return_value = [
        (MOBLY_LOGS_DIR, [], ['file1.log', 'file2.txt'])
    ]
    self.runner._process_test_results_from_summary(
        MOBLY_LOGS_DIR,
        MOBLY_SUMMARY_FILE,
        self.tinfo,
        0,
        1,
        mock_ants_uploader,
        mock_resultdb_uploader,
    )

    expected_passed_result = {
        'ants_work_unit_id': 'WU12345',
        'module_name': TEST_NAME,
        'class_name': 'SampleTest',
        'method_name': 'test_should_pass',
        'status': 'PASS',
        'start_time': 1000000000,
        'duration': 1000000000,
        'artifact_paths': ['file1.log', 'file2.txt'],
    }
    self.assertEqual(
        mock_resultdb_uploader.add_test_result.call_args_list[0].args[0],
        expected_passed_result,
    )

    expected_errored_result = {
        'ants_work_unit_id': 'WU12345',
        'module_name': TEST_NAME,
        'class_name': 'SampleTest',
        'method_name': 'test_should_error',
        'status': 'ERROR',
        'start_time': 1000000000,
        'duration': 1000000000,
        'artifact_paths': ['file1.log', 'file2.txt'],
        'summary_html': (
            '<p><b>Error Message: </b>error</p>'
            '<p><b>Stack Trace: </b>Exception: error</p>'
        ),
    }
    self.assertEqual(
        mock_resultdb_uploader.add_test_result.call_args_list[2].args[0],
        expected_errored_result,
    )

  @mock.patch('atest.test_runners.mobly_test_runner.uuid.uuid4')
  @mock.patch('atest.test_runners.mobly_test_runner.os.path.relpath', side_effect=lambda x, _: os.path.basename(x))
  @mock.patch('atest.test_runners.mobly_test_runner.os.walk')
  @mock.patch(
      'atest.mobly.test_result_uploaders.resultdb_test_result_uploader.ResultDBUploader',
      autospec=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.ants_test_result_uploader.AntsTestResultUploader',
      autospec=True,
  )
  def test_process_test_results_from_summary_resultdb_no_ants_workunit(
      self, mock_ants_uploader_cls, mock_resultdb_uploader_cls, mock_os_walk, _, mock_uuid
  ):
    """Tests that _process_test_results_from_summary creates correct result for
    ResultDB when ANTS workunit is not available.
    """
    mock_ants_uploader = mock_ants_uploader_cls.return_value
    mock_resultdb_uploader = mock_resultdb_uploader_cls.return_value
    self.runner._sponge_client = self.mock_sponge_client_cls.return_value
    self.runner._sponge_client.enabled = True
    mock_ants_uploader.enabled = False
    mock_ants_uploader.current_workunit = None
    mock_resultdb_uploader.enabled = True
    mock_os_walk.return_value = [
        (MOBLY_LOGS_DIR, [], ['file1.log', 'file2.txt'])
    ]
    mock_uuid.return_value = 'some-uuid'
    self.runner._process_test_results_from_summary(
        MOBLY_LOGS_DIR,
        MOBLY_SUMMARY_FILE,
        self.tinfo,
        0,
        1,
        mock_ants_uploader,
        mock_resultdb_uploader,
    )

    expected_passed_result = {
        'ants_work_unit_id': 'some-uuid',
        'module_name': TEST_NAME,
        'class_name': 'SampleTest',
        'method_name': 'test_should_pass',
        'status': 'PASS',
        'start_time': 1000000000,
        'duration': 1000000000,
        'artifact_paths': ['file1.log', 'file2.txt'],
    }
    self.assertEqual(
        mock_resultdb_uploader.add_test_result.call_args_list[0].args[0],
        expected_passed_result,
    )

  @mock.patch.object(
      mobly_test_runner.MoblyTestRunner,
      '_process_test_results_from_summary',
      return_value=(),
      autospec=True,
  )
  @mock.patch(
      'atest.test_runners.mobly_test_runner.os.readlink', side_effect=lambda x: x
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.resultdb_test_result_uploader.ResultDBUploader',
      autospec=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.ants_test_result_uploader.AntsTestResultUploader',
      autospec=True,
  )
  def test_run_and_handle_results_sponge_calls(
      self,
      mock_ants_uploader_cls,
      mock_resultdb_uploader_cls,
      _readlink,
      _process_results,
  ) -> None:
    """Tests that sponge client is called during _run_and_handle_results."""
    mock_ants_uploader = mock_ants_uploader_cls.return_value
    mock_resultdb_uploader = mock_resultdb_uploader_cls.return_value
    self.runner._sponge_client = self.mock_sponge_client_cls.return_value
    self.runner._sponge_client.enabled = True

    with mock.patch.object(
        self.runner,
        '_run_mobly_command',
        return_value=0,
        autospec=True,
    ):
      self.runner._run_and_handle_results(
          [],
          self.tinfo,
          mobly_test_runner.RerunOptions(1, False, False),
          self.mobly_args,
          self.reporter,
          mock_ants_uploader,
          mock_resultdb_uploader,
      )

    self.runner._sponge_client.preprocess_target.assert_called_once_with(
        self.tinfo.test_name
    )
    self.runner._sponge_client.postprocess_target.assert_called_once()

  @mock.patch(
      'atest.mobly.test_result_uploaders.resultdb_test_result_uploader.ResultDBUploader',
      autospec=True,
  )
  @mock.patch(
      'atest.mobly.test_result_uploaders.ants_test_result_uploader.AntsTestResultUploader',
      autospec=True,
  )
  def test_process_test_results_from_summary_sponge_upload(
      self, mock_ants_uploader_cls, mock_resultdb_uploader_cls
  ) -> None:
    """Tests that sponge client uploads test results."""
    mock_ants_uploader = mock_ants_uploader_cls.return_value
    mock_resultdb_uploader = mock_resultdb_uploader_cls.return_value
    self.runner._sponge_client = self.mock_sponge_client_cls.return_value
    self.runner._user_enabled_upload = True

    self.runner._process_test_results_from_summary(
        MOBLY_LOGS_DIR,
        MOBLY_SUMMARY_FILE,
        self.tinfo,
        0,
        1,
        mock_ants_uploader,
        mock_resultdb_uploader,
    )

    self.runner._sponge_client.upload_test_result.assert_called_once_with(
        MOBLY_LOGS_DIR, MOBLY_SUMMARY_FILE, 0
    )


if __name__ == '__main__':
  unittest.main()
