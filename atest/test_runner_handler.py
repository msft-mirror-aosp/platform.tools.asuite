# Copyright 2017, The Android Open Source Project
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

"""
Aggregates test runners, groups tests by test runners and kicks off tests.
"""

# pylint: disable=line-too-long
# pylint: disable=import-outside-toplevel

from __future__ import annotations

import itertools
import time
import traceback

from typing import Any, Callable, Dict, List, Tuple

from atest import atest_error
from atest import atest_execution_info
from atest import bazel_mode
from atest import constants
from atest import module_info
from atest import result_reporter

from atest.atest_enum import ExitCode
from atest.metrics import metrics
from atest.metrics import metrics_utils
from atest.test_finders import test_info
from atest.test_runners import atest_tf_test_runner
from atest.test_runners import mobly_test_runner
from atest.test_runners import robolectric_test_runner
from atest.test_runners import suite_plan_test_runner
from atest.test_runners import test_runner_base
from atest.test_runners import vts_tf_test_runner

_TEST_RUNNERS = {
    atest_tf_test_runner.AtestTradefedTestRunner.NAME: atest_tf_test_runner.AtestTradefedTestRunner,
    mobly_test_runner.MoblyTestRunner.NAME: mobly_test_runner.MoblyTestRunner,
    robolectric_test_runner.RobolectricTestRunner.NAME: robolectric_test_runner.RobolectricTestRunner,
    suite_plan_test_runner.SuitePlanTestRunner.NAME: suite_plan_test_runner.SuitePlanTestRunner,
    vts_tf_test_runner.VtsTradefedTestRunner.NAME: vts_tf_test_runner.VtsTradefedTestRunner,
    bazel_mode.BazelTestRunner.NAME: bazel_mode.BazelTestRunner,
}


def _get_test_runners():
    """Returns the test runners.

    If external test runners are defined outside atest, they can be try-except
    imported into here.

    Returns:
        Dict of test runner name to test runner class.
    """
    test_runners_dict = _TEST_RUNNERS
    # Example import of example test runner:
    try:
        from test_runners import example_test_runner
        test_runners_dict[example_test_runner.ExampleTestRunner.NAME] = example_test_runner.ExampleTestRunner
    except ImportError:
        pass
    return test_runners_dict


def group_tests_by_test_runners(test_infos):
    """Group the test_infos by test runners

    Args:
        test_infos: List of TestInfo.

    Returns:
        List of tuples (test runner, tests).
    """
    tests_by_test_runner = []
    test_runner_dict = _get_test_runners()
    key = lambda x: x.test_runner
    sorted_test_infos = sorted(list(test_infos), key=key)
    for test_runner, tests in itertools.groupby(sorted_test_infos, key):
        # groupby returns a grouper object, we want to operate on a list.
        tests = list(tests)
        test_runner_class = test_runner_dict.get(test_runner)
        if test_runner_class is None:
            raise atest_error.UnknownTestRunnerError('Unknown Test Runner %s' %
                                                     test_runner)
        tests_by_test_runner.append((test_runner_class, tests))
    return tests_by_test_runner


def create_test_runner_invocations(
    *,
    test_infos: List[test_info.TestInfo],
    results_dir: str,
    mod_info: module_info.ModuleInfo,
    extra_args: Dict[str, Any],
) -> List[TestRunnerInvocation]:
    """Creates TestRunnerInvocation instances.

    Args:
        test_infos: A list of instances of TestInfo.
        results_dir: A directory which stores the ATest execution information.
        mod_info: An instance of ModuleInfo.
        extra_args: A dict of arguments for the test runner to utilize.

    Returns:
        A list of TestRunnerInvocation instances.
    """

    test_runner_invocations = []
    for test_runner_class, tests in group_tests_by_test_runners(test_infos):
        test_runner = test_runner_class(
            results_dir,
            mod_info=mod_info,
            extra_args=extra_args,
        )

        test_runner_invocations.append(TestRunnerInvocation(
            test_runner=test_runner,
            extra_args=extra_args,
            test_infos=tests))

    return test_runner_invocations


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

    def get_test_runner_reqs(self) -> Set[str]:
        """Returns the required build targets for this test runner invocation."""
        return self._test_runner.get_test_runner_build_reqs(self._test_infos)

    # pylint: disable=too-many-locals
    def run_all_tests(
        self, reporter: result_reporter.ResultReporter) -> ExitCode:
        """Runs all tests."""

        test_start = time.time()
        is_success = True
        try:
            tests_ret_code = self._test_runner.run_tests(
                self._test_infos, self._extra_args, reporter)
        # pylint: disable=broad-except
        except Exception:
            stacktrace = traceback.format_exc()
            reporter.runner_failure(self._test_runner.NAME, stacktrace)
            tests_ret_code = ExitCode.TEST_FAILURE
            is_success = False

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
            tests.append({'name':testcase_name,
                          'result':result,
                          'stacktrace':test.details})
        metrics.RunnerFinishEvent(
            duration=run_time,
            success=is_success,
            runner_name=self._test_runner.NAME,
            test=tests)

        return tests_ret_code
