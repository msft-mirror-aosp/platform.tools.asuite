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
import sys
import unittest

from atest import atest_enum
from atest import atest_utils
from atest import constants
from atest import test_mapping
from atest import unittest_constants
from atest.acme import acme_utils
from test_configs_proto import test_configs_pb2

MOCK_BUILD_TOP_PATH = pathlib.Path('/build/top')

# Sample Soong Test Configs.
MODULE_PLAN = test_configs_pb2.ModulePlan(
    module=unittest_constants.MODULE_NAME,
    include=['include-filter1', 'include-filter2'],
    exclude=['exclude-filter1', 'exclude-filter2'],
    module_args=[test_configs_pb2.KeyValue(key='arg1', value='val1')],
)
MODULE_PLAN_SIMPLE = test_configs_pb2.ModulePlan(
    module=unittest_constants.MODULE_NAME,
)
MODULE2_PLAN = test_configs_pb2.ModulePlan(
    module=unittest_constants.MODULE2_NAME,
)
TEST_EXECUTION_PLAN = test_configs_pb2.TestExecutionPlan(
    name='sample-test-execution-plan', tests=[MODULE_PLAN, MODULE2_PLAN]
)
TEST_TRIGGER_INLINE_TESTS = test_configs_pb2.TestTrigger(
    name='sample-inlined-test-trigger',
    inline=test_configs_pb2.TestWorkflowInline(
        tests=[MODULE2_PLAN, MODULE_PLAN_SIMPLE]
    ),
)

SAMPLE_TEST_CONFIG = test_configs_pb2.TestConfigs(
    execution_plans=[TEST_EXECUTION_PLAN],
    triggers=[TEST_TRIGGER_INLINE_TESTS],
)
MODULE_PLAN_TEST_DETAILS = test_mapping.TestDetail({
    'name': unittest_constants.MODULE_NAME,
    'options': [
        {constants.TF_INCLUDE_FILTER_OPTION: 'include-filter1'},
        {constants.TF_INCLUDE_FILTER_OPTION: 'include-filter2'},
        {constants.TF_EXCLUDE_FILTER_OPTION: 'exclude-filter1'},
        {constants.TF_EXCLUDE_FILTER_OPTION: 'exclude-filter2'},
        {'arg1': 'val1'},
    ],
})
MODULE_PLAN_SIMPLE_TEST_DETAILS = test_mapping.TestDetail(
    {'name': unittest_constants.MODULE_NAME}
)
MODULE2_PLAN_TEST_DETAILS = test_mapping.TestDetail(
    {'name': unittest_constants.MODULE2_NAME}
)


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
        read_data=SAMPLE_TEST_CONFIG.SerializeToString()
    )
    mock_open_builtin.return_value = mock_file.return_value

    # Function call.
    test_configs = acme_utils.get_reduced_test_configs()

    # Assertions.
    self.assertEqual(SAMPLE_TEST_CONFIG, test_configs)
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
        name='test-exec-plan1', tests=[MODULE_PLAN, MODULE2_PLAN]
    )
    # One ModulePlan with same module name, but different options.
    # One ModulePlan that is identical and should be deduped.
    test_exec_plan2 = test_configs_pb2.TestExecutionPlan(
        name='test-exec-plan2', tests=[MODULE_PLAN_SIMPLE, MODULE2_PLAN]
    )
    test_details = acme_utils.create_test_details_from_test_execution_plans(
        [test_exec_plan1, test_exec_plan2]
    )
    expected_test_details = [
        MODULE_PLAN_TEST_DETAILS,
        MODULE_PLAN_SIMPLE_TEST_DETAILS,
        MODULE2_PLAN_TEST_DETAILS,
    ]
    self.assertCountEqual(expected_test_details, test_details)

  def test_get_filtered_test_execution_plans(self):
    """Tests getting TestExecutionPlans from a TestConfigs object."""
    inline_test_execution_plan = test_configs_pb2.TestExecutionPlan(
        tests=[MODULE2_PLAN, MODULE_PLAN_SIMPLE]
    )
    expected_test_execution_plans = [
        inline_test_execution_plan,
        TEST_EXECUTION_PLAN,
    ]
    test_execution_plans = acme_utils.get_filtered_test_execution_plans(
        SAMPLE_TEST_CONFIG
    )
    self.assertCountEqual(expected_test_execution_plans, test_execution_plans)

  @unittest.mock.patch.object(atest_utils, 'get_build_out_dir', autospec=True)
  @unittest.mock.patch.object(subprocess, 'run', autospec=True)
  @unittest.mock.patch('builtins.open')
  @unittest.mock.patch.object(
      atest_utils,
      'get_build_top',
      autospec=True,
      return_value=MOCK_BUILD_TOP_PATH,
  )
  def test_get_affected_test_details(
      self,
      mock_get_build_top,
      mock_open_builtin,
      mock_subprocess_run,
      mock_get_build_out_dir,
  ):
    """Tests successful getting TestDetails for affected TestTriggers."""
    # Set up mocks.
    fake_pb_path = '/fake/path/to/test-configs.pb'
    mock_get_build_out_dir.return_value = fake_pb_path

    mock_file = unittest.mock.mock_open(
        read_data=SAMPLE_TEST_CONFIG.SerializeToString()
    )
    mock_open_builtin.return_value = mock_file.return_value

    # Function call.
    tests, test_details = acme_utils.get_affected_test_details()
    actual_return_val = zip(tests, test_details)
    expected_return_val = zip(
        [
            unittest_constants.MODULE_NAME,
            unittest_constants.MODULE2_NAME,
            unittest_constants.MODULE_NAME,
        ],
        [
            MODULE_PLAN_TEST_DETAILS,
            MODULE2_PLAN_TEST_DETAILS,
            MODULE_PLAN_SIMPLE_TEST_DETAILS,
        ],
    )

    self.assertCountEqual(expected_return_val, actual_return_val)
    mock_get_build_top.assert_called_once()
    mock_subprocess_run.assert_called_once_with(
        acme_utils.REDUCE_TEST_CONFIGS_CMD, cwd=MOCK_BUILD_TOP_PATH, check=True
    )
    mock_open_builtin.assert_called_once_with(fake_pb_path, 'rb')

  @unittest.mock.patch.object(atest_utils, 'get_build_out_dir', autospec=True)
  @unittest.mock.patch.object(subprocess, 'run', autospec=True)
  @unittest.mock.patch('builtins.open')
  @unittest.mock.patch.object(
      atest_utils,
      'get_build_top',
      autospec=True,
      return_value=MOCK_BUILD_TOP_PATH,
  )
  def test_get_affected_test_details_no_tests_found(
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
        read_data=test_configs_pb2.TestConfigs().SerializeToString()
    )
    mock_open_builtin.return_value = mock_file.return_value

    mock_sys_exit = self.enterContext(
        unittest.mock.patch.object(sys, 'exit', autospec=True)
    )

    # Function call.
    acme_utils.get_affected_test_details()

    # Assertions.
    mock_get_build_top.assert_called_once()
    mock_sys_exit.assert_called_once_with(atest_enum.ExitCode.TEST_NOT_FOUND)
    mock_subprocess_run.assert_called_once_with(
        acme_utils.REDUCE_TEST_CONFIGS_CMD, cwd=MOCK_BUILD_TOP_PATH, check=True
    )
    mock_open_builtin.assert_called_once_with(fake_pb_path, 'rb')


if __name__ == '__main__':
  unittest.main()
