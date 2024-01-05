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

import json
from pathlib import Path
import subprocess
from typing import Callable, Dict, List
import atest_integration_test


class CommandSuccessTests(atest_integration_test.TestCase):
  """Test whether the atest commands run with success exit codes."""

  def test_csuite_harness_tests(self):
    atest = atest_integration_test.AtestIntegrationTest(self.id())
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
    atest = atest_integration_test.AtestIntegrationTest(self.id())
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
              'atest-dev -it csuite_cli_test -s ' + atest.get_device_serial()
          ).split(),
          check=True,
          env=atest.get_env(),
          cwd=atest.get_repo_root(),
      )


class CommandVerificationTests(atest_integration_test.TestCase):
  """Checks atest tradefed commands."""

  def test_AnimatorTest(self):
    self.verify_command(
        'atest-dev -g AnimatorTest'.split(),
        lambda data: self.assertIn('AnimatorTest', data['AnimatorTest']),
    )

  def test_CtsAnimationTestCases_AnimatorTest(self):
    self.verify_command(
        'atest-dev -g CtsAnimationTestCases:AnimatorTest'.split(),
        lambda data: self.assertIn(
            'CtsAnimationTestCases:android.animation.cts.AnimatorTest',
            data['CtsAnimationTestCases:AnimatorTest'],
        ),
    )

  def verify_command(
      self,
      cmd_list: List[str],
      verify_func: Callable[[Dict[str, List[str]]], None],
  ) -> None:
    """Verifies the command by executing it and checking its output.

    Args:
      cmd_list: The command to execute.
      verify_func: A function that takes the output of the command and checks
        it.
    """
    atest = atest_integration_test.AtestIntegrationTest(self.id())
    runner_commands_json = 'tools/asuite/atest/test_data/runner_commands.json'
    if atest.in_build_env():
      Path(atest.get_repo_root()).joinpath(runner_commands_json).unlink(
          missing_ok=True
      )
      subprocess.run(
          cmd_list,
          check=True,
          env=atest.get_env(),
          cwd=atest.get_repo_root(),
      )
      atest.add_snapshot_paths(runner_commands_json)

    if atest.in_test_env():
      with open(
          Path(atest.get_repo_root()).joinpath(runner_commands_json), 'r'
      ) as f:
        dict_from_json = json.load(f)
      verify_func(dict_from_json)


if __name__ == '__main__':
  atest_integration_test.main()
