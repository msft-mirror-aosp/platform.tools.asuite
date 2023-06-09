# Copyright 2023, The Android Open Source Project
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

"""Mobly test runner."""

from typing import Any, Dict, List, Set

from atest import result_reporter
from atest.test_finders import test_info
from atest.test_runners import test_runner_base


class MoblyTestRunner(test_runner_base.TestRunnerBase):
    """Mobly test runner class."""
    NAME = 'MoblyTestRunner'
    # Unused placeholder value. Mobly tests will be run from Python virtualenv
    EXECUTABLE = '.'

    # pylint: disable=unused-argument
    def run_tests(
            self, test_infos: List[test_info.TestInfo],
            extra_args: Dict[str, Any],
            reporter: result_reporter.ResultReporter) -> int:
        """Run the list of test_infos.

        Should contain code for kicking off the test runs using
        test_runner_base.run(). Results should be processed and printed
        via the reporter passed in.

        Args:
            test_infos: List of TestInfo.
            extra_args: Dict of extra args to add to test run.
            reporter: An instance of result_report.ResultReporter.

        Returns:
            0 if tests succeed, non-zero otherwise.
        """
        # TODO: to be implemented
        return 0

    def host_env_check(self) -> None:
        """Checks that host env has met requirements."""

    def get_test_runner_build_reqs(
            self, test_infos: List[test_info.TestInfo]) -> Set[str]:
        """Returns a set of build targets required by the test runner."""
        build_targets = set()
        build_targets.update(test_runner_base.gather_build_targets(test_infos))
        return build_targets

    # pylint: disable=unused-argument
    def generate_run_commands(
            self, test_infos: List[test_info.TestInfo],
            extra_args: Dict[str, Any], _port: int | None = None) -> List[str]:
        """Generate a list of run commands from TestInfos.

        Args:
            test_infos: A set of TestInfo instances.
            extra_args: A Dict of extra args to append.
            _port: Unused.

        Returns:
            A list of run commands to run the tests.
        """
        # TODO: to be implemented
        return []
