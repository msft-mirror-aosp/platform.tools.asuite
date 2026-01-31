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

"""Module for running test triggers affected by the relevant files."""

import argparse
import collections
import sys
import typing

from atest import atest_enum
from atest import atest_utils
from atest import test_mapping
from atest.acme import acme_utils
from atest.metrics import metrics
from test_configs_proto import test_configs_pb2

RUN_AFFECTED_TRIGGERS_ARG_NAME = '--run-affected-triggers'
SCHEDULING_PLAN_ARG_NAME = '--scheduling-plan'
DEFAULT_SCHEDULING_PLAN = 'presubmit'
CURRENT_PROJECT_ARG_NAME = '--current-project'
PROJECTS_ARG_NAME = '--projects'
FILE_PATHS_ARG_NAME = '--file-paths'


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
  parser.add_argument(
      CURRENT_PROJECT_ARG_NAME,
      default=False,
      action='store_true',
      help=(
          '(For use with --run-affected-triggers) Only find affected triggers'
          ' within the current project. Cannot be used in conjunction with'
          ' --projects or --file-paths.'
      ),
  )
  parser.add_argument(
      PROJECTS_ARG_NAME,
      default=[],
      nargs='*',
      help=(
          '(For use with --run-affected-triggers) Only find affected triggers'
          ' within the specified projects. Cannot be used in conjunction with'
          ' --file-paths or --current-project.'
      ),
  )
  parser.add_argument(
      FILE_PATHS_ARG_NAME,
      default=[],
      nargs='*',
      help=(
          '(For use with --run-affected-triggers) Override discovered affected'
          ' paths with explicit list of file paths. File paths are relative to'
          'cwd. Cannot be used in conjunction with --projects or'
          ' --current-project.'
      ),
  )


def process_parsed_args(args: argparse.Namespace):
  """Processes --run-affected-triggers related arguments."""
  if args.run_affected_triggers:
    metrics.LocalDetectEvent(
        detect_type=atest_enum.DetectType.RUN_AFFECTED_TRIGGERS_MODE, result=1
    )
    # Check that only one of the three args is used.
    if (
        sum(
            1
            for arg in (args.file_paths, args.projects, args.current_project)
            if arg
        )
        > 1
    ):
      atest_utils.print_and_log_error(
          'Only one of --projects, --file-paths or --current-project can be'
          ' used with --run-affected-triggers.'
      )
      sys.exit(atest_enum.ExitCode.INVALID_RUN_AFFECTED_TRIGGERS_ARGS)
  if args.file_paths:
    _ensure_file_paths_exist(args.file_paths)
  if args.current_project and not acme_utils.get_current_project():
    atest_utils.print_and_log_error(
        'Unable to determine the current repo project.'
    )
    sys.exit(atest_enum.ExitCode.INVALID_RUN_AFFECTED_TRIGGERS_ARGS)


def _ensure_file_paths_exist(file_paths):
  """Validate the input filepaths exist."""
  _, invalid_file_paths = acme_utils.get_file_paths_relative_to_build_top(
      file_paths
  )
  if invalid_file_paths:
    atest_utils.print_and_log_error(
        f'The following input file paths do not exist: {invalid_file_paths}'
    )
    sys.exit(atest_enum.ExitCode.INVALID_RUN_AFFECTED_TRIGGERS_ARGS)


def get_module_execution_plan_map(
    scheduling_plan_name: str,
    current_project: bool | None = None,
    projects: list[typing.Optional[str]] | None = None,
    file_paths: list[typing.Optional[str]] | None = None,
) -> acme_utils.ModuleExecutionPlanMap:
  """Returns the ModuleExecutionPlanMap for the affected TestExecutionPlans."""
  test_execution_plans = _get_test_execution_plans(
      scheduling_plan_name, current_project, projects, file_paths
  )
  module_to_exec_plan_names_dict = collections.defaultdict(set)
  for test_exec_plan in test_execution_plans:
    for module_plan in test_exec_plan.tests:
      module_to_exec_plan_names_dict[module_plan.module].add(
          test_exec_plan.name
      )

  return acme_utils.ModuleExecutionPlanMap(module_to_exec_plan_names_dict)


def _get_test_execution_plans(
    scheduling_plan_name: str,
    current_project: bool | None = None,
    projects: list[typing.Optional[str]] | None = None,
    file_paths: list[typing.Optional[str]] | None = None,
) -> [test_configs_pb2.TestExecutionPlan]:
  """Returns the TestDetails for the relevant TestExecutionPlans."""
  if current_project:
    projects = [acme_utils.get_current_project()]
  file_paths = file_paths or []
  relative_file_paths, _ = acme_utils.get_file_paths_relative_to_build_top(
      file_paths
  )
  test_configs = acme_utils.get_reduced_test_configs(
      projects, relative_file_paths
  )
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
  return test_execution_plans


def get_affected_test_details(
    scheduling_plan_name: str,
    current_project: bool | None = None,
    projects: list[typing.Optional[str]] | None = None,
    file_paths: list[typing.Optional[str]] | None = None,
) -> tuple[list[str], list[test_mapping.TestDetail]]:
  """Returns the TestDetails for the relevant TestExecutionPlans."""
  metrics.LocalDetectEvent(
      detect_type=atest_enum.DetectType.RUN_AFFECTED_TRIGGERS_MODE, result=1
  )
  test_execution_plans = _get_test_execution_plans(
      scheduling_plan_name, current_project, projects, file_paths
  )
  test_details = acme_utils.create_test_details_from_test_execution_plans(
      test_execution_plans
  )

  tests = [x.name for x in test_details]
  return tests, test_details
