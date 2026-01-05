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

import sys
import unittest

from atest import atest_enum
from atest import unittest_constants
from atest.acme import acme_test_constants
from atest.acme import acme_utils
from atest.acme import run_affected_triggers_mode
from atest.metrics import metrics
from test_configs_proto import test_configs_pb2


class TestRunAffectedTriggersModeModule(unittest.TestCase):

  @unittest.mock.patch.object(metrics, 'LocalDetectEvent', autospec=True)
  @unittest.mock.patch.object(
      acme_utils, 'get_reduced_test_configs', autospec=True
  )
  def test_get_affected_test_details_no_affected_tests(
      self, mock_get_reduced_test_configs, mock_local_detect_event
  ):
    """Test get_affected_test_details exits if no tests are affected."""
    # Set up mocks.
    mock_get_reduced_test_configs.return_value = test_configs_pb2.TestConfigs()
    mock_sys_exit = self.enterContext(
        unittest.mock.patch.object(sys, 'exit', autospec=True)
    )

    # Function call.
    run_affected_triggers_mode.get_affected_test_details(
        acme_test_constants.SCHEDULING_PLAN.name
    )

    # Assertions.
    mock_sys_exit.assert_called_once_with(atest_enum.ExitCode.TEST_NOT_FOUND)
    mock_local_detect_event.assert_called_once_with(
        detect_type=atest_enum.DetectType.RUN_AFFECTED_TRIGGERS_MODE, result=1
    )

  @unittest.mock.patch.object(metrics, 'LocalDetectEvent', autospec=True)
  @unittest.mock.patch.object(
      acme_utils, 'get_reduced_test_configs', autospec=True
  )
  def test_get_affected_test_details_all_filtered_out(
      self, mock_get_reduced_test_configs, mock_local_detect_event
  ):
    """Test get_affected_test_details exits if all plans are filtered out."""
    # Set up mocks.
    mock_get_reduced_test_configs.return_value = (
        acme_test_constants.SAMPLE_TEST_CONFIG
    )
    mock_sys_exit = self.enterContext(
        unittest.mock.patch.object(sys, 'exit', autospec=True)
    )

    # Function call.
    run_affected_triggers_mode.get_affected_test_details(
        'some-other-scheduling-plan'
    )

    # Assertions.
    mock_sys_exit.assert_called_once_with(atest_enum.ExitCode.TEST_NOT_FOUND)
    mock_local_detect_event.assert_called_once_with(
        detect_type=atest_enum.DetectType.RUN_AFFECTED_TRIGGERS_MODE, result=1
    )

  @unittest.mock.patch.object(metrics, 'LocalDetectEvent', autospec=True)
  @unittest.mock.patch.object(
      acme_utils, 'get_reduced_test_configs', autospec=True
  )
  def test_get_affected_test_details(
      self, mock_get_reduced_test_configs, mock_local_detect_event
  ):
    """Tests that get_affected_test_details returns the correct TestDetails."""
    # Set up mocks.
    mock_get_reduced_test_configs.return_value = (
        acme_test_constants.SAMPLE_TEST_CONFIG
    )

    # Function call.
    tests, test_details = run_affected_triggers_mode.get_affected_test_details(
        acme_test_constants.SCHEDULING_PLAN.name
    )
    actual_return_val = zip(tests, test_details)
    expected_return_val = zip(
        [
            unittest_constants.MODULE_NAME,
            unittest_constants.MODULE2_NAME,
            unittest_constants.MODULE_NAME,
        ],
        [
            acme_test_constants.MODULE_PLAN_TEST_DETAILS,
            acme_test_constants.MODULE2_PLAN_TEST_DETAILS,
            acme_test_constants.MODULE_PLAN_SIMPLE_TEST_DETAILS,
        ],
    )

    self.assertCountEqual(expected_return_val, actual_return_val)
    mock_local_detect_event.assert_called_once_with(
        detect_type=atest_enum.DetectType.RUN_AFFECTED_TRIGGERS_MODE, result=1
    )


if __name__ == '__main__':
  unittest.main()
