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

import pathlib
import subprocess
import unittest

from atest import atest_utils
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
    """Tests successful getting TestDetails for relevant TestTriggers."""
    # Set up mocks.
    fake_pb_path = '/fake/path/to/test-configs.pb'
    mock_get_build_out_dir.return_value = fake_pb_path
    mock_file = unittest.mock.mock_open(
        read_data=acme_test_constants.SAMPLE_TEST_CONFIG.SerializeToString()
    )
    mock_open_builtin.return_value = mock_file.return_value

    # Function call.
    test_configs = acme_utils.get_reduced_test_configs()

    # Assertions.
    self.assertEqual(acme_test_constants.SAMPLE_TEST_CONFIG, test_configs)
    mock_get_build_top.assert_called_once()
    mock_subprocess_run.assert_called_once_with(
        acme_utils.REDUCE_TEST_CONFIGS_CMD, cwd=MOCK_BUILD_TOP_PATH, check=True
    )
    mock_open_builtin.assert_called_once_with(fake_pb_path, 'rb')

  @unittest.mock.patch.object(subprocess, 'run', autospec=True)
  @unittest.mock.patch.object(
      atest_utils,
      'get_build_top',
      autospec=True,
      return_value=MOCK_BUILD_TOP_PATH,
  )
  def test_build_reduced_test_configs_call_error(
      self,
      mock_get_build_top,
      mock_subprocess_run,
  ):
    """Tests successful getting TestDetails for relevant TestTriggers."""
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
        acme_utils.REDUCE_TEST_CONFIGS_CMD, cwd=MOCK_BUILD_TOP_PATH, check=True
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

  def test_get_filtered_test_execution_plans_all_filtered_out(self):
    """Tests getting execution plans when none belong to the scheduling plan."""
    expected_test_execution_plans = []
    test_execution_plans = acme_utils.get_filtered_test_execution_plans(
        acme_test_constants.SAMPLE_TEST_CONFIG,
        'some-other-scheduling-plan',
    )
    self.assertCountEqual(expected_test_execution_plans, test_execution_plans)


if __name__ == '__main__':
  unittest.main()
