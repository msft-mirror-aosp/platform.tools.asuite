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

"""Module for running test config modules directly."""

import argparse
import collections
import sys

from atest import atest_enum
from atest import atest_utils
from atest import test_mapping
from atest.acme import acme_utils
from test_configs_proto import test_configs_pb2


RUN_TEST_EXECUTION_PLANS_ARG_NAME = '--test-execution-plans'
RUN_TEST_TRIGGERS_ARG_NAME = '--test-triggers'
RUN_TEST_WORKFLOWS_ARG_NAME = '--test-workflows'


def add_global_arguments(parser: argparse.ArgumentParser):
  """Adds flags for running test configs directly to the global argument parser."""
  parser.add_argument(
      RUN_TEST_EXECUTION_PLANS_ARG_NAME,
      default=[],
      nargs='+',
      help='Run the specified test execution plans.',
  )
  parser.add_argument(
      RUN_TEST_TRIGGERS_ARG_NAME,
      default=[],
      nargs='+',
      help=(
          'Run the test execution plans referenced in the specified test'
          ' triggers.'
      ),
  )
  parser.add_argument(
      RUN_TEST_WORKFLOWS_ARG_NAME,
      default=[],
      nargs='+',
      help=(
          'Run the test execution plans referenced in the specified test'
          ' workflows.'
      ),
  )


# pylint: disable=unused-argument
def add_arguments(parser: argparse.ArgumentParser):
  """Adds arguments specific to run direct mode to the argument parser."""
  pass


# pylint: disable=unused-argument
def process_parsed_args(args: argparse.Namespace):
  """Processes run direct mode related arguments."""
  pass


def _ensure_input_test_configs_exist(
    test_configs,
    test_execution_plan_names,
    test_workflow_names,
    test_trigger_names,
):
  """Validate the input test configs are defined."""
  invalid_test_execution_plans = set(test_execution_plan_names) - set(
      x.name for x in test_configs.execution_plans
  )
  invalid_test_workflows = set(test_workflow_names) - set(
      x.name for x in test_configs.workflows
  )
  invalid_test_triggers = set(test_trigger_names) - set(
      x.name for x in test_configs.triggers
  )
  if any([
      invalid_test_execution_plans,
      invalid_test_triggers,
      invalid_test_workflows,
  ]):
    error_message = 'Unable to find all test configs.'
    if invalid_test_execution_plans:
      error_message += (
          f'\nMissing test execution plans: {invalid_test_execution_plans}'
      )
    if invalid_test_workflows:
      error_message += f'\nMissing test workflows: {invalid_test_workflows}'
    if invalid_test_triggers:
      error_message += f'\nMissing test triggers: {invalid_test_triggers}'
    atest_utils.print_and_log_warning(error_message)
    sys.exit(atest_enum.ExitCode.TEST_NOT_FOUND)


def get_module_execution_plan_map(
    test_execution_plan_names: list[str] | None = None,
    test_workflow_names: list[str] | None = None,
    test_trigger_names: list[str] | None = None,
) -> acme_utils.ModuleExecutionPlanMap:
  """Returns the ModuleExecutionPlanMap for the relevant TestExecutionPlans."""
  # Get ExecutionPlans from TestConfigs.
  test_execution_plans = _get_test_execution_plans(
      test_execution_plan_names=test_execution_plan_names or [],
      test_workflow_names=test_workflow_names or [],
      test_trigger_names=test_trigger_names or [],
  )

  module_to_exec_plan_names_dict = collections.defaultdict(set)
  for test_exec_plan in test_execution_plans:
    for module_plan in test_exec_plan.tests:
      module_to_exec_plan_names_dict[module_plan.module].add(
          test_exec_plan.name
      )
  if not module_to_exec_plan_names_dict:
    atest_utils.print_and_log_warning(
        'All tests for the given test execution plans were disabled.'
    )
    sys.exit(atest_enum.ExitCode.TEST_NOT_FOUND)

  return acme_utils.ModuleExecutionPlanMap(module_to_exec_plan_names_dict)


def _get_test_execution_plans(
    test_execution_plan_names: list[str] | None = None,
    test_workflow_names: list[str] | None = None,
    test_trigger_names: list[str] | None = None,
) -> [test_configs_pb2.TestExecutionPlan]:
  """Returns the TestExecutionPlans referenced in the given configs."""
  # Get TestConfigs and validate user input.
  test_configs = acme_utils.get_full_test_configs()
  _ensure_input_test_configs_exist(
      test_configs,
      test_execution_plan_names=test_execution_plan_names or [],
      test_workflow_names=test_workflow_names or [],
      test_trigger_names=test_trigger_names or [],
  )

  # Get ExecutionPlans from TestConfigs.
  execution_plans = (
      acme_utils.get_test_execution_plans(
          test_configs, test_execution_plan_names
      )
      + acme_utils.get_execution_plans_for_test_workflows(
          test_configs, test_workflow_names
      )
      + acme_utils.get_execution_plans_for_test_triggers(
          test_configs, test_trigger_names
      )
  )
  return execution_plans


def get_test_details(
    test_execution_plan_names: list[str] | None = None,
    test_workflow_names: list[str] | None = None,
    test_trigger_names: list[str] | None = None,
) -> list[test_mapping.TestDetail]:
  """Returns the TestDetails for all TestExecutionPlans in the given configs."""
  # Get TestConfigs and validate user input.
  execution_plans = _get_test_execution_plans(
      test_execution_plan_names=test_execution_plan_names or [],
      test_workflow_names=test_workflow_names or [],
      test_trigger_names=test_trigger_names or [],
  )

  # Get deduplicated TestDetails.
  test_details = acme_utils.create_test_details_from_test_execution_plans(
      execution_plans
  )

  tests = [x.name for x in test_details]
  if not tests:
    atest_utils.print_and_log_warning(
        'All tests for the given test execution plans were disabled.'
    )
    sys.exit(atest_enum.ExitCode.TEST_NOT_FOUND)
  return tests, test_details
