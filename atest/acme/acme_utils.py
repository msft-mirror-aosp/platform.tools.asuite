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

"""Util functions for running ACME Test Configurations via atest."""

import subprocess

from atest import atest_utils
from atest import constants
from atest import test_mapping
from test_configs_proto import test_configs_pb2

REDUCE_TEST_CONFIGS_CMD = 'build/soong/testconfigs/scripts/reduce-test-configs'
REDUCE_TEST_CONFIGS_OUTPUT_SUB_PATH = (
    'soong/test-configs-reduced/test_configs.pb'
)


def get_reduced_test_configs() -> test_configs_pb2.TestConfigs:
  """Runs the reduce-test-configs script and returns the TestConfigs proto."""
  # TODO: b/460119831 - Return a more informative error message.
  subprocess.run(
      REDUCE_TEST_CONFIGS_CMD, cwd=atest_utils.get_build_top(), check=True
  )
  output_path = atest_utils.get_build_out_dir(
      REDUCE_TEST_CONFIGS_OUTPUT_SUB_PATH
  )
  with open(output_path, 'rb') as f:
    test_configs = test_configs_pb2.TestConfigs()
    test_configs.ParseFromString(f.read())
  return test_configs


def get_filtered_test_execution_plans(
    test_configs: test_configs_pb2.TestConfigs, scheduling_plan_name: str
) -> list[test_configs_pb2.TestExecutionPlan]:
  """Returns TestExecutionPlans from TestConfigs for a scheduling plan."""

  # Create a mapping from execution plan name to the plan object.
  named_test_exec_plans_map = {
      exec_plan.name: exec_plan for exec_plan in test_configs.execution_plans
  }

  # Filter test execution plans based on the scheduling plan.
  test_execution_plans = []
  for test_trigger in test_configs.triggers:
    # Handle inline workflows.
    if test_trigger.inline.scheduling_plan.name == scheduling_plan_name:
      test_exec_plan = test_configs_pb2.TestExecutionPlan(
          name=f'{test_trigger.name}_inline_plan',  # Give it a unique name.
          tests=test_trigger.inline.tests,
      )
      test_execution_plans.append(test_exec_plan)
    # Handle a list workflows.
    else:
      for workflow in test_trigger.list.workflows:
        if workflow.scheduling_plan.name != scheduling_plan_name:
          continue
        test_exec_plan_name = workflow.execution_plan.name
        test_exec_plan = named_test_exec_plans_map.get(test_exec_plan_name)
        if test_exec_plan:
          test_execution_plans.append(test_exec_plan)

  return test_execution_plans


def create_test_details_from_test_execution_plans(
    test_execution_plans: list[test_configs_pb2.TestExecutionPlan],
) -> list[test_mapping.TestDetail]:
  """Parses TestExecutionPlans into a list of test details."""
  test_details = set()
  for test_exec_plan in test_execution_plans:
    for module_plan in test_exec_plan.tests:
      detail_dict = {'name': module_plan.module, 'options': []}
      for include_filter in module_plan.include:
        detail_dict['options'].append(
            {constants.TF_INCLUDE_FILTER_OPTION: include_filter}
        )
      for exclude_filter in module_plan.exclude:
        detail_dict['options'].append(
            {constants.TF_EXCLUDE_FILTER_OPTION: exclude_filter}
        )
      for arg in module_plan.module_args:
        detail_dict['options'].append({arg.key: arg.value})
      test_detail = test_mapping.TestDetail(detail_dict)
      # Deduplicate identical TestDetails.
      test_details.add(test_detail)
  return list(test_details)
