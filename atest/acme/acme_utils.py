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

import dataclasses
import pathlib
import subprocess
import typing

from atest import atest_utils
from atest import constants
from atest import test_mapping
from atest.test_finders.test_info import TestInfo
from test_configs_proto import test_configs_pb2


REDUCE_TEST_CONFIGS_CMD = 'build/soong/testconfigs/scripts/reduce-test-configs'
REDUCE_TEST_CONFIGS_OUTPUT_SUB_PATH = (
    'soong/test-configs-reduced/test_configs.pb'
)

TEST_CONFIGS_BUILD_TARGET = 'test-configs-zip'
TEST_CONFIGS_OUTPUT_SUB_PATH = 'soong/test-configs/test_configs.pb'
TEST_CONFIGS_ZIP_PATH = 'soong/test-configs.zip'


@dataclasses.dataclass(frozen=True)
class ModuleExecutionPlanMap:
  """Mapping of module names to their associated test execution plans."""

  _mapping: dict[str, set[str]]

  def get_all_module_names(self) -> list[str]:
    """Returns a list of all module names."""
    return list(self._mapping.keys())

  def get_execution_plans_for_module(self, module_name: str) -> set[str]:
    """Returns the set of execution plan names for a given module."""
    return self._mapping.get(module_name, set())

  def add_execution_plans_to_test_infos(self, test_infos):
    """Adds the associated execution plans to the given TestInfos."""
    for ti in test_infos:
      ti.data['execution_plans'] = list(
          self.get_execution_plans_for_module(ti.test_name)
      )
    return test_infos


def _parse_test_configs_proto(
    test_configs_proto_path: pathlib.Path,
) -> test_configs_pb2.TestConfigs:
  """Parses a TestConfigs proto from a file."""
  with open(test_configs_proto_path, 'rb') as f:
    test_configs = test_configs_pb2.TestConfigs()
    test_configs.ParseFromString(f.read())
  return test_configs


def get_full_test_configs() -> test_configs_pb2.TestConfigs:
  """Returns the complete set of TestConfigs."""
  atest_utils.build([TEST_CONFIGS_BUILD_TARGET])
  output_path = atest_utils.get_build_out_dir(TEST_CONFIGS_OUTPUT_SUB_PATH)
  return _parse_test_configs_proto(output_path)


def get_reduced_test_configs(
    projects: list[typing.Optional[str]] | None = None,
    file_paths: list[typing.Optional[str]] | None = None,
) -> test_configs_pb2.TestConfigs:
  """Runs the reduce-test-configs script and returns the TestConfigs proto."""

  cmd = [REDUCE_TEST_CONFIGS_CMD]
  if projects:
    cmd.append('-projects')
    cmd.extend(projects)
  if file_paths:
    cmd.append('--filepaths')
    relative_file_paths, _ = get_file_paths_relative_to_build_top(file_paths)
    cmd.extend(relative_file_paths)

  # TODO: b/460119831 - Return a more informative error message.
  subprocess.run(cmd, cwd=atest_utils.get_build_top(), check=True)
  output_path = atest_utils.get_build_out_dir(
      REDUCE_TEST_CONFIGS_OUTPUT_SUB_PATH
  )
  return _parse_test_configs_proto(output_path)


def get_file_paths_relative_to_build_top(
    file_paths: list[str],
) -> tuple([list[str], list[str]]):
  """Returns file paths relative to build top and a list of invalid paths."""
  relative_paths = []
  invalid_file_paths = []
  for fp in file_paths:
    try:
      resolved_path = pathlib.Path(fp).resolve(strict=True)
      relative_paths.append(
          str(resolved_path.relative_to(atest_utils.get_build_top()))
      )
    except FileNotFoundError:
      invalid_file_paths.append(fp)
  return relative_paths, invalid_file_paths


def get_current_project() -> typing.Optional[str]:
  """Returns the current repo project."""
  ret = subprocess.run(
      "repo forall . -c 'echo $REPO_PROJECT'",
      shell=True,
      check=False,
      capture_output=True,
      encoding='utf-8',
  )
  if not ret.returncode:
    return ret.stdout.strip()


def get_filtered_test_execution_plans(
    test_configs: test_configs_pb2.TestConfigs, scheduling_plan_name: str
) -> list[test_configs_pb2.TestExecutionPlan]:
  """Returns TestExecutionPlans from TestConfigs for a scheduling plan."""

  # Create a mapping from execution plan name to the plan object.
  named_test_exec_plans_map = {
      exec_plan.name: exec_plan for exec_plan in test_configs.execution_plans
  }

  # Create a mapping from execution plan name to the plan object.
  named_test_workflows_map = {
      workflow.name: workflow for workflow in test_configs.workflows
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
        # Search for the workflow in the named_test_workflows_map if the
        # workflow proto only contains a reference.
        if not workflow.HasField('scheduling_plan'):
          workflow = named_test_workflows_map.get(workflow.name)

        if workflow.scheduling_plan.name != scheduling_plan_name:
          continue

        test_exec_plan_name = workflow.execution_plan.name
        test_exec_plan = named_test_exec_plans_map.get(test_exec_plan_name)
        if test_exec_plan:
          test_execution_plans.append(test_exec_plan)

  return test_execution_plans


def get_test_execution_plans(
    test_configs: test_configs_pb2.TestConfigs,
    test_execution_plan_names: list[str],
) -> list[test_configs_pb2.TestExecutionPlan]:
  """Returns the TestExecutionPlans for the given test_execution_plan_names."""
  test_execution_plans = []
  for test_execution_plan in test_configs.execution_plans:
    if test_execution_plan.name in test_execution_plan_names:
      test_execution_plans.append(test_execution_plan)
  return test_execution_plans


def get_execution_plans_for_test_workflows(
    test_configs: test_configs_pb2.TestConfigs, test_workflow_names: list[str]
) -> list[test_configs_pb2.TestExecutionPlan]:
  """Returns the TestExecutionPlans referenced in the given test_workflows."""
  test_execution_plan_names = []
  for workflow in test_configs.workflows:
    if workflow.name in test_workflow_names:
      test_execution_plan_names.append(workflow.execution_plan.name)
  return get_test_execution_plans(test_configs, test_execution_plan_names)


def get_execution_plans_for_test_triggers(
    test_configs: test_configs_pb2.TestConfigs, test_trigger_names: list[str]
) -> list[test_configs_pb2.TestExecutionPlan]:
  """Returns the TestExecutionPlans referenced in the given test_triggers."""
  test_workflow_names = []
  for test_trigger in test_configs.triggers:
    if test_trigger.name in test_trigger_names:
      # Get all the TestWorkflows referenced in the TestTrigger.
      test_workflow_names.extend(
          [workflow.name for workflow in test_trigger.list.workflows]
      )
  return get_execution_plans_for_test_workflows(
      test_configs, test_workflow_names
  )


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


def use_atest_execution_plan_suite_runner(test_infos: list[TestInfo]) -> bool:
  """Returns true if the test_infos contains execution plans."""
  return test_infos and test_infos[0].data.get('execution_plans', [])


def create_atest_execution_plan_suite_runner_test_args(
    test_infos: list[TestInfo],
) -> list[str]:
  """Create test arguments for invoking AtestExecutionPlanSuiteRunner."""
  args = []
  unique_exec_plans = []
  for ti in test_infos:
    unique_exec_plans.extend(ti.data.get('execution_plans', []))
  for exec_plan in unique_exec_plans:
    args.append('--execution-plans')
    args.append(exec_plan)
  test_configs_zip_path = atest_utils.get_build_out_dir(TEST_CONFIGS_ZIP_PATH)
  args.extend(['--extra-file', f'test-configs.zip={test_configs_zip_path}'])
  args.extend(['--config-zip-paths', 'test-configs.zip'])
  return args
