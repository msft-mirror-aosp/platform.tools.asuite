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

import argparse
import subprocess
import sys

from atest import atest_enum
from atest import atest_utils
from atest import constants
from atest import test_mapping
from test_configs_proto import test_configs_pb2

RUN_AFFECTED_ARG_NAME = '--run-affected'
REDUCE_TEST_CONFIGS_CMD = 'build/soong/testconfigs/scripts/reduce-test-configs'


def add_global_arguments(parser: argparse.ArgumentParser):
  """Adds flags for running ACME test configs to the global argument parser."""

  parser.add_argument(
      RUN_AFFECTED_ARG_NAME,
      default=False,
      action='store_true',
      help=(
          'Run all tests defined in test_execution_plans affected by the'
          ' locally modified files.'
      ),
  )


def _get_affected_test_execution_plans() -> (
    list[test_configs_pb2.TestExecutionPlan]
):
  """Returns the execution plans affected by the changes in the checkout."""
  subprocess.run(
      REDUCE_TEST_CONFIGS_CMD, cwd=atest_utils.get_build_top(), check=True
  )
  output_path = atest_utils.get_build_out_dir(
      'soong/test-configs/test_configs.pb'
  )
  with open(output_path, 'rb') as f:
    test_configs = test_configs_pb2.TestConfigs()
    test_configs.ParseFromString(f.read())
  test_exec_plans = test_configs.execution_plans
  for test_trigger in test_configs.triggers:
    module_plans = test_trigger.inline.tests
    test_exec_plans.append(
        test_configs_pb2.TestExecutionPlan(tests=module_plans)
    )
  return test_exec_plans


def _create_test_details_from_test_exec_plans(
    test_exec_plans: list[test_configs_pb2.TestExecutionPlan],
) -> tuple[list[str], list[test_mapping.TestDetail]]:
  """Parses TestExecutionPlans into lists of test modules and test details."""
  tests, test_details = [], []
  unique_test_details = set()
  for test_exec_plan in test_exec_plans:
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
      # Deduplicate identical TestDetails
      if test_detail not in unique_test_details:
        unique_test_details.add(test_detail)
        tests.append(module_plan.module)
        test_details.append(test_mapping.TestDetail(detail_dict))
  return tests, test_details


def get_affected_test_details() -> list[test_mapping.TestDetail]:
  """Returns the TestDetails for the relevant TestExecutionPlans."""
  exec_plans = _get_affected_test_execution_plans()
  tests, test_details = _create_test_details_from_test_exec_plans(exec_plans)
  if not tests:
    atest_utils.print_and_log_warning(
        'No relevant test execution configs found.'
    )
    sys.exit(atest_enum.ExitCode.TEST_NOT_FOUND)
  return tests, test_details
