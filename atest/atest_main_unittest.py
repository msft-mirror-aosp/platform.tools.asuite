#!/usr/bin/env python3
#
# Copyright 2017, The Android Open Source Project
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

"""Unittests for atest."""

# pylint: disable=invalid-name

import datetime
from importlib import reload
import os
import subprocess
import tempfile
from typing import List
import unittest
from unittest import mock
from atest import arg_parser
from atest import atest_main
from atest import atest_utils
from atest import constants
from atest import module_info
from atest.atest_enum import DetectType
from atest.atest_enum import ExitCode
from atest.metrics import metrics
from atest.metrics import metrics_utils
from atest.test_finders import test_info
from pyfakefs import fake_filesystem_unittest


# pylint: disable=protected-access
class AtestUnittests(unittest.TestCase):
  """Unit tests for atest_main.py"""

  @mock.patch('os.environ.get')
  def test_missing_environment_variables(self, mock_env_get):
    """Test _missing_environment_variables method."""
    test_cases = [
        ('uninitialized', None, True),
        ('initialized', 'out/testcases/', False),
    ]

    for name, return_value, expected in test_cases:
      with self.subTest(name=name):
        mock_env_get.return_value = return_value
        self.assertEqual(bool(atest_main._missing_environment_variables()), expected)

  def _assert_args_in_order(self, arg_list: List[str], arg0: str, arg1: str):
    self.assertIn(arg0, arg_list)
    index = arg_list.index(arg0)
    self.assertLess(
        index,
        len(arg_list) - 1,
        f"'{arg0}' is last argument in {arg_list}",
    )
    self.assertEqual(
        arg_list[index + 1],
        arg1,
        f"'{arg0}' is not immediately followed by '{arg1}' in {arg_list}",
    )

  def test_parse_args_with_tests(self):
    """Test _parse_args with test arguments."""
    # Test out test and custom args are properly retrieved.
    args = ['test_name_one', 'test_name_two', '--', '--custom_arg', 'custom_arg_val']
    parsed_args = atest_main._parse_args(args)
    self.assertEqual(parsed_args.tests, ['test_name_one', 'test_name_two'])
    self._assert_args_in_order(
        parsed_args.custom_args, '--custom_arg', 'custom_arg_val'
    )

  def test_parse_args_no_tests(self):
    """Test _parse_args with no test arguments."""
    custom_arg_val = 'custom_arg_val'
    pos_custom_arg = 'pos_custom_arg'

    # Test out custom positional args with no test args.
    args = ['--', pos_custom_arg, custom_arg_val]
    parsed_args = atest_main._parse_args(args)
    self.assertEqual(parsed_args.tests, [])
    self._assert_args_in_order(
        parsed_args.custom_args, pos_custom_arg, custom_arg_val
    )

  def test_has_valid_test_mapping_args(self):
    """Test _has_valid_test_mapping_args method."""
    # Test test mapping related args are not mixed with incompatible args.
    options_no_tm_support = [
        (
            '--annotation-filter',
            'androidx.test.filters.SmallTest',
        ),
    ]
    tm_options = ['--test-mapping', '--include-subdirs']

    for tm_option in tm_options:
      for no_tm_option, no_tm_option_value in options_no_tm_support:
        args = [tm_option, no_tm_option]
        if no_tm_option_value:
          args.append(no_tm_option_value)
        parsed_args = atest_main._parse_args(args)
        self.assertFalse(
            atest_main._has_valid_test_mapping_args(parsed_args),
            f'Failed to validate: {args}',
        )

  @mock.patch.object(atest_utils, 'get_adb_devices')
  @mock.patch.object(metrics_utils, 'send_exit_event')
  def test_validate_exec_mode(self, _send_exit, _devs):
    """Test _validate_exec_mode."""
    _devs.return_value = ['127.0.0.1:34556']
    no_install_test_info = test_info.TestInfo(
        'mod',
        '',
        set(),
        data={},
        module_class=['JAVA_LIBRARIES'],
        install_locations=set(['device']),
    )
    host_test_info = test_info.TestInfo(
        'mod',
        '',
        set(),
        data={},
        module_class=['NATIVE_TESTS'],
        install_locations=set(['host']),
    )
    device_test_info = test_info.TestInfo(
        'mod',
        '',
        set(),
        data={},
        module_class=['NATIVE_TESTS'],
        install_locations=set(['device']),
    )
    both_test_info = test_info.TestInfo(
        'mod',
        '',
        set(),
        data={},
        module_class=['NATIVE_TESTS'],
        install_locations=set(['host', 'device']),
    )

    # $atest <Both-support>
    parsed_args = atest_main._parse_args([])
    test_infos = [host_test_info]
    atest_main._validate_exec_mode(parsed_args, test_infos)
    self.assertFalse(parsed_args.host)

    # $atest <Both-support> with host_tests set to True
    parsed_args = atest_main._parse_args([])
    test_infos = [host_test_info]
    atest_main._validate_exec_mode(parsed_args, test_infos, host_tests=True)
    # Make sure the host option is not set.
    self.assertFalse(parsed_args.host)

    # $atest <Both-support> with host_tests set to False
    parsed_args = atest_main._parse_args([])
    test_infos = [host_test_info]
    atest_main._validate_exec_mode(parsed_args, test_infos, host_tests=False)
    self.assertFalse(parsed_args.host)

    # $atest <device-only> with host_tests set to False
    parsed_args = atest_main._parse_args([])
    test_infos = [device_test_info]
    atest_main._validate_exec_mode(parsed_args, test_infos, host_tests=False)
    # Make sure the host option is not set.
    self.assertFalse(parsed_args.host)

    # $atest <device-only> with host_tests set to True
    parsed_args = atest_main._parse_args([])
    test_infos = [device_test_info]
    self.assertRaises(
        SystemExit,
        atest_main._validate_exec_mode,
        parsed_args,
        test_infos,
        host_tests=True,
    )

    # $atest <Both-support>
    parsed_args = atest_main._parse_args([])
    test_infos = [both_test_info]
    atest_main._validate_exec_mode(parsed_args, test_infos)
    self.assertFalse(parsed_args.host)

    # $atest <no_install_test_info>
    parsed_args = atest_main._parse_args([])
    test_infos = [no_install_test_info]
    atest_main._validate_exec_mode(parsed_args, test_infos)
    self.assertFalse(parsed_args.host)

  @mock.patch.object(atest_utils, 'get_adb_devices')
  @mock.patch.object(metrics_utils, 'send_exit_event')
  def test_validate_exec_mode_no_system_exit_with_smart_test_selection(
      self, _send_exit, _devs
  ):
    """Test _validate_exec_mode."""
    _devs.return_value = ['127.0.0.1:34556']
    parsed_args = atest_main._parse_args(['--sts'])
    host_test_info = test_info.TestInfo(
        'mod',
        '',
        set(),
        data={},
        module_class=['NATIVE_TESTS'],
        install_locations=set(['host']),
    )
    device_test_info = test_info.TestInfo(
        'mod',
        '',
        set(),
        data={},
        module_class=['NATIVE_TESTS'],
        install_locations=set(['device']),
    )
    test_infos = [device_test_info, host_test_info]

    atest_main._validate_exec_mode(parsed_args, test_infos)

    self.assertFalse(parsed_args.host)

  def test_make_test_run_dir(self):
    """Test make_test_run_dir."""
    tmp_dir = tempfile.mkdtemp()
    constants.ATEST_RESULT_ROOT = tmp_dir

    work_dir = atest_main.make_test_run_dir()
    folder_name = os.path.basename(work_dir)
    date_time = datetime.datetime.strptime(
        '_'.join(folder_name.split('_')[0:2]), atest_main.TEST_RUN_DIR_PREFIX
    )
    reload(constants)
    self.assertIsNotNone(date_time)

  def test_has_set_sufficient_devices(self):
    """Test has_set_sufficient_devices method."""
    test_cases = [
        ('no_device_no_require', 0, None, True),
        ('equal_required_attached_devices', 2, ['serial1', 'serial2'], True),
        ('attached_devices_more_than_required',
         2, ['serial1', 'serial2', 'serial3'], True),
        ('not_enough_devices', 2, ['serial1'], False),
    ]

    for name, required_num, attached_devices, expected in test_cases:
      with self.subTest(name=name):
        result = atest_main.has_set_sufficient_devices(
            required_num, attached_devices)
        self.assertEqual(result, expected)

  def test_ravenwood_tests_is_deviceless(self):
    ravenwood_test_info = test_info.TestInfo(
        'mod',
        '',
        set(),
        compatibility_suites=[
            test_info.MODULE_COMPATIBILITY_SUITES_RAVENWOOD_TESTS
        ],
    )

    self.assertEqual(
        constants.DEVICELESS_TEST,
        ravenwood_test_info.get_supported_exec_mode(),
        'If compatibility suites contains ravenwood-tests, '
        'the test should be recognized as deviceless.',
    )


class AtestMainUnitTests(unittest.TestCase):

  def test_performance_tests_inject_default_args(self):
    non_perf_test_info = test_info.TestInfo(
        'some_module',
        'TestRunner',
        set(),
        compatibility_suites=['not-performance'],
    )
    perf_test_info = test_info.TestInfo(
        'some_module',
        'TestRunner',
        set(),
        compatibility_suites=['performance-tests'],
    )
    args_original = atest_main._parse_args([])

    test_cases = [
        (
            'does not inject default args for non-perf tests',
            non_perf_test_info,
            True,
        ),
        (
            'injects default args for perf tests',
            perf_test_info,
            False,
        ),
    ]

    for name, t_info, should_be_equal in test_cases:
      with self.subTest(name=name):
        args = atest_main._parse_args([])
        atest_main._AtestMain._inject_default_arguments_based_on_test_infos(
            [t_info], args
        )
        are_equal = args_original == args
        self.assertEqual(should_be_equal, are_equal)

  @mock.patch.object(
      atest_main._AtestMain, '_get_build_targets', return_value=None
  )
  def test_run_build_step_exits_normally_when_no_build_target(
      self, _mock_get_build_targets
  ):
    pseudo_atest_main = atest_main._AtestMain(argv=[])
    pseudo_atest_main._args = atest_main._parse_args(argv=[])

    self.assertIsNone(pseudo_atest_main._run_build_step())

  @mock.patch.object(
      atest_main, '_missing_environment_variables', return_value=False
  )
  @mock.patch('os.getenv', return_value='/tmp/my_android_build_root')
  @mock.patch('os.getcwd', return_value='/tmp/my_android_build_root/tools')
  def test_check_envs_and_args_smart_test_selection_and_test_refs_specified(
      self, _mock_getcwd, _mock_getenv, _mock_missing_env
  ):
    pseudo_atest_main = atest_main._AtestMain(argv=[])
    pseudo_atest_main._args = atest_main._parse_args(
        argv=['--sts', 'SomeTestModule']
    )

    self.assertEqual(
        pseudo_atest_main._check_envs_and_args(),
        ExitCode.INPUT_TEST_REFERENCE_ERROR,
    )

  @mock.patch(
      'subprocess.run',
      return_value=subprocess.CompletedProcess(args=[], returncode=1),
  )
  @mock.patch.object(
      atest_main, '_missing_environment_variables', return_value=False
  )
  @mock.patch('os.getenv', return_value='/tmp/my_android_build_root')
  @mock.patch('os.getcwd', return_value='/tmp/my_android_build_root/tools')
  def test_check_envs_and_args_smart_test_selection_not_under_a_repo(
      self, _mock_getcwd, _mock_getenv, _mock_missing_env, _mock_run
  ):
    pseudo_atest_main = atest_main._AtestMain(argv=[])
    pseudo_atest_main._args = atest_main._parse_args(argv=['--sts'])

    self.assertEqual(
        pseudo_atest_main._check_envs_and_args(),
        ExitCode.OUTSIDE_REPO,
    )

  @mock.patch.object(
      atest_main, '_missing_environment_variables', return_value=False
  )
  @mock.patch('os.getenv', return_value='/tmp/my_android_build_root')
  @mock.patch('os.getcwd', return_value='/tmp/my_android_build_root/tools')
  def test_check_envs_and_args_cross_branch_args_valid_with_bid(
      self, _mock_getcwd, _mock_getenv, _mock_missing_env
  ):
    """Tests cross-branch args are valid with build target and bid."""
    pseudo_atest_main = atest_main._AtestMain(argv=[])
    pseudo_atest_main._args = atest_main._parse_args(
        argv=[
            '--test_build_target',
            'test_suites_arm64',
            '--test_build_id',
            '123456',
        ]
    )

    self.assertIsNone(pseudo_atest_main._check_envs_and_args())

  @mock.patch.object(
      atest_main, '_missing_environment_variables', return_value=False
  )
  @mock.patch('os.getenv', return_value='/tmp/my_android_build_root')
  @mock.patch('os.getcwd', return_value='/tmp/my_android_build_root/tools')
  def test_check_envs_and_args_cross_branch_args_valid_with_branch(
      self, _mock_getcwd, _mock_getenv, _mock_missing_env
  ):
    """Tests cross-branch args are valid with build target and branch."""
    pseudo_atest_main = atest_main._AtestMain(argv=[])
    pseudo_atest_main._args = atest_main._parse_args(
        argv=[
            '--test_build_target',
            'test_suites_arm64',
            '--test_branch',
            'git_main',
        ]
    )

    self.assertIsNone(pseudo_atest_main._check_envs_and_args())

  @mock.patch.object(
      atest_main, '_missing_environment_variables', return_value=False
  )
  @mock.patch('os.getenv', return_value='/tmp/my_android_build_root')
  @mock.patch('os.getcwd', return_value='/tmp/my_android_build_root/tools')
  def test_check_envs_and_args_cross_branch_args_no_target(
      self, _mock_getcwd, _mock_getenv, _mock_missing_env
  ):
    """Tests cross-branch args are invalid without build target."""
    pseudo_atest_main = atest_main._AtestMain(argv=[])
    pseudo_atest_main._args = atest_main._parse_args(
        argv=[
            '--test_build_id',
            '123456',
            '--test_branch',
            'git_main',
        ]
    )

    self.assertEqual(
        pseudo_atest_main._check_envs_and_args(),
        ExitCode.INVALID_CROSS_BRANCH_ARGS,
    )

  @mock.patch.object(
      atest_main, '_missing_environment_variables', return_value=False
  )
  @mock.patch('os.getenv', return_value='/tmp/my_android_build_root')
  @mock.patch('os.getcwd', return_value='/tmp/my_android_build_root/tools')
  def test_check_envs_and_args_cross_branch_args_no_bid_branch(
      self, _mock_getcwd, _mock_getenv, _mock_missing_env
  ):
    """Tests cross-branch args are invalid without branch and bid."""
    pseudo_atest_main = atest_main._AtestMain(argv=[])
    pseudo_atest_main._args = atest_main._parse_args(
        argv=['--test_build_target', 'test_suites_arm64']
    )

    self.assertEqual(
        pseudo_atest_main._check_envs_and_args(),
        ExitCode.INVALID_CROSS_BRANCH_ARGS,
    )


# pylint: disable=missing-function-docstring
class AtestUnittestFixture(fake_filesystem_unittest.TestCase):
  """Fixture for ModuleInfo tests."""

  def setUp(self):
    self.setUpPyfakefs()

  # pylint: disable=protected-access
  def create_empty_module_info(self):
    fake_temp_file_name = next(tempfile._get_candidate_names())
    self.fs.create_file(fake_temp_file_name, contents='{}')
    return module_info.load_from_file(module_file=fake_temp_file_name)

  def create_module_info(self, modules=None):
    mod_info = self.create_empty_module_info()
    if modules is None:
      modules = []

    for m in modules:
      mod_info.name_to_module_info[m['module_name']] = m

    return mod_info

  def create_test_info(
      self,
      test_name='hello_world_test',
      test_runner='AtestTradefedRunner',
      build_targets=None,
  ):
    """Create a test_info.TestInfo object."""
    if build_targets is None:
      build_targets = set()
    return test_info.TestInfo(test_name, test_runner, build_targets)


class HasValidTestMappingArgsTest(AtestUnittestFixture):
  """Test _has_valid_test_mapping_args metric event sending."""

  @mock.patch('atest.metrics.metrics.LocalDetectEvent')
  def test_has_valid_test_mapping_args_metric_event_sending(self, mock_event):
    """Test _has_valid_test_mapping_args metric event sending."""
    test_cases = [
        ('no_tests', [], 1),
        ('with_tests', ['test1'], 0),
    ]

    for name, test_args, expected_result in test_cases:
        with self.subTest(name=name):
            # Arrange
            expected_detect_type = DetectType.IS_TEST_MAPPING
            args = arg_parser.create_atest_arg_parser().parse_args(test_args)

            # Act
            atest_main._has_valid_test_mapping_args(args)

            # Assert
            mock_event.assert_called_once_with(
                detect_type=expected_detect_type, result=expected_result
            )
            # Reset mock for the next subtest
            mock_event.reset_mock()


if __name__ == '__main__':
  unittest.main()
