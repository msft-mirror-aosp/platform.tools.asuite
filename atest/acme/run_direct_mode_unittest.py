# Copyright 2026, The Android Open Source Project
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

"""Unit tests for run_direct_mode.py."""

import argparse
import sys
import unittest
from unittest import mock

from atest import atest_enum
from atest import unittest_constants
from atest.acme import acme_test_constants
from atest.acme import acme_utils
from atest.acme import run_direct_mode
from test_configs_proto import test_configs_pb2

TEST_CONFIGS = test_configs_pb2.TestConfigs(
    execution_plans=[
        acme_test_constants.TEST_EXECUTION_PLAN,
        acme_test_constants.TEST_EXECUTION_PLAN_2,
        acme_test_constants.TEST_EXECUTION_PLAN_3,
    ],
    workflows=[
        acme_test_constants.TEST_WORKFLOW,
        acme_test_constants.TEST_WORKFLOW_2,
        acme_test_constants.TEST_WORKFLOW_3,
    ],
    triggers=[
        acme_test_constants.TEST_TRIGGER_LIST_WORKFLOW_REFERENCE_ONLY,
        acme_test_constants.TEST_TRIGGER_LIST_WORKFLOW_2_REFERENCE_ONLY,
    ],
)


class RunDirectModeUnittest(unittest.TestCase):
  """Unit tests for run_direct_mode.py."""

  @mock.patch.object(acme_utils, 'ensure_no_incompatible_args', autospec=True)
  def test_process_parsed_args(
      self,
      mock_ensure_no_incompatible_args,
  ):
    """Test process_parsed_args calls ensure_no_incompatible_args."""
    args_dict = {
        'test_execution_plans': ['plan1'],
        'tests': [],
    }
    args = argparse.Namespace(**args_dict)

    # Function call.
    run_direct_mode.process_parsed_args(args)

    # Assertions.
    mock_ensure_no_incompatible_args.assert_called_once_with(args)

  @mock.patch.object(
      acme_utils, 'create_test_details_from_test_execution_plans', autospec=True
  )
  @mock.patch.object(
      acme_utils, 'get_execution_plans_for_test_triggers', autospec=True
  )
  @mock.patch.object(
      acme_utils, 'get_execution_plans_for_test_workflows', autospec=True
  )
  @mock.patch.object(acme_utils, 'get_test_execution_plans', autospec=True)
  @mock.patch.object(
      run_direct_mode, '_ensure_input_test_configs_exist', autospec=True
  )
  @mock.patch.object(acme_utils, 'get_full_test_configs', autospec=True)
  def test_get_test_details_function_calls(
      self,
      mock_get_configs,
      mock_validate_configs,
      mock_get_plans,
      mock_get_plans_for_workflows,
      mock_get_plans_for_triggers,
      mock_create_test_details,
  ):
    """Test get_test_details calls the correct helper functions."""
    # Set return values for mocked functions.
    mock_get_configs.return_value = TEST_CONFIGS
    mock_get_plans.return_value = [acme_test_constants.TEST_EXECUTION_PLAN]
    mock_get_plans_for_workflows.return_value = [
        acme_test_constants.TEST_EXECUTION_PLAN_2
    ]
    mock_get_plans_for_triggers.return_value = [
        acme_test_constants.TEST_EXECUTION_PLAN_3
    ]
    mock_create_test_details.return_value = [
        acme_test_constants.MODULE_PLAN_TEST_DETAILS,
    ]

    # Call the function under test.
    plan_names = ['plan1', 'plan2']
    workflow_names = ['workflow1', 'workflow2']
    trigger_names = ['trigger1', 'trigger2']

    tests, test_details = run_direct_mode.get_test_details(
        test_execution_plan_names=plan_names,
        test_workflow_names=workflow_names,
        test_trigger_names=trigger_names,
    )

    # Assertions.
    mock_get_configs.assert_called_once_with()
    mock_validate_configs.assert_called_once_with(
        TEST_CONFIGS,
        test_execution_plan_names=plan_names,
        test_workflow_names=workflow_names,
        test_trigger_names=trigger_names,
    )
    mock_get_plans.assert_called_once_with(TEST_CONFIGS, plan_names)
    mock_get_plans_for_workflows.assert_called_once_with(
        TEST_CONFIGS, workflow_names
    )
    mock_get_plans_for_triggers.assert_called_once_with(
        TEST_CONFIGS, trigger_names
    )
    mock_create_test_details.assert_called_once_with([
        acme_test_constants.TEST_EXECUTION_PLAN,
        acme_test_constants.TEST_EXECUTION_PLAN_2,
        acme_test_constants.TEST_EXECUTION_PLAN_3,
    ])
    self.assertCountEqual(
        [
            acme_test_constants.MODULE_PLAN.module,
        ],
        tests,
    )
    self.assertCountEqual(
        [
            acme_test_constants.MODULE_PLAN_TEST_DETAILS,
        ],
        test_details,
    )

  @mock.patch.object(
      acme_utils, 'get_execution_plans_for_test_triggers', autospec=True
  )
  @mock.patch.object(
      acme_utils, 'get_execution_plans_for_test_workflows', autospec=True
  )
  @mock.patch.object(acme_utils, 'get_test_execution_plans', autospec=True)
  @mock.patch.object(
      run_direct_mode, '_ensure_input_test_configs_exist', autospec=True
  )
  @mock.patch.object(acme_utils, 'get_full_test_configs', autospec=True)
  def test_get_module_execution_plan_map_function_calls(
      self,
      mock_get_configs,
      mock_validate_configs,
      mock_get_plans,
      mock_get_plans_for_workflows,
      mock_get_plans_for_triggers,
  ):
    """Test get_module_execution_plan_map calls helper functions."""
    # Set return values for mocked functions.
    mock_get_configs.return_value = TEST_CONFIGS
    mock_get_plans.return_value = [acme_test_constants.TEST_EXECUTION_PLAN]
    mock_get_plans_for_workflows.return_value = []
    mock_get_plans_for_triggers.return_value = []

    # Call the function under test.
    plan_names = ['plan1']
    mep = run_direct_mode.get_module_execution_plan_map(
        test_execution_plan_names=plan_names
    )

    # Assertions.
    mock_get_configs.assert_called_once_with()
    mock_validate_configs.assert_called_once_with(
        TEST_CONFIGS,
        test_execution_plan_names=plan_names,
        test_workflow_names=[],
        test_trigger_names=[],
    )
    mock_get_plans.assert_called_once_with(TEST_CONFIGS, plan_names)
    mock_get_plans_for_workflows.assert_called_once_with(TEST_CONFIGS, [])
    mock_get_plans_for_triggers.assert_called_once_with(TEST_CONFIGS, [])

    self.assertCountEqual(
        [
            unittest_constants.MODULE_NAME,
            unittest_constants.MODULE2_NAME,
        ],
        mep.get_all_module_names(),
    )
    self.assertEqual(
        {acme_test_constants.TEST_EXECUTION_PLAN.name},
        mep.get_execution_plans_for_module(unittest_constants.MODULE_NAME),
    )

  @mock.patch(
      'atest.acme.run_direct_mode.atest_utils.print_and_log_warning',
      autospec=True,
  )
  @mock.patch.object(acme_utils, 'get_full_test_configs', autospec=True)
  def test_get_test_details_with_invalid_inputs(
      self, mock_get_configs, mock_print_and_log_warning
  ):
    """Test get_test_details exits when an invalid config is given."""
    mock_get_configs.return_value = TEST_CONFIGS
    base_error_message = 'Unable to find all test configs.'
    test_cases = {
        'invalid_plan': {
            'plans': ['invalid-plan'],
            'workflows': [],
            'triggers': [],
            'expected_message': (
                f'{base_error_message}\n'
                "Missing test execution plans: {'invalid-plan'}"
            ),
        },
        'invalid_workflow': {
            'plans': [],
            'workflows': ['invalid-workflow'],
            'triggers': [],
            'expected_message': (
                f'{base_error_message}\n'
                "Missing test workflows: {'invalid-workflow'}"
            ),
        },
        'invalid_trigger': {
            'plans': [],
            'workflows': [],
            'triggers': ['invalid-trigger'],
            'expected_message': (
                f'{base_error_message}\n'
                "Missing test triggers: {'invalid-trigger'}"
            ),
        },
        'all_invalid': {
            'plans': ['invalid-plan'],
            'workflows': ['invalid-workflow'],
            'triggers': ['invalid-trigger'],
            'expected_message': (
                f'{base_error_message}\n'
                "Missing test execution plans: {'invalid-plan'}\n"
                "Missing test workflows: {'invalid-workflow'}\n"
                "Missing test triggers: {'invalid-trigger'}"
            ),
        },
    }
    for name, inputs in test_cases.items():
      with self.subTest(name):
        mock_print_and_log_warning.reset_mock()
        with mock.patch.object(sys, 'exit', autospec=True) as mock_sys_exit:
          run_direct_mode.get_test_details(
              test_execution_plan_names=inputs['plans'],
              test_workflow_names=inputs['workflows'],
              test_trigger_names=inputs['triggers'],
          )
          mock_sys_exit.assert_called_with(atest_enum.ExitCode.TEST_NOT_FOUND)
        mock_print_and_log_warning.assert_any_call(inputs['expected_message'])

  @mock.patch(
      'atest.acme.run_direct_mode.atest_utils.print_and_log_warning',
      autospec=True,
  )
  @mock.patch.object(acme_utils, 'get_full_test_configs', autospec=True)
  def test_get_module_execution_plan_map_with_invalid_inputs(
      self, mock_get_configs, mock_print_and_log_warning
  ):
    """Test get_module_execution_plan_map exits when an invalid config is given."""
    mock_get_configs.return_value = TEST_CONFIGS
    base_error_message = 'Unable to find all test configs.'
    test_cases = {
        'invalid_plan': {
            'plans': ['invalid-plan'],
            'workflows': [],
            'triggers': [],
            'expected_message': (
                f'{base_error_message}\n'
                "Missing test execution plans: {'invalid-plan'}"
            ),
        },
        'invalid_workflow': {
            'plans': [],
            'workflows': ['invalid-workflow'],
            'triggers': [],
            'expected_message': (
                f'{base_error_message}\n'
                "Missing test workflows: {'invalid-workflow'}"
            ),
        },
        'invalid_trigger': {
            'plans': [],
            'workflows': [],
            'triggers': ['invalid-trigger'],
            'expected_message': (
                f'{base_error_message}\n'
                "Missing test triggers: {'invalid-trigger'}"
            ),
        },
        'all_invalid': {
            'plans': ['invalid-plan'],
            'workflows': ['invalid-workflow'],
            'triggers': ['invalid-trigger'],
            'expected_message': (
                f'{base_error_message}\n'
                "Missing test execution plans: {'invalid-plan'}\n"
                "Missing test workflows: {'invalid-workflow'}\n"
                "Missing test triggers: {'invalid-trigger'}"
            ),
        },
    }
    for name, inputs in test_cases.items():
      with self.subTest(name):
        mock_print_and_log_warning.reset_mock()
        with mock.patch.object(sys, 'exit', autospec=True) as mock_sys_exit:
          run_direct_mode.get_module_execution_plan_map(
              test_execution_plan_names=inputs['plans'],
              test_workflow_names=inputs['workflows'],
              test_trigger_names=inputs['triggers'],
          )
          mock_sys_exit.assert_called_with(atest_enum.ExitCode.TEST_NOT_FOUND)
        mock_print_and_log_warning.assert_any_call(inputs['expected_message'])

  @mock.patch(
      'atest.acme.run_direct_mode.atest_utils.print_and_log_warning',
      autospec=True,
  )
  @mock.patch.object(
      run_direct_mode, '_get_test_execution_plans', autospec=True
  )
  def test_get_test_details_all_tests_disabled(
      self, mock_get_exec_plans, mock_print_and_log_warning
  ):
    """Test get_test_details exits if all tests are disabled."""
    mock_get_exec_plans.return_value = [
        test_configs_pb2.TestExecutionPlan(name='sample', tests=[])
    ]
    with mock.patch.object(sys, 'exit', autospec=True) as mock_sys_exit:
      run_direct_mode.get_test_details()
      mock_sys_exit.assert_called_with(atest_enum.ExitCode.TEST_NOT_FOUND)
      mock_print_and_log_warning.assert_any_call(
          'All tests for the given test execution plans were disabled.'
      )

  @mock.patch(
      'atest.acme.run_direct_mode.atest_utils.print_and_log_warning',
      autospec=True,
  )
  @mock.patch.object(
      run_direct_mode, '_get_test_execution_plans', autospec=True
  )
  def test_get_module_execution_plan_map_all_tests_disabled(
      self, mock_get_exec_plans, mock_print_and_log_warning
  ):
    """Test get_module_execution_plan_map exits if all tests are disabled."""
    mock_get_exec_plans.return_value = [
        test_configs_pb2.TestExecutionPlan(name='sample', tests=[])
    ]
    with mock.patch.object(sys, 'exit', autospec=True) as mock_sys_exit:
      run_direct_mode.get_module_execution_plan_map()
      mock_sys_exit.assert_called_with(atest_enum.ExitCode.TEST_NOT_FOUND)
      mock_print_and_log_warning.assert_any_call(
          'All tests for the given test execution plans were disabled.'
      )

  @mock.patch.object(acme_utils, 'get_full_test_configs', autospec=True)
  def test_get_test_details_end_to_end(self, mock_get_configs):
    """Test get_test_details."""
    mock_get_configs.return_value = TEST_CONFIGS

    tests, test_details = run_direct_mode.get_test_details(
        test_execution_plan_names=[
            acme_test_constants.TEST_EXECUTION_PLAN_3.name
        ],
        test_workflow_names=[acme_test_constants.TEST_WORKFLOW_2.name],
        test_trigger_names=[
            acme_test_constants.TEST_TRIGGER_LIST_WORKFLOW.name
        ],
    )
    actual_return_val = zip(tests, test_details)
    expected_return_val = zip(
        [
            unittest_constants.MODULE2_NAME,
            unittest_constants.MODULE2_NAME,
            unittest_constants.MODULE_NAME,
            unittest_constants.MODULE_NAME,
        ],
        [
            acme_test_constants.MODULE2_PLAN_SIMPLE_TEST_DETAILS,
            acme_test_constants.MODULE2_PLAN_TEST_DETAILS,
            acme_test_constants.MODULE_PLAN_SIMPLE_TEST_DETAILS,
            acme_test_constants.MODULE_PLAN_TEST_DETAILS,
        ],
    )

    self.assertCountEqual(list(expected_return_val), list(actual_return_val))

  @mock.patch.object(acme_utils, 'get_full_test_configs', autospec=True)
  def test_get_module_execution_plan_map_end_to_end(self, mock_get_configs):
    """Test get_module_execution_plan_map."""
    mock_get_configs.return_value = TEST_CONFIGS

    mep = run_direct_mode.get_module_execution_plan_map(
        test_execution_plan_names=[
            acme_test_constants.TEST_EXECUTION_PLAN_3.name
        ],
        test_workflow_names=[acme_test_constants.TEST_WORKFLOW_2.name],
        test_trigger_names=[
            acme_test_constants.TEST_TRIGGER_LIST_WORKFLOW.name
        ],
    )

    self.assertCountEqual(
        [
            unittest_constants.MODULE_NAME,
            unittest_constants.MODULE2_NAME,
        ],
        mep.get_all_module_names(),
    )
    self.assertEqual(
        {
            acme_test_constants.TEST_EXECUTION_PLAN.name,
            acme_test_constants.TEST_EXECUTION_PLAN_2.name,
            acme_test_constants.TEST_EXECUTION_PLAN_3.name,
        },
        mep.get_execution_plans_for_module(unittest_constants.MODULE2_NAME),
    )


if __name__ == '__main__':
  unittest.main()
