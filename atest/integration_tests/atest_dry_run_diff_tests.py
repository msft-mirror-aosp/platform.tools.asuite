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

"""A collection of integration test cases for atest."""

import concurrent.futures
import csv
import dataclasses
import functools
import multiprocessing
import pathlib
from typing import Any, Optional
import atest_integration_test


@dataclasses.dataclass
class _AtestCommandUsage:
  """A class to hold the atest command and its usage frequency."""

  command: str
  usage_count: int
  user_count: int

  @staticmethod
  def to_json(usage: '_AtestCommandUsage') -> dict[str, Any]:
    """Converts an _AtestCommandUsage object to a JSON dictionary."""
    return {
        'command': usage.command,
        'usage_count': usage.usage_count,
        'user_count': usage.user_count,
    }

  @staticmethod
  def from_json(json_dict: dict[str, Any]) -> '_AtestCommandUsage':
    """Creates an _AtestCommandUsage object from a JSON dictionary."""
    return _AtestCommandUsage(
        json_dict['command'],
        json_dict['usage_count'],
        json_dict['user_count'],
    )


class AtestDryRunDiffTests(atest_integration_test.AtestTestCase):
  """Tests to compare the atest dry run output between atest prod binary and dev binary."""

  def setUp(self):
    super().setUp()
    self.maxDiff = None

  def test_dry_run_output_diff(self):
    """Tests to compare the atest dry run output between atest prod binary and dev binary."""
    script = self.create_atest_script()
    script.add_build_step(self._build_step)
    script.add_test_step(self._test_step)
    script.run()

  def _get_atest_command_usages(
      self, repo_root: str, dry_run_diff_test_cmd_input_file: Optional[str]
  ) -> list[_AtestCommandUsage]:
    """Returns the atest command usages for the dry run diff test.

    Returns:
      A list of _AtestCommandUsage objects.
    """
    if not dry_run_diff_test_cmd_input_file:
      return [
          _AtestCommandUsage(cmd, -1, -1) for cmd in _default_input_commands
      ]
    with (
        pathlib.Path(repo_root)
        .joinpath(dry_run_diff_test_cmd_input_file)
        .open()
    ) as input_file:
      reader = csv.reader(input_file)
      return [_AtestCommandUsage(*row) for row in reader if row and row[0]]

  def _build_step(
      self,
      step_in: atest_integration_test.StepInput,
  ) -> atest_integration_test.StepOutput:

    run_command = lambda use_prod, command_usage: self.run_atest_command(
        '--dry-run -it ' + command_usage.command,
        step_in,
        include_device_serial=False,
        use_prebuilt_atest_binary=use_prod,
    )
    get_prod_result = functools.partial(run_command, True)
    get_dev_result = functools.partial(run_command, False)

    command_usages = self._get_atest_command_usages(
        step_in.get_repo_root(),
        step_in.get_config().dry_run_diff_test_cmd_input_file,
    )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=multiprocessing.cpu_count()
    ) as executor:
      # Run the version command with -c to clear the cache by the prod binary.
      self.run_atest_command(
          '--version -c',
          step_in,
          include_device_serial=False,
          use_prebuilt_atest_binary=True,
      )
      cmd_results_prod = list(executor.map(get_prod_result, command_usages))
      # Run the version command with -c to clear the cache by the dev binary.
      self.run_atest_command(
          '--version -c',
          step_in,
          include_device_serial=False,
          use_prebuilt_atest_binary=False,
      )
      cmd_results_dev = list(executor.map(get_dev_result, command_usages))

    step_out = self.create_step_output()
    step_out.set_snapshot_include_paths([])
    step_out.add_snapshot_obj(
        'usages', list(map(_AtestCommandUsage.to_json, command_usages))
    )
    step_out.add_snapshot_obj(
        'returncode_prod',
        list(map(lambda result: result.get_returncode(), cmd_results_prod)),
    )
    step_out.add_snapshot_obj(
        'returncode_dev',
        list(map(lambda result: result.get_returncode(), cmd_results_dev)),
    )
    step_out.add_snapshot_obj(
        'elapsed_time_prod',
        list(map(lambda result: result.get_elapsed_time(), cmd_results_prod)),
    )
    step_out.add_snapshot_obj(
        'elapsed_time_dev',
        list(map(lambda result: result.get_elapsed_time(), cmd_results_dev)),
    )
    step_out.add_snapshot_obj(
        'runner_cmd_prod',
        list(
            map(
                lambda result: result.get_atest_log_values_from_prefix(
                    atest_integration_test.DRY_RUN_COMMAND_LOG_PREFIX
                )[0],
                cmd_results_prod,
            )
        ),
    )
    step_out.add_snapshot_obj(
        'runner_cmd_dev',
        list(
            map(
                lambda result: result.get_atest_log_values_from_prefix(
                    atest_integration_test.DRY_RUN_COMMAND_LOG_PREFIX
                )[0],
                cmd_results_dev,
            )
        ),
    )

    return step_out

  def _test_step(self, step_in: atest_integration_test.StepInput) -> None:
    usages = list(map(_AtestCommandUsage.from_json, step_in.get_obj('usages')))
    returncode_prod = step_in.get_obj('returncode_prod')
    returncode_dev = step_in.get_obj('returncode_dev')
    elapsed_time_prod = step_in.get_obj('elapsed_time_prod')
    elapsed_time_dev = step_in.get_obj('elapsed_time_dev')
    runner_cmd_prod = step_in.get_obj('runner_cmd_prod')
    runner_cmd_dev = step_in.get_obj('runner_cmd_dev')

    for idx in range(len(usages)):
      impact_str = (
          'Potential'
          f' impacted number of users: {usages[idx].user_count}, number of'
          f' invocations: {usages[idx].usage_count}.'
      )
      with self.subTest(name=f'{usages[idx].command}_returncode'):
        self.assertEqual(
            returncode_prod[idx],
            returncode_dev[idx],
            f'Return code mismatch for command: {usages[idx].command}. Prod:'
            f' {returncode_prod[idx]} Dev: {returncode_dev[idx]}. {impact_str}',
        )
      with self.subTest(name=f'{usages[idx].command}_elapsed_time'):
        self.assertAlmostEqual(
            elapsed_time_prod[idx],
            elapsed_time_dev[idx],
            delta=12,
            msg=(
                f'Elapsed time mismatch for command: {usages[idx].command}.'
                f' Prod: {elapsed_time_prod[idx]} Dev:'
                f' {elapsed_time_dev[idx]} {impact_str}'
            ),
        )
      with self.subTest(
          name=f'{usages[idx].command}_runner_cmd_has_same_elements'
      ):
        sanitized_runner_cmd_prod = (
            atest_integration_test.sanitize_runner_command(runner_cmd_prod[idx])
        )
        sanitized_runner_cmd_dev = (
            atest_integration_test.sanitize_runner_command(runner_cmd_dev[idx])
        )
        self.assertEqual(
            set(sanitized_runner_cmd_prod.split(' ')),
            set(sanitized_runner_cmd_dev.split(' ')),
            'Runner command mismatch for command:'
            f' {usages[idx].command}.\nProd:\n'
            f' {sanitized_runner_cmd_prod}\nDev:\n{sanitized_runner_cmd_dev}\n'
            f' {impact_str}',
        )


# A copy of the list of atest commands tested in the command verification tests.
_default_input_commands = [
    'AnimatorTest',
    'CtsAnimationTestCases:AnimatorTest',
    'CtsSampleDeviceTestCases:android.sample.cts',
    'CtsAnimationTestCases CtsSampleDeviceTestCases',
    'HelloWorldTests',
    'android.animation.cts',
    'android.sample.cts.SampleDeviceReportLogTest',
    'android.sample.cts.SampleDeviceTest#testSharedPreferences',
    'hello_world_test',
    'native-benchmark',
    'platform_testing/tests/example/native',
    'platform_testing/tests/example/native/Android.bp',
    'tools/tradefederation/core/res/config/native-benchmark.xml',
    'QuickAccessWalletRoboTests',
    'QuickAccessWalletRoboTests --host',
    'CtsWifiAwareTestCases',
    'pts-bot:PAN/GN/MISC/UUID/BV-01-C',
    'TeeUIUtilsTest',
    'android.security.cts.PermissionMemoryFootprintTest',
    'CtsSampleDeviceTestCases:SampleDeviceTest#testSharedPreferences',
    'CtsSampleDeviceTestCases:android.sample.cts.SampleDeviceReportLogTest',
    (
        'PerInstance/CameraHidlTest#'
        'configureInjectionStreamsAvailableOutputs/0_internal_0'
    ),
    (
        'VtsHalCameraProviderV2_4TargetTest:PerInstance/'
        'CameraHidlTest#configureInjectionStreamsAvailableOutputs/'
        '0_internal_0'
    ),
    (
        'TeeUIUtilsTest#intersectTest,ConvexObjectConstruction,'
        'ConvexObjectLineIntersection'
    ),
    (
        'CtsSecurityTestCases:android.security.cts.'
        'ActivityManagerTest#testActivityManager_'
        'registerUidChangeObserver_allPermission'
    ),
    (
        'cts/tests/tests/security/src/android/security/cts/'
        'ActivityManagerTest.java#testActivityManager_'
        'registerUidChangeObserver_allPermission'
    ),
    (
        'cts/tests/tests/security/src/android/security/cts/'
        'PermissionMemoryFootprintTest.kt#'
        'checkAppsCantIncreasePermissionSizeAfterCreating'
    ),
    (
        'android.security.cts.PermissionMemoryFootprintTest#'
        'checkAppsCantIncreasePermissionSizeAfterCreating'
    ),
]

if __name__ == '__main__':
  atest_integration_test.main()
