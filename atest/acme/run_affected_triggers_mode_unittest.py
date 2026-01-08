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

import argparse
import sys
import unittest

from atest import atest_enum
from atest import unittest_constants
from atest.acme import acme_test_constants
from atest.acme import acme_utils
from atest.acme import run_affected_triggers_mode
from atest.metrics import metrics
from test_configs_proto import test_configs_pb2


class TestRunAffectedTriggersModeModule(unittest.TestCase):

  @unittest.mock.patch.object(
      acme_utils, 'get_file_paths_relative_to_build_top', autospec=True
  )
  @unittest.mock.patch.object(sys, 'exit', autospec=True)
  @unittest.mock.patch.object(
      run_affected_triggers_mode.atest_utils,
      'print_and_log_error',
      autospec=True,
  )
  def test_process_parsed_args_valid_flag_combinations(
      self,
      mock_print_and_log_error,
      mock_sys_exit,
      mock_get_rel_paths,
  ):
    """Tests for process_parsed_args with valid arguments."""
    test_cases = [
        (
            'run_affected_triggers_false',
            {
                'run_affected_triggers': False,
                'projects': [],
                'file_paths': [],
            },
        ),
        (
            'run_affected_triggers_true',
            {
                'run_affected_triggers': True,
                'projects': [],
                'file_paths': [],
            },
        ),
        (
            'run_affected_triggers_true_with_projects',
            {
                'run_affected_triggers': True,
                'projects': ['a'],
                'file_paths': [],
            },
        ),
        (
            'run_affected_triggers_true_with_file_paths',
            {
                'run_affected_triggers': True,
                'projects': [],
                'file_paths': ['a/b.c'],
            },
        ),
    ]

    for name, args_dict in test_cases:
      with self.subTest(name):
        # Set up mocks.
        mock_sys_exit.reset_mock()
        mock_print_and_log_error.reset_mock()
        mock_get_rel_paths.reset_mock()
        mock_get_rel_paths.return_value = ([], [])
        args = argparse.Namespace(**args_dict)

        # Function call.
        run_affected_triggers_mode.process_parsed_args(args)

        # Assertions.
        mock_sys_exit.assert_not_called()
        mock_print_and_log_error.assert_not_called()
        if args.file_paths:
          mock_get_rel_paths.assert_called_once_with(args.file_paths)

  @unittest.mock.patch.object(
      acme_utils, 'get_file_paths_relative_to_build_top', autospec=True
  )
  @unittest.mock.patch.object(sys, 'exit', autospec=True)
  @unittest.mock.patch.object(
      run_affected_triggers_mode.atest_utils,
      'print_and_log_error',
      autospec=True,
  )
  def test_process_parsed_args_invalid_flag_combinations(
      self,
      mock_print_and_log_error,
      mock_sys_exit,
      mock_get_rel_paths,
  ):
    """Tests for process_parsed_args with invalid argument combinations."""
    mock_get_rel_paths.return_value = ([], [])
    args_dict = {
        'run_affected_triggers': True,
        'projects': ['a'],
        'file_paths': ['a/b.c'],
    }
    args = argparse.Namespace(**args_dict)

    # Function call.
    run_affected_triggers_mode.process_parsed_args(args)

    # Assertions.
    mock_sys_exit.assert_called_once_with(
        atest_enum.ExitCode.INVALID_RUN_AFFECTED_TRIGGERS_ARGS
    )
    mock_print_and_log_error.assert_called_once_with(
        'Only one of --projects or --file-paths can be'
        ' used with --run-affected-triggers.'
    )

  @unittest.mock.patch.object(
      acme_utils, 'get_file_paths_relative_to_build_top', autospec=True
  )
  @unittest.mock.patch.object(sys, 'exit', autospec=True)
  @unittest.mock.patch.object(
      run_affected_triggers_mode.atest_utils,
      'print_and_log_error',
      autospec=True,
  )
  def test_process_parsed_args_non_existent_paths(
      self,
      mock_print_and_log_error,
      mock_sys_exit,
      mock_get_rel_paths,
  ):
    """Tests for process_parsed_args with non-existent file paths."""
    args_dict = {
        'run_affected_triggers': True,
        'projects': [],
        'file_paths': ['a/b.c'],
    }
    mock_get_rel_paths.return_value = ([], ['a/b.c'])
    args = argparse.Namespace(**args_dict)

    # Function call.
    run_affected_triggers_mode.process_parsed_args(args)

    # Assertions.
    mock_sys_exit.assert_called_once_with(
        atest_enum.ExitCode.INVALID_RUN_AFFECTED_TRIGGERS_ARGS
    )
    mock_print_and_log_error.assert_called_once_with(
        "The following input file paths do not exist: ['a/b.c']"
    )
    mock_get_rel_paths.assert_called_once_with(args.file_paths)

  @unittest.mock.patch.object(metrics, 'LocalDetectEvent', autospec=True)
  @unittest.mock.patch.object(
      acme_utils, 'get_reduced_test_configs', autospec=True
  )
  def test_get_affected_test_details_no_affected_tests(
      self,
      mock_get_reduced_test_configs,
      mock_local_detect_event,
  ):
    """Test get_affected_test_details exits if no tests are affected."""
    # Set up mocks.
    mock_get_reduced_test_configs.return_value = test_configs_pb2.TestConfigs()
    mock_sys_exit = self.enterContext(
        unittest.mock.patch.object(sys, 'exit', autospec=True)
    )

    # Function call.
    run_affected_triggers_mode.get_affected_test_details(
        acme_test_constants.SCHEDULING_PLAN.name
    )

    # Assertions.
    mock_sys_exit.assert_called_once_with(atest_enum.ExitCode.TEST_NOT_FOUND)
    mock_local_detect_event.assert_called_once_with(
        detect_type=atest_enum.DetectType.RUN_AFFECTED_TRIGGERS_MODE, result=1
    )

  @unittest.mock.patch.object(metrics, 'LocalDetectEvent', autospec=True)
  @unittest.mock.patch.object(
      acme_utils, 'get_reduced_test_configs', autospec=True
  )
  def test_get_affected_test_details_all_filtered_out(
      self,
      mock_get_reduced_test_configs,
      mock_local_detect_event,
  ):
    """Test get_affected_test_details exits if all plans are filtered out."""
    # Set up mocks.
    mock_get_reduced_test_configs.return_value = (
        acme_test_constants.SAMPLE_TEST_CONFIG
    )
    mock_sys_exit = self.enterContext(
        unittest.mock.patch.object(sys, 'exit', autospec=True)
    )

    # Function call.
    run_affected_triggers_mode.get_affected_test_details(
        'some-other-scheduling-plan'
    )

    # Assertions.
    mock_sys_exit.assert_called_once_with(atest_enum.ExitCode.TEST_NOT_FOUND)
    mock_local_detect_event.assert_called_once_with(
        detect_type=atest_enum.DetectType.RUN_AFFECTED_TRIGGERS_MODE, result=1
    )

  @unittest.mock.patch.object(metrics, 'LocalDetectEvent', autospec=True)
  @unittest.mock.patch.object(
      acme_utils, 'get_reduced_test_configs', autospec=True
  )
  def test_get_affected_test_details(
      self,
      mock_get_reduced_test_configs,
      mock_local_detect_event,
  ):
    """Tests that get_affected_test_details returns the correct TestDetails."""
    # Set up mocks.
    mock_get_reduced_test_configs.return_value = (
        acme_test_constants.SAMPLE_TEST_CONFIG
    )

    # Function call.
    tests, test_details = run_affected_triggers_mode.get_affected_test_details(
        acme_test_constants.SCHEDULING_PLAN.name,
    )
    actual_return_val = zip(tests, test_details)
    expected_return_val = zip(
        [
            unittest_constants.MODULE_NAME,
            unittest_constants.MODULE2_NAME,
            unittest_constants.MODULE_NAME,
        ],
        [
            acme_test_constants.MODULE_PLAN_TEST_DETAILS,
            acme_test_constants.MODULE2_PLAN_TEST_DETAILS,
            acme_test_constants.MODULE_PLAN_SIMPLE_TEST_DETAILS,
        ],
    )

    self.assertCountEqual(expected_return_val, actual_return_val)
    mock_local_detect_event.assert_called_once_with(
        detect_type=atest_enum.DetectType.RUN_AFFECTED_TRIGGERS_MODE, result=1
    )

  @unittest.mock.patch.object(
      acme_utils, 'get_reduced_test_configs', autospec=True
  )
  def test_get_affected_test_details_specific_projects(
      self,
      mock_get_reduced_test_configs,
  ):
    """Tests get_affected_test_details when called with a list of projects."""
    # Set up mocks.
    mock_get_reduced_test_configs.return_value = (
        acme_test_constants.SAMPLE_TEST_CONFIG
    )

    # Function call.
    test_projects = ['some/mock/project-a', 'another/mock/project-b']
    tests, test_details = run_affected_triggers_mode.get_affected_test_details(
        acme_test_constants.SCHEDULING_PLAN.name, projects=test_projects
    )
    actual_return_val = zip(tests, test_details)
    expected_return_val = zip(
        [
            unittest_constants.MODULE_NAME,
            unittest_constants.MODULE2_NAME,
            unittest_constants.MODULE_NAME,
        ],
        [
            acme_test_constants.MODULE_PLAN_TEST_DETAILS,
            acme_test_constants.MODULE2_PLAN_TEST_DETAILS,
            acme_test_constants.MODULE_PLAN_SIMPLE_TEST_DETAILS,
        ],
    )

    self.assertCountEqual(expected_return_val, actual_return_val)
    mock_get_reduced_test_configs.assert_called_once_with(test_projects, [])

  @unittest.mock.patch.object(
      acme_utils, 'get_file_paths_relative_to_build_top', autospec=True
  )
  @unittest.mock.patch.object(
      acme_utils, 'get_reduced_test_configs', autospec=True
  )
  def test_get_affected_test_details_specific_file_paths(
      self, mock_get_reduced_test_configs, mock_get_rel_paths
  ):
    """Tests get_affected_test_details when called with a list of file paths."""
    # Set up mocks.
    mock_get_reduced_test_configs.return_value = (
        acme_test_constants.SAMPLE_TEST_CONFIG
    )
    rel_paths = ['a/b/c', 'd/e/f']
    mock_get_rel_paths.return_value = (rel_paths, [])

    # Function call.
    test_file_paths = ['/some/path/a/b/c', '/another/path/d/e/f']
    tests, test_details = run_affected_triggers_mode.get_affected_test_details(
        acme_test_constants.SCHEDULING_PLAN.name, file_paths=test_file_paths
    )
    actual_return_val = zip(tests, test_details)
    expected_return_val = zip(
        [
            unittest_constants.MODULE_NAME,
            unittest_constants.MODULE2_NAME,
            unittest_constants.MODULE_NAME,
        ],
        [
            acme_test_constants.MODULE_PLAN_TEST_DETAILS,
            acme_test_constants.MODULE2_PLAN_TEST_DETAILS,
            acme_test_constants.MODULE_PLAN_SIMPLE_TEST_DETAILS,
        ],
    )

    self.assertCountEqual(expected_return_val, actual_return_val)
    mock_get_reduced_test_configs.assert_called_once_with(None, rel_paths)
    mock_get_rel_paths.assert_called_once_with(test_file_paths)


if __name__ == '__main__':
  unittest.main()
