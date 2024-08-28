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

from dataclasses import dataclass
from typing import Callable

import atest_integration_test


class DevicelessJavaTestHostTest(atest_integration_test.AtestTestCase):
  _TARGET_NAME = 'deviceless_java_test_host'

  def test_passed_failed_counts(self):
    _run_and_verify(
        self,
        atest_command=self._TARGET_NAME + ' --no-bazel-mode --host',
        is_device_required=False,
        verifiers=_create_pass_fail_ignore_verifiers(
            expected_passed_count=2,
            expected_failed_count=1,
            expected_ignored_count=0,
        )
        + _create_elapsed_time_verifiers(max_sec=10),
    )


class DevicelessPythonTestHostTest(atest_integration_test.AtestTestCase):
  _TARGET_NAME = 'deviceless_python_test_host'

  def test_passed_failed_counts(self):
    _run_and_verify(
        self,
        atest_command=self._TARGET_NAME + ' --no-bazel-mode --host',
        is_device_required=False,
        verifiers=_create_pass_fail_ignore_verifiers(
            expected_passed_count=2,
            expected_failed_count=1,
            expected_ignored_count=0,
        )
        + _create_elapsed_time_verifiers(max_sec=10),
    )


class DeviceAndroidTestTest(atest_integration_test.AtestTestCase):

  def test_passed_failed_counts(self):
    _run_and_verify(
        self,
        atest_command='device_android_test',
        is_device_required=True,
        verifiers=_create_pass_fail_ignore_verifiers(
            expected_passed_count=2,
            expected_failed_count=1,
            expected_ignored_count=0,
        )
        + _create_elapsed_time_verifiers(max_sec=20),
    )

  def test_early_tradefed_exit_shows_useful_output(self):
    verifiers = [
        _Verifier(
            lambda test_case, result: test_case.assertIn(
                'Test failed because instrumentation process died.',
                result.get_stdout(),
            ),
            'process_died',
        ),
        _Verifier(
            lambda test_case, result: test_case.assertNotIn(
                'Traceback (most recent call last)', result.get_stdout()
            ),
            'no_traceback',
        ),
    ]
    _run_and_verify(
        self,
        atest_command='device_android_test_non_starting',
        is_device_required=True,
        verifiers=verifiers,
    )


class DeviceCcTestTest(atest_integration_test.AtestTestCase):
  _TARGET_NAME = 'device_cc_test'

  def test_passed_failed_counts(self):
    _run_and_verify(
        self,
        atest_command=self._TARGET_NAME,
        is_device_required=True,
        verifiers=_create_pass_fail_ignore_verifiers(
            expected_passed_count=2,
            expected_failed_count=1,
            expected_ignored_count=0,
        )
        + _create_elapsed_time_verifiers(max_sec=20),
    )


@dataclass
class _Verifier:
  """Wrapper class to store a verifier function with a subtest name."""

  do_verify: Callable[
      atest_integration_test.AtestTestCase,
      atest_integration_test.AtestRunResult,
  ]
  name: str


def _create_elapsed_time_verifiers(max_sec: float) -> list[_Verifier]:
  return [
      _Verifier(
          lambda test_case, result: test_case.assertLessEqual(
              result.get_elapsed_time(), max_sec
          ),
          'elapsed_time',
      )
  ]


def _create_pass_fail_ignore_verifiers(
    expected_passed_count: int,
    expected_failed_count: int,
    expected_ignored_count: int,
) -> list[_Verifier]:
  """Create a list of verifiers that verify an atest command finished with expected result counts.

  Args:
      expected_passed_count: Number of expected passed count.
      expected_failed_count: Number of expected failed count.
      expected_ignored_count: Number of expected ignored count.
  """
  return [
      _Verifier(
          lambda test_case, result: test_case.assertEqual(
              result.get_passed_count(), expected_passed_count
          ),
          'pass_count',
      ),
      _Verifier(
          lambda test_case, result: test_case.assertEqual(
              result.get_failed_count(), expected_failed_count
          ),
          'fail_count',
      ),
      _Verifier(
          lambda test_case, result: test_case.assertEqual(
              result.get_ignored_count(), expected_ignored_count
          ),
          'ignore_count',
      ),
  ]


def _run_and_verify(
    test_case: atest_integration_test.AtestTestCase,
    atest_command: str,
    is_device_required: bool,
    verifiers: list[_Verifier],
):
  """Verify an atest command finished with expected result counts.

  Args:
      test_case: The reference to the calling test case.
      atest_command: The atest command to execute. Note: exclude 'atest',
        'atest-dev', '-b', '-i', and '-t' from it.
      is_device_required: Whether the test requires a device.
      verifiers: A list of verifiers to call to verify the result.
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

    for verifier in verifiers:
      with test_case.subTest(verifier.name):
        verifier.do_verify(test_case, result)

  script.add_build_step(build_step)
  script.add_test_step(test_step)
  script.run()


if __name__ == '__main__':
  atest_integration_test.main()
