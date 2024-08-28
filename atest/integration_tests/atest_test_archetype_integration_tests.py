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

"""Integration tests to make sure selected test archetypes works in atest."""

from typing import Callable

import atest_integration_test


class DevicelessJavaTestHostTest(atest_integration_test.AtestTestCase):
  _TARGET_NAME = 'deviceless_java_test_host'

  def test_passed_failed_counts(self):
    _verify_test_passed_failed_ignored_counts(
        self,
        atest_command=self._TARGET_NAME + ' --no-bazel-mode --host',
        is_device_required=False,
        expected_passed_count=2,
        expected_failed_count=1,
        expected_ignored_count=0,
    )


class DevicelessPythonTestHostTest(atest_integration_test.AtestTestCase):
  _TARGET_NAME = 'deviceless_python_test_host'

  def test_passed_failed_counts(self):
    _verify_test_passed_failed_ignored_counts(
        self,
        atest_command=self._TARGET_NAME + ' --no-bazel-mode --host',
        is_device_required=False,
        expected_passed_count=2,
        expected_failed_count=1,
        expected_ignored_count=0,
    )


class DeviceAndroidTestTest(atest_integration_test.AtestTestCase):

  def test_passed_failed_counts(self):
    _verify_test_passed_failed_ignored_counts(
        self,
        atest_command='device_android_test',
        is_device_required=True,
        expected_passed_count=2,
        expected_failed_count=1,
        expected_ignored_count=0,
    )

  def test_early_tradefed_exit_shows_useful_output(self):
    _run_and_verify(
        self,
        atest_command='device_android_test_non_starting',
        is_device_required=True,
        verifier=self._verify_stdout_on_early_termination,
    )

  def _verify_stdout_on_early_termination(
      self,
      test_case: atest_integration_test.AtestTestCase,
      result: atest_integration_test.AtestRunResult,
  ):
    """Assert we see the message we expect and that we do not see a stacktrace."""
    test_case.assertIn(
        'Test failed because instrumentation process died.', result.get_stdout()
    )
    test_case.assertNotIn(
        'Traceback (most recent call last)', result.get_stdout()
    )


class DeviceCcTestTest(atest_integration_test.AtestTestCase):
  _TARGET_NAME = 'device_cc_test'

  def test_passed_failed_counts(self):
    _verify_test_passed_failed_ignored_counts(
        self,
        atest_command=self._TARGET_NAME,
        is_device_required=True,
        expected_passed_count=2,
        expected_failed_count=1,
        expected_ignored_count=0,
    )


def _verify_test_passed_failed_ignored_counts(
    test_case: atest_integration_test.AtestTestCase,
    atest_command: str,
    is_device_required: bool,
    expected_passed_count: int,
    expected_failed_count: int,
    expected_ignored_count: int,
):
  """Verify an atest command finished with expected result counts.

  Args:
      test_case: The reference to the calling test case.
      atest_command: The atest command to execute. Note: exclude 'atest',
        'atest-dev', '-b', '-i', and '-t' from it.
      is_device_required: Whether the test requires a device.
      expected_passed_count: Number of expected passed count.
      expected_failed_count: Number of expected failed count.
      expected_ignored_count: Number of expected ignored count.
  """

  script = test_case.create_atest_script()

  def build_step(
      step_in: atest_integration_test.StepInput,
  ) -> atest_integration_test.StepOutput:

    test_case.run_atest_command(
        atest_command + ' -cb', step_in, include_device_serial=False
    ).check_returncode()

    return test_case.create_step_output()

  def test_step(step_in: atest_integration_test.StepInput) -> None:
    result = test_case.run_atest_command(
        atest_command + ' -it',
        step_in,
        include_device_serial=is_device_required,
        print_output=False,
    )

    test_case.assertEqual(result.get_passed_count(), expected_passed_count)
    test_case.assertEqual(result.get_failed_count(), expected_failed_count)
    test_case.assertEqual(result.get_ignored_count(), expected_ignored_count)

  script.add_build_step(build_step)
  script.add_test_step(test_step)
  script.run()


def _run_and_verify(
    test_case: atest_integration_test.AtestTestCase,
    atest_command: str,
    is_device_required: bool,
    verifier: Callable[
        atest_integration_test.AtestTestCase,
        atest_integration_test.AtestRunResult,
    ],
):
  """Verify an atest command finished with expected result counts.

  Args:
      test_case: The reference to the calling test case.
      atest_command: The atest command to execute. Note: exclude 'atest',
        'atest-dev', '-b', '-i', and '-t' from it.
      is_device_required: Whether the test requires a device.
      verifier: function to call to verify the result.
  """

  script = test_case.create_atest_script()

  def build_step(
      step_in: atest_integration_test.StepInput,
  ) -> atest_integration_test.StepOutput:

    test_case.run_atest_command(
        atest_command + ' -cb', step_in, include_device_serial=False
    ).check_returncode()

    return test_case.create_step_output()

  def test_step(step_in: atest_integration_test.StepInput) -> None:
    result = test_case.run_atest_command(
        atest_command + ' -it',
        step_in,
        include_device_serial=is_device_required,
        print_output=False,
    )

    verifier(test_case, result)

  script.add_build_step(build_step)
  script.add_test_step(test_step)
  script.run()


if __name__ == '__main__':
  atest_integration_test.main()
