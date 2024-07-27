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


import subprocess
import atest_integration_test


class AdeviceCommandSuccessTests(atest_integration_test.AtestTestCase):
  """Test whether the adevice commands run with success exit codes."""

  def setUp(self):
    super().setUp()
    self._default_snapshot_include_paths += [
        '$OUT_DIR/combined-*.ninja*',
        '$OUT_DIR/*.ninja*',
        '$OUT_DIR/soong/*.ninja*',
        '$OUT_DIR/target/product/',
    ]

    self._default_snapshot_env_keys += ['TARGET_PRODUCT', 'ANDROID_BUILD_TOP']
    self._default_snapshot_exclude_paths += [
        '$OUT_DIR/**/*.img',
        '$OUT_DIR/**/symbols',
        '$OUT_DIR/target/product/**/obj',
        '$OUT_DIR/target/product/**/tmpfvcx759x',
        '$OUT_DIR/host/linux-x86/bin/go',
        '$OUT_DIR/host/linux-x86/bin/soong_build',
        '$OUT_DIR/host/linux-x86/obj',
        '$OUT_DIR/host/linux-x86/cvd-host_package',
        '$OUT_DIR/host/linux-x86/testcases',
    ]

  def test_1_status(self):
    """Test if status command runs successfully on latest repo sync."""
    self._verify_adevice_command(
        build_cmd='build/soong/soong_ui.bash --make-mode droid adevice'.split(),
        build_clean_up_cmd=[],
        test_cmd='adevice status'.split(),
        expected_in_log=[],
        expected_not_in_log=[],
    )

  def test_2_update(self):
    """Test if update command runs successfully on latest repo sync."""
    self._verify_adevice_command_success(
        'adevice update --max-allowed-changes=6000'.split()
    )

  def test_3_status_no_changes(self):
    """Test if status command doesn't perform any updates after adevice update."""
    self._verify_adevice_command(
        build_cmd=[],
        build_clean_up_cmd=[],
        test_cmd='adevice status'.split(),
        expected_in_log=['Adb Cmds - 0'],
        expected_not_in_log=['push'],
    )

  def test_4_update_no_changes(self):
    """Test if status command doesn't perform any updates after adevice update."""
    self._verify_adevice_command(
        build_cmd=[],
        build_clean_up_cmd=[],
        test_cmd='adevice update'.split(),
        expected_in_log=['Adb Cmds - 0'],
        expected_not_in_log=['push'],
    )

  #   Skipping test that has additional build_pre_cmd until rest are working.
  #   def test_5_system_server_change_expect_soft_restart(self):
  #     """Test if adevice update on system server update results in a soft
  #     restart."""
  #     log_string_to_find = 'Entered the Android system server'
  #     filename = (
  #         'frameworks/base/services/java/com/android/server/SystemServer.java'
  #     )
  #     build_pre_cmd = [
  #         'sed',
  #         '-i',
  #         f's#{log_string_to_find}#{log_string_to_find}ADEVICE_TEST#g',
  #         filename,
  #     ]
  #     build_clean_up_cmd = f'sed -i s#ADEVICE_TEST##g {filename}'.split()

  #     self._verify_adevice_command(
  #         build_pre_cmd=build_pre_cmd,
  #         build_clean_up_cmd=build_clean_up_cmd,
  #         test_cmd='adevice update'.split(),
  #         expected_in_log=['push', 'services.jar', 'SoftRestart'],
  #         expected_not_in_log=['reboot'],
  #     )

  def _verify_adevice_command_success(self, test_cmd: list[str]):
    """Verifies whether an adevice command run completed with exit code 0."""
    self._verify_adevice_command(
        build_cmd=[],
        build_clean_up_cmd=[],
        test_cmd=test_cmd,
        expected_in_log=[],
        expected_not_in_log=[],
    )

  def _verify_adevice_command(
      self,
      build_cmd: list[str],
      build_clean_up_cmd: list[str],
      test_cmd: list[str],
      expected_in_log: list[str],
      expected_not_in_log: list[str],
  ):
    """Verifies whether an adevice command run completed with exit code 0."""
    script = self.create_atest_script()

    def build_step(
        step_in: atest_integration_test.StepInput,
    ) -> atest_integration_test.StepOutput:

      try:
        if build_cmd:
          self._run_shell_command(
              build_cmd,
              env=step_in.get_env(),
              cwd=step_in.get_repo_root(),
              print_output=True,
          ).check_returncode()
        return self.create_step_output()
      except subprocess.CalledProcessError as e:
        self.fail(e)
      finally:
        # Always attempt to clean up
        if build_clean_up_cmd:
          self._run_shell_command(
              build_clean_up_cmd,
              env=step_in.get_env(),
              cwd=step_in.get_repo_root(),
              print_output=False,
          )

    def test_step(step_in: atest_integration_test.StepInput) -> None:
      result = self._run_shell_command(
          test_cmd,
          env=step_in.get_env(),
          cwd=step_in.get_repo_root(),
          print_output=False,
      )
      check_log_process = self._run_shell_command(
          f'cat {step_in.get_env()["ANDROID_BUILD_TOP"]}/out/adevice.log'.split(),
          env=step_in.get_env(),
          cwd=step_in.get_repo_root(),
      )

      # Check for error exit
      result.check_returncode()
      for s in expected_in_log:
        self.assertIn(s, check_log_process.stdout, f'{s} was not found in log')
      for s in expected_not_in_log:
        self.assertNotIn(s, check_log_process.stdout, f'{s} was found in log')

    script.add_build_step(build_step)
    script.add_test_step(test_step)
    script.run()


if __name__ == '__main__':
  atest_integration_test.main()
