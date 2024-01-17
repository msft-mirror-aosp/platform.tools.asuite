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

import subprocess

from atest_integration_test import AtestTestCase, StepInput, StepOutput, main


class CommandSuccessTests(AtestTestCase):
    """Test whether the atest commands run with success exit codes."""

    def test_csuite_harness_tests(self):
        """Test if csuite-harness-tests command runs successfully."""
        script = self.create_atest_script()

        def build_step(step_in: StepInput) -> StepOutput:
            subprocess.run(
                'atest-dev -b csuite-harness-tests'.split(),
                check=True,
                env=step_in.get_env(),
                cwd=step_in.get_repo_root(),
            )
            return self.create_step_output()

        def test_step(step_in: StepInput) -> None:
            subprocess.run(
                (
                    'atest-dev -it csuite-harness-tests'
                    + step_in.get_device_serial_args_or_empty()
                ).split(),
                check=True,
                env=step_in.get_env(),
                cwd=step_in.get_repo_root(),
            )

        script.add_build_step(build_step)
        script.add_test_step(test_step)
        script.run()

    def test_csuite_cli_test(self):
        """Test if csuite_cli_test command runs successfully."""
        script = self.create_atest_script()

        def build_step(step_in: StepInput) -> StepOutput:
            subprocess.run(
                'atest-dev -b csuite_cli_test'.split(),
                check=True,
                env=step_in.get_env(),
                cwd=step_in.get_repo_root(),
            )
            return self.create_step_output()

        def test_step(step_in: StepInput) -> None:
            subprocess.run(
                (
                    'atest-dev -it csuite_cli_test'
                    + step_in.get_device_serial_args_or_empty()
                ).split(),
                check=True,
                env=step_in.get_env(),
                cwd=step_in.get_repo_root(),
            )

        script.add_build_step(build_step)
        script.add_test_step(test_step)
        script.run()


if __name__ == '__main__':
    main()
