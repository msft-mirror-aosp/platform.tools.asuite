# Copyright 2024, The Android Open Source Project
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

"""Test runner invocation class."""

from __future__ import annotations

import os
import time
import traceback
from typing import Any, Dict, List, Set

from atest import result_reporter
from atest.atest_enum import ExitCode
from atest.metrics import metrics
from atest.metrics import metrics_utils
from atest.test_finders import test_info
from atest.test_runners import test_runner_base
from atest.test_runners.event_handler import EventHandleError

# Look for this in tradefed log messages.
TRADEFED_EARLY_EXIT_LOG_SIGNAL = (
    'INSTRUMENTATION_RESULT: shortMsg=Process crashed'
)

# Print this to user.
TRADEFED_EARLY_EXIT_ATEST_MSG = (
    'Test failed because instrumentation process died.'
    ' Please check your device logs.'
)


class TestRunnerInvocation:
  """An invocation executing tests based on given arguments."""

  def __init__(
      self,
      *,
      test_runner: test_runner_base.TestRunnerBase,
      extra_args: Dict[str, Any],
      test_infos: List[test_info.TestInfo],
  ):
    self._extra_args = extra_args
    self._test_infos = test_infos
    self._test_runner = test_runner

  @property
  def test_infos(self):
    return self._test_infos

  def __eq__(self, other):
    return self.__dict__ == other.__dict__

  def requires_device_update(self):
    """Checks whether this invocation requires device update."""
    return self._test_runner.requires_device_update(self._test_infos)

  def get_test_runner_reqs(self) -> Set[str]:
    """Returns the required build targets for this test runner invocation."""
    return self._test_runner.get_test_runner_build_reqs(self._test_infos)

  # pylint: disable=too-many-locals
  def run_all_tests(self, reporter: result_reporter.ResultReporter) -> ExitCode:
    """Runs all tests."""

    test_start = time.time()
    is_success = True
    err_msg = None
    try:
      tests_ret_code = self._test_runner.run_tests(
          self._test_infos, self._extra_args, reporter
      )
    except EventHandleError:
      is_success = False
      if self.log_shows_early_exit():
        err_msg = TRADEFED_EARLY_EXIT_ATEST_MSG
      else:
        err_msg = traceback.format_exc()

    except Exception:  # pylint: disable=broad-except
      is_success = False
      err_msg = traceback.format_exc()

    if not is_success:
      reporter.runner_failure(self._test_runner.NAME, err_msg)
      tests_ret_code = ExitCode.TEST_FAILURE

    run_time = metrics_utils.convert_duration(time.time() - test_start)
    tests = []
    for test in reporter.get_test_results_by_runner(self._test_runner.NAME):
      # group_name is module name with abi(for example,
      # 'x86_64 CtsSampleDeviceTestCases').
      # Filtering abi in group_name.
      test_group = test.group_name
      # Withdraw module name only when the test result has reported.
      module_name = test_group
      if test_group and ' ' in test_group:
        _, module_name = test_group.split()
      testcase_name = '%s:%s' % (module_name, test.test_name)
      result = test_runner_base.RESULT_CODE[test.status]
      tests.append(
          {'name': testcase_name, 'result': result, 'stacktrace': test.details}
      )
    metrics.RunnerFinishEvent(
        duration=run_time,
        success=is_success,
        runner_name=self._test_runner.NAME,
        test=tests,
    )

    return tests_ret_code

  def log_shows_early_exit(self) -> bool:
    """Grep the log file for TF process crashed message."""
    # Ensure file exists and is readable.
    if not os.access(self._test_runner.test_log_file.name, os.R_OK):
      return False

    with open(self._test_runner.test_log_file.name, 'r') as log_file:
      for line in log_file:
        if TRADEFED_EARLY_EXIT_LOG_SIGNAL in line:
          return True

    return False
