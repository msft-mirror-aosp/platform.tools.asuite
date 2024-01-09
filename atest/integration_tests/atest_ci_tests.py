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

"""A collection of integration test cases for atest."""

import json
from pathlib import Path
import subprocess
from typing import Callable
from atest_integration_test import AtestIntegrationTest, TestCase, main


class CommandSuccessTests(TestCase):
    """Test whether the atest commands run with success exit codes."""

    def test_csuite_harness_tests(self):
        """Test if csuite-harness-tests command runs successfully."""
        atest = AtestIntegrationTest(self.id())
        if atest.in_build_env():
            subprocess.run(
                'atest-dev -b csuite-harness-tests'.split(),
                check=True,
                env=atest.get_env(),
                cwd=atest.get_repo_root(),
            )

        if atest.in_test_env():
            subprocess.run(
                (
                    'atest-dev -it csuite-harness-tests -s '
                    + atest.get_device_serial()
                ).split(),
                check=True,
                env=atest.get_env(),
                cwd=atest.get_repo_root(),
            )

    def test_csuite_cli_test(self):
        """Test if csuite_cli_test command runs successfully."""
        atest = AtestIntegrationTest(self.id())
        if atest.in_build_env():
            subprocess.run(
                'atest-dev -b csuite_cli_test'.split(),
                check=True,
                env=atest.get_env(),
                cwd=atest.get_repo_root(),
            )

        if atest.in_test_env():
            subprocess.run(
                (
                    'atest-dev -it csuite_cli_test -s '
                    + atest.get_device_serial()
                ).split(),
                check=True,
                env=atest.get_env(),
                cwd=atest.get_repo_root(),
            )


class CommandVerificationTests(TestCase):
    """Checks atest tradefed commands."""

    def test_animator_test(self):
        """Test if AnimatorTest command runs correctly."""
        cmd = 'AnimatorTest'
        self._verify_atest_internal_command(
            cmd,
            lambda atest_internal_command, atest: self.assertIn(
                cmd, atest_internal_command
            ),
        )

    def test_cts_animation_test_cases_animator_test(self):
        """Test if CtsAnimationTestCases:AnimatorTest command runs correctly."""
        cmd = 'CtsAnimationTestCases:AnimatorTest'
        self._verify_atest_internal_command(
            cmd,
            lambda atest_internal_command, atest: self.assertIn(
                'CtsAnimationTestCases:android.animation.cts.AnimatorTest',
                atest_internal_command,
            ),
        )

    def _verify_atest_internal_command(
        self,
        cmd: str,
        verify_func: Callable[[str, AtestIntegrationTest], None],
    ) -> None:
        """Verifies the command by executing it and checking its output.

        Args:
          cmd_list: The atest command to execute.
          verify_func: A function that takes the atest internal command string
            and checks it.
        """
        atest = AtestIntegrationTest(self.id())
        cmd_split = cmd.split()
        cmd_list = ['atest-dev', '-g']
        cmd_list.extend(cmd_split)
        runner_commands_key = cmd_split[0]
        runner_commands_json = (
            'tools/asuite/atest/test_data/runner_commands.json'
        )
        if atest.in_build_env():
            Path(atest.get_repo_root()).joinpath(runner_commands_json).unlink(
                missing_ok=True
            )
            subprocess.run(
                cmd_list,
                check=True,
                env=atest.get_env(),
                cwd=atest.get_repo_root(),
                encoding='utf-8',
            )
            atest.add_snapshot_paths(runner_commands_json)

        if atest.in_test_env():
            with open(
                Path(atest.get_repo_root()).joinpath(runner_commands_json),
                'r',
                encoding='utf-8',
            ) as f:
                dict_from_json = json.load(f)
            verify_func(dict_from_json[runner_commands_key], atest)


if __name__ == '__main__':
    main()
