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

"""Module for running test triggers affected by the locally modified files."""

import argparse
import sys

from atest import atest_enum
from atest import atest_utils
from atest import test_mapping
from atest.acme import acme_utils

RUN_AFFECTED_TRIGGERS_ARG_NAME = '--run-affected-triggers'
SCHEDULING_PLAN_ARG_NAME = '--scheduling-plan'
DEFAULT_SCHEDULING_PLAN = 'presubmit'


def add_global_arguments(parser: argparse.ArgumentParser):
  """Adds flags for running ACME test configs to the global argument parser."""

  parser.add_argument(
      RUN_AFFECTED_TRIGGERS_ARG_NAME,
      default=False,
      action='store_true',
      help=(
          'Run all tests defined in the test_triggers affected by the'
          ' locally modified files.'
      ),
  )


def add_arguments(parser: argparse.ArgumentParser):
  """Adds arguments specific to --run-affected-triggers mode to the argument parser."""
  parser.add_argument(
      SCHEDULING_PLAN_ARG_NAME,
      type=str,
      help=(
          '(For use with --run-affected-triggers) Only consider'
          ' test_execution_plans for the given scheduling plan. Defaults to'
          ' "presubmit".'
      ),
      default=DEFAULT_SCHEDULING_PLAN,
  )


# pylint: disable=unused-argument
def process_parsed_args(args: argparse.Namespace):
  """Processes --run-affected-triggers related arguments."""
  pass


def get_affected_test_details(
    scheduling_plan_name: str,
) -> tuple[list[str], list[test_mapping.TestDetail]]:
  """Returns the TestDetails for the relevant TestExecutionPlans."""
  test_configs = acme_utils.get_reduced_test_configs()
  if not test_configs:
    atest_utils.print_and_log_warning(
        'No affected tests found based on the local changes.'
    )
    sys.exit(atest_enum.ExitCode.TEST_NOT_FOUND)

  test_execution_plans = acme_utils.get_filtered_test_execution_plans(
      test_configs, scheduling_plan_name
  )
  if not test_execution_plans:
    available_scheduling_plans = [x.name for x in test_configs.scheduling_plans]
    atest_utils.print_and_log_warning(
        f'No affected tests found for scheduling plan {scheduling_plan_name}.'
        f' Available scheduling plans: {available_scheduling_plans}'
    )
    sys.exit(atest_enum.ExitCode.TEST_NOT_FOUND)
  test_details = acme_utils.create_test_details_from_test_execution_plans(
      test_execution_plans
  )

  tests = [x.name for x in test_details]
  return tests, test_details
