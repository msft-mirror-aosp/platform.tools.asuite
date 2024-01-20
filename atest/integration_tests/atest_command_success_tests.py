#!/usr/bin/env python3
#
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

"""Tests to check if atest commands were executed with success exit codes."""

from atest_integration_test import AtestTestCase, StepInput, StepOutput, main


class CommandSuccessTests(AtestTestCase):
    """Test whether the atest commands run with success exit codes."""

    def test_csuite_crash_detection_tests(self):
        """Test if csuite-harness-tests command runs successfully."""
        self._verify_atest_command_success('csuite_crash_detection_test')

    def test_csuite_harness_tests(self):
        """Test if csuite-harness-tests command runs successfully."""
        self._verify_atest_command_success('csuite-harness-tests')

    def test_csuite_cli_test(self):
        """Test if csuite_cli_test command runs successfully."""
        self._verify_atest_command_success('csuite_cli_test')

    def _verify_atest_command_success(self, cmd: str):
        """Verifies whether an Atest command run completed with exit code 0."""
        script = self.create_atest_script()

        def build_step(step_in: StepInput) -> StepOutput:
            self.run_atest_dev(cmd + ' -b', step_in).check_returncode()
            return self.create_step_output()

        def test_step(step_in: StepInput) -> None:
            self.run_atest_dev(cmd + ' -it', step_in).check_returncode()

        script.add_build_step(build_step)
        script.add_test_step(test_step)
        script.run()


if __name__ == '__main__':
    main()
