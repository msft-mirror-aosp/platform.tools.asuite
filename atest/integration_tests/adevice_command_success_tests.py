#!/usr/bin/env python3
#
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

"""Tests to check if adevice commands were executed with success exit codes."""

import atest_integration_test


class AdeviceCommandSuccessTests(atest_integration_test.AtestTestCase):
  """Test whether the adevice commands run with success exit codes."""

  def setUp(self):
    super().setUp()
    self._default_snapshot_include_paths += [
        '$OUT_DIR/combined-*.ninja',
        '$OUT_DIR/build-*.ninja',
        '$OUT_DIR/soong/*.ninja',
        '$OUT_DIR/target/',
    ]

    self._default_snapshot_env_keys += ['TARGET_PRODUCT', 'ANDROID_BUILD_TOP']
    self._default_snapshot_exclude_paths = []

  def test_status(self):
    """Test if status command runs successfully across periodic repo syncs."""
    self._verify_adevice_command_success('adevice status')

  def test_update(self):
    """Test if update command runs successfully across periodic repo syncs."""
    self._verify_adevice_command_success(
        'adevice update --max-allowed-changes=6000'
    )

  def _verify_adevice_command_success(self, test_cmd: str):
    """Verifies whether an adevice command run completed with exit code 0."""
    script = self.create_atest_script()

    def build_step(
        step_in: atest_integration_test.StepInput,
    ) -> atest_integration_test.StepOutput:
      self._run_shell_command(
          'build/soong/soong_ui.bash --make-mode'.split(),
          env=step_in.get_env(),
          cwd=step_in.get_repo_root(),
          print_output=True,
      ).check_returncode()
      return self.create_step_output()

    def test_step(step_in: atest_integration_test.StepInput) -> None:
      self._run_shell_command(
          test_cmd.split(),
          env=step_in.get_env(),
          cwd=step_in.get_repo_root(),
          print_output=True,
      ).check_returncode()
      print(step_in.get_env())

    script.add_build_step(build_step)
    script.add_test_step(test_step)
    script.run()


if __name__ == '__main__':
  atest_integration_test.main()
