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
import copy
import pathlib
import subprocess
import sys
import unittest

from atest import atest_enum
from atest import atest_utils
from atest import unittest_constants
from atest.acme import acme_test_constants
from atest.acme import acme_utils
from test_configs_proto import test_configs_pb2

MOCK_BUILD_TOP_PATH = pathlib.Path('/build/top')


class TestAcmeUtilsModule(unittest.TestCase):

  @unittest.mock.patch.object(atest_utils, 'get_build_out_dir', autospec=True)
  @unittest.mock.patch.object(subprocess, 'run', autospec=True)
  @unittest.mock.patch('builtins.open')
  @unittest.mock.patch.object(
      atest_utils,
      'get_build_top',
      autospec=True,
      return_value=MOCK_BUILD_TOP_PATH,
  )
  def test_build_reduced_test_configs(
      self,
      mock_get_build_top,
      mock_open_builtin,
      mock_subprocess_run,
      mock_get_build_out_dir,
  ):
    """Test the get_reduced_test_configs method."""
    test_cases = [
        (
            'no_args',
            {},
            [acme_utils.REDUCE_TEST_CONFIGS_CMD],
        ),
        (
            'with_projects',
            {
                'projects': ['a', 'b'],
            },
            [acme_utils.REDUCE_TEST_CONFIGS_CMD, '-projects', 'a', 'b'],
        ),
    ]
    for name, kwargs, expected_cmd in test_cases:
      with self.subTest(name):
        # Set up mocks.
        mock_subprocess_run.reset_mock()
        mock_open_builtin.reset_mock()
        mock_get_build_top.reset_mock()
        mock_get_build_out_dir.reset_mock()
        fake_pb_path = '/fake/path/to/test-configs.pb'
        mock_get_build_out_dir.return_value = fake_pb_path
        mock_file = unittest.mock.mock_open(
            read_data=acme_test_constants.SAMPLE_TEST_CONFIG.SerializeToString()
        )
        mock_open_builtin.return_value = mock_file.return_value

        # Function call.
        test_configs = acme_utils.get_reduced_test_configs(**kwargs)

        # Assertions.
        self.assertEqual(acme_test_constants.SAMPLE_TEST_CONFIG, test_configs)

        mock_subprocess_run.assert_called_once_with(
            expected_cmd, cwd=MOCK_BUILD_TOP_PATH, check=True
        )
        mock_get_build_top.assert_called_once()
        mock_get_build_out_dir.assert_called_once_with(
            acme_utils.REDUCE_TEST_CONFIGS_OUTPUT_SUB_PATH
        )
        mock_open_builtin.assert_called_once_with(fake_pb_path, 'rb')

  @unittest.mock.patch.object(subprocess, 'run', autospec=True)
  @unittest.mock.patch.object(
      atest_utils,
      'get_build_top',
      autospec=True,
      return_value=MOCK_BUILD_TOP_PATH,
  )
  def test_get_reduced_test_configs_call_error(
      self,
      mock_get_build_top,
      mock_subprocess_run,
  ):
    """Tests get_reduced_test_configs raises an error when subprocess fails."""
    # Set up mocks.
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=acme_utils.REDUCE_TEST_CONFIGS_CMD,
    )

    # Function call and assertions.
    with self.assertRaises(subprocess.CalledProcessError):
      acme_utils.get_reduced_test_configs()

    mock_get_build_top.assert_called_once()
    mock_subprocess_run.assert_called_once_with(
        [acme_utils.REDUCE_TEST_CONFIGS_CMD],
        cwd=MOCK_BUILD_TOP_PATH,
        check=True,
    )

  @unittest.mock.patch.object(
      atest_utils,
      'get_build_top',
      autospec=True,
      return_value=MOCK_BUILD_TOP_PATH,
  )
  def test_get_file_paths_relative_to_build_top(self, mock_get_build_top):
    """Tests get_file_paths_relative_to_build_top."""

    def mock_resolve_side_effect(path_instance, strict=False):
      if strict and 'invalid' in str(path_instance):
        raise FileNotFoundError
      return pathlib.Path(str(path_instance))

    test_cases = [
        {
            'name': 'all_valid_paths',
            'file_paths': [
                f'{MOCK_BUILD_TOP_PATH}/a/b',
                f'{MOCK_BUILD_TOP_PATH}/c',
            ],
            'expected': (['a/b', 'c'], []),
        },
        {
            'name': 'all_invalid_paths',
            'file_paths': ['/invalid/path1', '/another/invalid/path'],
            'expected': ([], ['/invalid/path1', '/another/invalid/path']),
        },
        {
            'name': 'mixed_paths',
            'file_paths': [
                f'{MOCK_BUILD_TOP_PATH}/a/b',
                '/some/invalid/path',
            ],
            'expected': (['a/b'], ['/some/invalid/path']),
        },
        {'name': 'empty_list', 'file_paths': [], 'expected': ([], [])},
    ]

    with unittest.mock.patch.object(
        pathlib.Path,
        'resolve',
        side_effect=mock_resolve_side_effect,
        autospec=True,
    ) as mock_resolve:
      for test_case in test_cases:
        with self.subTest(test_case['name']):
          mock_get_build_top.reset_mock()
          mock_resolve.reset_mock()
          expected_relative_paths, expected_invalid_paths = test_case[
              'expected'
          ]
          rel_paths, invalid_paths = (
              acme_utils.get_file_paths_relative_to_build_top(
                  test_case['file_paths']
              )
          )
          self.assertCountEqual(expected_relative_paths, rel_paths)
          self.assertCountEqual(expected_invalid_paths, invalid_paths)
          # get_build_top should be called once for each valid path.
          self.assertEqual(
              len(expected_relative_paths), mock_get_build_top.call_count
          )
          # resolve should be called once for each path.
          self.assertEqual(
              len(test_case['file_paths']), mock_resolve.call_count
          )

  def test_create_test_details_from_test_execution_plans(self):
    """Tests creation of TestDetail objects from TestExecutionPlans."""
    test_exec_plan1 = test_configs_pb2.TestExecutionPlan(
        name='test-exec-plan1',
        tests=[
            acme_test_constants.MODULE_PLAN,
            acme_test_constants.MODULE2_PLAN,
        ],
    )
    # One ModulePlan with same module name, but different options.
    # One ModulePlan that is identical and should be deduped.
    test_exec_plan2 = test_configs_pb2.TestExecutionPlan(
        name='test-exec-plan2',
        tests=[
            acme_test_constants.MODULE_PLAN_SIMPLE,
            acme_test_constants.MODULE2_PLAN,
        ],
    )
    test_details = acme_utils.create_test_details_from_test_execution_plans(
        [test_exec_plan1, test_exec_plan2]
    )
    expected_test_details = [
        acme_test_constants.MODULE_PLAN_TEST_DETAILS,
        acme_test_constants.MODULE_PLAN_SIMPLE_TEST_DETAILS,
        acme_test_constants.MODULE2_PLAN_TEST_DETAILS,
    ]
    self.assertCountEqual(expected_test_details, test_details)

  @unittest.mock.patch.object(atest_utils, 'get_build_out_dir', autospec=True)
  @unittest.mock.patch('builtins.open')
  @unittest.mock.patch.object(atest_utils, 'build', autospec=True)
  def test_get_full_test_configs(
      self, mock_build, mock_open_builtin, mock_get_build_out_dir
  ):
    """Tests successful getting the full test-configs artifact."""
    # Set up mocks.
    fake_pb_path = '/fake/path/to/test-configs.pb'
    mock_get_build_out_dir.return_value = fake_pb_path
    mock_file = unittest.mock.mock_open(
        read_data=acme_test_constants.SAMPLE_TEST_CONFIG.SerializeToString()
    )
    mock_open_builtin.return_value = mock_file.return_value

    # Function call.
    test_configs = acme_utils.get_full_test_configs()

    # Assertions.
    self.assertEqual(acme_test_constants.SAMPLE_TEST_CONFIG, test_configs)
    mock_build.assert_called_once_with([acme_utils.TEST_CONFIGS_BUILD_TARGET])
    mock_open_builtin.assert_called_once_with(fake_pb_path, 'rb')

  def test_get_filtered_test_execution_plans_mixed_scheduling_plans(self):
    """Tests filtering test execution plans by scheduling plan."""
    expected_test_execution_plans = [
        acme_test_constants.INLINE_WORKFLOW_SCHEDULING_PLAN_2_EXECUTION_PLAN
    ]
    test_execution_plans = acme_utils.get_filtered_test_execution_plans(
        acme_test_constants.SAMPLE_TEST_CONFIG_MIXED_SCHEDULING_PLANS,
        acme_test_constants.SCHEDULING_PLAN_2.name,
    )
    self.assertCountEqual(expected_test_execution_plans, test_execution_plans)

  def test_get_filtered_test_execution_plans_all_selected(self):
    """Tests getting execution plan when all belong to the scheduling plan."""
    expected_test_execution_plans = [
        acme_test_constants.INLINE_WORKFLOW_EXECUTION_PLAN,
        acme_test_constants.TEST_EXECUTION_PLAN,
    ]
    test_execution_plans = acme_utils.get_filtered_test_execution_plans(
        acme_test_constants.SAMPLE_TEST_CONFIG,
        acme_test_constants.SCHEDULING_PLAN.name,
    )
    self.assertCountEqual(expected_test_execution_plans, test_execution_plans)

  def test_get_filtered_test_execution_plans_only_references(self):
    """Tests getting execution plans when test-triggers contain references."""
    expected_test_execution_plans = [
        acme_test_constants.INLINE_WORKFLOW_EXECUTION_PLAN,
        acme_test_constants.TEST_EXECUTION_PLAN,
    ]
    test_execution_plans = acme_utils.get_filtered_test_execution_plans(
        acme_test_constants.SAMPLE_FULL_TEST_CONFIGS,
        acme_test_constants.SCHEDULING_PLAN.name,
    )
    self.assertCountEqual(expected_test_execution_plans, test_execution_plans)

  def test_get_filtered_test_execution_plans_all_filtered_out(self):
    """Tests getting execution plans when none belong to the scheduling plan."""
    expected_test_execution_plans = []
    test_execution_plans = acme_utils.get_filtered_test_execution_plans(
        acme_test_constants.SAMPLE_TEST_CONFIG,
        'some-other-scheduling-plan',
    )
    self.assertCountEqual(expected_test_execution_plans, test_execution_plans)

  def test_get_test_execution_plans(self):
    """Tests getting test execution plans by name."""
    expected_plans = [acme_test_constants.TEST_EXECUTION_PLAN]
    test_execution_plans = acme_utils.get_test_execution_plans(
        acme_test_constants.SAMPLE_FULL_TEST_CONFIGS,
        [acme_test_constants.TEST_EXECUTION_PLAN.name],
    )
    self.assertCountEqual(expected_plans, test_execution_plans)

  def test_get_test_execution_plans_empty_list(self):
    """Tests getting test execution plans with an empty list of names."""
    test_execution_plans = acme_utils.get_test_execution_plans(
        acme_test_constants.SAMPLE_FULL_TEST_CONFIGS, []
    )
    self.assertCountEqual([], test_execution_plans)

  def test_get_test_execution_plans_invalid(self):
    """Tests getting test execution plans with an invalid name."""
    test_execution_plans = acme_utils.get_test_execution_plans(
        acme_test_constants.SAMPLE_FULL_TEST_CONFIGS, ['invalid-plan']
    )
    self.assertCountEqual([], test_execution_plans)

  def test_get_test_execution_plans_for_test_workflows(self):
    """Tests getting test execution plans for test workflows."""
    expected_plans = [acme_test_constants.TEST_EXECUTION_PLAN]
    test_execution_plans = acme_utils.get_execution_plans_for_test_workflows(
        acme_test_constants.SAMPLE_FULL_TEST_CONFIGS,
        [acme_test_constants.TEST_WORKFLOW.name],
    )
    self.assertCountEqual(expected_plans, test_execution_plans)

  def test_get_test_execution_plans_for_test_workflows_empty_list(self):
    """Tests getting test execution plans for test workflows with an empty list."""
    test_execution_plans = acme_utils.get_execution_plans_for_test_workflows(
        acme_test_constants.SAMPLE_FULL_TEST_CONFIGS, []
    )
    self.assertCountEqual([], test_execution_plans)

  def test_get_test_execution_plans_for_test_workflows_invalid(self):
    """Tests getting test execution plans for test workflows with an invalid name."""
    test_execution_plans = acme_utils.get_execution_plans_for_test_workflows(
        acme_test_constants.SAMPLE_FULL_TEST_CONFIGS, ['invalid-workflow']
    )
    self.assertCountEqual([], test_execution_plans)

  def test_get_test_execution_plans_for_test_triggers(self):
    """Tests getting test execution plans for test triggers."""
    expected_plans = [acme_test_constants.TEST_EXECUTION_PLAN]
    test_execution_plans = acme_utils.get_execution_plans_for_test_triggers(
        acme_test_constants.SAMPLE_FULL_TEST_CONFIGS,
        [acme_test_constants.TEST_TRIGGER_LIST_WORKFLOW.name],
    )
    self.assertCountEqual(expected_plans, test_execution_plans)

  def test_get_test_execution_plans_for_test_triggers_empty_list(self):
    """Tests getting test execution plans for test triggers with an empty list."""
    test_execution_plans = acme_utils.get_execution_plans_for_test_triggers(
        acme_test_constants.SAMPLE_FULL_TEST_CONFIGS, []
    )
    self.assertCountEqual([], test_execution_plans)

  def test_get_test_execution_plans_for_test_triggers_invalid(self):
    """Tests getting test execution plans for test triggers with an invalid name."""
    test_execution_plans = acme_utils.get_execution_plans_for_test_triggers(
        acme_test_constants.SAMPLE_FULL_TEST_CONFIGS, ['invalid-trigger']
    )
    self.assertCountEqual([], test_execution_plans)

  @unittest.mock.patch.object(sys, 'exit', autospec=True)
  def test_ensure_no_incompatible_args_no_acme_args(self, mock_exit):
    """Tests ensure_no_incompatible_args when no ACME args are passed in."""
    args_dict = {arg: True for arg in acme_utils.ACME_INCOMPATIBLE_ARGS}
    args = argparse.Namespace(**args_dict)
    acme_utils.ensure_no_incompatible_args(args)
    mock_exit.assert_not_called()

  @unittest.mock.patch.object(sys, 'exit', autospec=True)
  def test_ensure_no_incompatible_args_all_valid(self, mock_exit):
    """Tests ensure_no_incompatible_args with valid flag combinations."""
    for acme_arg in acme_utils.ACME_TRIGGER_ARGS:
      with self.subTest(acme_arg=acme_arg):
        mock_exit.reset_mock()
        args_dict = {
            acme_arg: True,
            # Random atest flags.
            'verbose': True,
            'dry_run': True,
        }
        args = argparse.Namespace(**args_dict)
        acme_utils.ensure_no_incompatible_args(args)
        mock_exit.assert_not_called()

  @unittest.mock.patch.object(atest_utils, 'print_and_log_error', autospec=True)
  @unittest.mock.patch.object(sys, 'exit', autospec=True)
  def test_ensure_no_incompatible_args_invalid_combinations(
      self, mock_exit, mock_print_error
  ):
    """Tests ensure_no_incompatible_args with invalid flag combinations."""
    for acme_arg in acme_utils.ACME_TRIGGER_ARGS:
      for incompatible_arg in acme_utils.ACME_INCOMPATIBLE_ARGS:
        with self.subTest(acme_arg=acme_arg, incompatible_arg=incompatible_arg):
          mock_exit.reset_mock()
          mock_print_error.reset_mock()
          args_dict = {
              acme_arg: True,
              incompatible_arg: (
                  ['fake-test'] if incompatible_arg == 'tests' else True
              ),
          }
          args = argparse.Namespace(**args_dict)

          acme_utils.ensure_no_incompatible_args(args)

          mock_exit.assert_called_once_with(
              atest_enum.ExitCode.INVALID_RUN_AFFECTED_TRIGGERS_ARGS
          )
          mock_print_error.assert_called_once()

  @unittest.mock.patch('subprocess.run', autospec=True)
  def test_get_current_project(self, mock_subprocess_run):
    """Tests that get_current_project returns the correct project."""
    mock_subprocess_run.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='platform/development',
        stderr=None,
    )
    project = acme_utils.get_current_project()
    self.assertEqual('platform/development', project)
    mock_subprocess_run.assert_called_once_with(
        "repo forall . -c 'echo $REPO_PROJECT'",
        shell=True,
        check=False,
        capture_output=True,
        encoding='utf-8',
    )

  def test_use_atest_execution_plan_suite_runner(self):
    """Tests use_atest_execution_plan_suite_runner."""
    test_info_with_plans = copy.deepcopy(unittest_constants.MODULE_INFO)
    test_info_with_plans.data = {'execution_plans': ['plan1']}
    test_info_no_plans = copy.deepcopy(unittest_constants.MODULE_INFO)
    test_info_no_plans.data = {}

    self.assertTrue(
        acme_utils.use_atest_execution_plan_suite_runner([test_info_with_plans])
    )
    self.assertFalse(
        acme_utils.use_atest_execution_plan_suite_runner([test_info_no_plans])
    )
    self.assertFalse(acme_utils.use_atest_execution_plan_suite_runner([]))

  @unittest.mock.patch.object(atest_utils, 'get_build_out_dir', autospec=True)
  def test_create_atest_execution_plan_suite_runner_test_args(
      self, mock_get_build_out_dir
  ):
    """Tests create_atest_execution_plan_suite_runner_test_args."""
    fake_zip_path = '/fake/path/to/test-configs.zip'
    mock_get_build_out_dir.return_value = fake_zip_path
    test_info1 = copy.deepcopy(unittest_constants.MODULE_INFO)
    test_info1.data = {'execution_plans': ['plan1', 'plan2']}
    test_info2 = copy.deepcopy(unittest_constants.MODULE_INFO2)
    test_info2.data = {'execution_plans': ['plan3']}

    args = acme_utils.create_atest_execution_plan_suite_runner_test_args(
        [test_info1, test_info2]
    )

    expected_args = [
        '--execution-plans',
        'plan1',
        '--execution-plans',
        'plan2',
        '--execution-plans',
        'plan3',
        '--extra-file',
        f'test-configs.zip={fake_zip_path}',
        '--config-zip-paths',
        'test-configs.zip',
    ]
    self.assertEqual(expected_args, args)
    mock_get_build_out_dir.assert_called_once_with(
        acme_utils.TEST_CONFIGS_ZIP_PATH
    )


class TestModuleExecutionPlanMap(unittest.TestCase):
  """Tests ModuleExecutionPlanMap dataclass."""

  def test_get_all_module_names(self):
    """Tests get_all_module_names."""
    mapping = {
        'module1': {'plan1', 'plan2'},
        'module2': {'plan3'},
    }
    mep = acme_utils.ModuleExecutionPlanMap(mapping)

    self.assertCountEqual(['module1', 'module2'], mep.get_all_module_names())

  def test_get_execution_plans_for_module(self):
    """Tests get_execution_plans_for_module."""
    mapping = {
        'module1': {'plan1', 'plan2'},
        'module2': {'plan3'},
    }
    mep = acme_utils.ModuleExecutionPlanMap(mapping)

    self.assertEqual(
        {'plan1', 'plan2'}, mep.get_execution_plans_for_module('module1')
    )
    self.assertEqual({'plan3'}, mep.get_execution_plans_for_module('module2'))
    self.assertEqual(set(), mep.get_execution_plans_for_module('unknown'))

  def test_add_execution_plans_to_test_infos(self):
    """Tests add_execution_plans_to_test_infos."""
    mapping = {
        unittest_constants.MODULE_NAME: {'plan1', 'plan2'},
        unittest_constants.MODULE2_NAME: {'plan3'},
    }
    mep = acme_utils.ModuleExecutionPlanMap(mapping)

    test_info1 = copy.deepcopy(unittest_constants.MODULE_INFO)
    test_info1.data = {}
    test_info2 = copy.deepcopy(unittest_constants.MODULE_INFO2)
    test_info2.data = {}

    mep.add_execution_plans_to_test_infos([test_info1, test_info2])

    self.assertCountEqual(
        ['plan1', 'plan2'], test_info1.data['execution_plans']
    )
    self.assertCountEqual(['plan3'], test_info2.data['execution_plans'])


if __name__ == '__main__':
  unittest.main()
