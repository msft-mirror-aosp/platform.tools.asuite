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

from atest_integration_test import AtestTestCase, main


class CommandSuccessTests(AtestTestCase):
    """Test whether the atest commands run with success exit codes."""

    def test_csuite_harness_tests(self):
        """Test if csuite-harness-tests command runs successfully."""
        atest = self.create_atest_script()
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
                    'atest-dev -it csuite-harness-tests'
                    + atest.get_device_serial_args_or_empty()
                ).split(),
                check=True,
                env=atest.get_env(),
                cwd=atest.get_repo_root(),
            )

    def test_csuite_cli_test(self):
        """Test if csuite_cli_test command runs successfully."""
        atest = self.create_atest_script()
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
                    'atest-dev -it csuite_cli_test'
                    + atest.get_device_serial_args_or_empty()
                ).split(),
                check=True,
                env=atest.get_env(),
                cwd=atest.get_repo_root(),
            )


if __name__ == '__main__':
    main()
