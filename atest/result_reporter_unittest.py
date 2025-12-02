#!/usr/bin/env python3
#
# Copyright 2018, The Android Open Source Project
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

"""Unittests for result_reporter."""


from io import StringIO
import unittest
from unittest import mock

from atest import arg_parser
from atest import atest_configs
from atest import atest_enum
from atest import result_reporter
from atest.test_runners import test_runner_base


DEFAULT_ARGS = arg_parser.create_atest_arg_parser().parse_args([])


RESULT_PASSED_TEST = test_runner_base.TestResult(
    runner_name='someTestRunner',
    group_name='someTestModule',
    test_name='someClassName#sostName',
    status=test_runner_base.PASSED_STATUS,
    details=None,
    test_count=1,
    test_time='(10ms)',
    runner_total=None,
    group_total=2,
    additional_info={},
    test_run_name='com.android.UnitTests',
)

RESULT_PASSED_TEST_MODULE_2 = test_runner_base.TestResult(
    runner_name='someTestRunner',
    group_name='someTestModule2',
    test_name='someClassName#sostName',
    status=test_runner_base.PASSED_STATUS,
    details=None,
    test_count=1,
    test_time='(10ms)',
    runner_total=None,
    group_total=2,
    additional_info={},
    test_run_name='com.android.UnitTests',
)

RESULT_PASSED_TEST_RUNNER_2_NO_MODULE = test_runner_base.TestResult(
    runner_name='someTestRunner2',
    group_name=None,
    test_name='someClassName#sostName',
    status=test_runner_base.PASSED_STATUS,
    details=None,
    test_count=1,
    test_time='(10ms)',
    runner_total=None,
    group_total=2,
    additional_info={},
    test_run_name='com.android.UnitTests',
)

RESULT_FAILED_TEST = test_runner_base.TestResult(
    runner_name='someTestRunner',
    group_name='someTestModule',
    test_name='someClassName2#sestName2',
    status=test_runner_base.FAILED_STATUS,
    details='someTrace',
    test_count=1,
    test_time='',
    runner_total=None,
    group_total=2,
    additional_info={},
    test_run_name='com.android.UnitTests',
)

RESULT_RUN_FAILURE = test_runner_base.TestResult(
    runner_name='someTestRunner',
    group_name='someTestModule',
    test_name='someClassName#sostName',
    status=test_runner_base.ERROR_STATUS,
    details='someRunFailureReason',
    test_count=1,
    test_time='',
    runner_total=None,
    group_total=2,
    additional_info={},
    test_run_name='com.android.UnitTests',
)

RESULT_RUN_FAILURE_2 = test_runner_base.TestResult(
    runner_name='someTestRunner',
    group_name='someTestModule2',
    test_name='someClassName2#sostName2',
    status=test_runner_base.ERROR_STATUS,
    details='someRunFailureReason',
    test_count=1,
    test_time='',
    runner_total=None,
    group_total=2,
    additional_info={},
    test_run_name='com.android.UnitTests',
)

RESULT_INVOCATION_FAILURE = test_runner_base.TestResult(
    runner_name='someTestRunner',
    group_name=None,
    test_name=None,
    status=test_runner_base.ERROR_STATUS,
    details='someInvocationFailureReason',
    test_count=1,
    test_time='',
    runner_total=None,
    group_total=None,
    additional_info={},
    test_run_name='com.android.UnitTests',
)

RESULT_IGNORED_TEST = test_runner_base.TestResult(
    runner_name='someTestRunner',
    group_name='someTestModule',
    test_name='someClassName#sostName',
    status=test_runner_base.IGNORED_STATUS,
    details=None,
    test_count=1,
    test_time='(10ms)',
    runner_total=None,
    group_total=2,
    additional_info={},
    test_run_name='com.android.UnitTests',
)

RESULT_ASSUMPTION_FAILED_TEST = test_runner_base.TestResult(
    runner_name='someTestRunner',
    group_name='someTestModule',
    test_name='someClassName#sostName',
    status=test_runner_base.ASSUMPTION_FAILED,
    details=None,
    test_count=1,
    test_time='(10ms)',
    runner_total=None,
    group_total=2,
    additional_info={},
    test_run_name='com.android.UnitTests',
)


# pylint: disable=protected-access
# pylint: disable=invalid-name
class ResultReporterUnittests(unittest.TestCase):
  """Unit tests for result_reporter.py"""

  def setUp(self):
    self.rr = result_reporter.ResultReporter()

  def tearDown(self):
    mock.patch.stopall()

  @mock.patch.object(result_reporter.ResultReporter, '_print_group_title')
  @mock.patch.object(result_reporter.ResultReporter, '_update_stats')
  @mock.patch.object(result_reporter.ResultReporter, '_print_result')
  def test_process_test_result(self, mock_print, mock_update, mock_title):
    """Test process_test_result method."""
    # Passed Test
    self.assertNotIn('someTestRunner', self.rr.runners)
    self.rr.process_test_result(RESULT_PASSED_TEST)
    self.assertIn('someTestRunner', self.rr.runners)
    group = self.rr.runners['someTestRunner'].get('someTestModule')
    self.assertIsNotNone(group)
    mock_title.assert_called_with(RESULT_PASSED_TEST)
    mock_update.assert_called_with(RESULT_PASSED_TEST, group)
    mock_print.assert_called_with(RESULT_PASSED_TEST)
    # Failed Test
    mock_title.reset_mock()
    self.rr.process_test_result(RESULT_FAILED_TEST)
    mock_title.assert_not_called()
    mock_update.assert_called_with(RESULT_FAILED_TEST, group)
    mock_print.assert_called_with(RESULT_FAILED_TEST)
    # Test with new Group
    mock_title.reset_mock()
    self.rr.process_test_result(RESULT_PASSED_TEST_MODULE_2)
    self.assertIn('someTestModule2', self.rr.runners['someTestRunner'])
    mock_title.assert_called_with(RESULT_PASSED_TEST_MODULE_2)
    # Test with new Runner
    mock_title.reset_mock()
    self.rr.process_test_result(RESULT_PASSED_TEST_RUNNER_2_NO_MODULE)
    self.assertIn('someTestRunner2', self.rr.runners)
    mock_title.assert_called_with(RESULT_PASSED_TEST_RUNNER_2_NO_MODULE)

  @mock.patch.object(result_reporter.ResultReporter, '_print_group_title')
  @mock.patch.object(result_reporter.ResultReporter, '_update_stats')
  @mock.patch.object(result_reporter.ResultReporter, '_print_result')
  def test_process_test_result_class_level_report(
      self, mock_print, mock_update, mock_title
  ):
    """Test process_test_result method reported by class level."""
    reporter = result_reporter.ResultReporter(class_level_report=True)

    reporter.process_test_result(RESULT_PASSED_TEST)

    self.assertIn('someTestRunner', reporter.runners)
    group = reporter.runners['someTestRunner'].get(
        'someTestModule:someClassName'
    )
    self.assertIsNotNone(group)
    mock_title.assert_called_with(RESULT_PASSED_TEST)
    mock_update.assert_called_with(RESULT_PASSED_TEST, group)
    mock_print.assert_called_with(RESULT_PASSED_TEST)

  def test_print_result_run_name(self):
    """Test print run name function in print_result method."""
    rr = result_reporter.ResultReporter()
    test_cases = [
        ('com.android.UnitTests', '(2h44m36.402s)'),
        ('com.android.UnitTests2', '(2h43m36.402s)'),
    ]
    for run_name, test_time in test_cases:
      with mock.patch('sys.stdout', new_callable=StringIO) as capture_output:
        rr._print_result(
            test_runner_base.TestResult(
                runner_name='runner_name',
                group_name='someTestModule',
                test_name='someClassName#someTestName',
                status=test_runner_base.FAILED_STATUS,
                details='someTrace',
                test_count=2,
                test_time=test_time,
                runner_total=None,
                group_total=2,
                additional_info={},
                test_run_name=run_name,
            )
        )
        # Make sure run name in the first line.
        capture_output_str = capture_output.getvalue().strip()
        self.assertIn(run_name, capture_output_str.split('\n')[0])

  def test_register_unsupported_runner(self):
    """Test register_unsupported_runner method."""
    self.rr.register_unsupported_runner('NotSupported')
    runner = self.rr.runners['NotSupported']
    self.assertIsNotNone(runner)
    self.assertEqual(runner, result_reporter.UNSUPPORTED_FLAG)

  def test_update_stats_passed(self):
    """Test _update_stats method."""
    # Passed Test
    group = result_reporter.RunStat()
    self.rr._update_stats(RESULT_PASSED_TEST, group)
    self.assertEqual(self.rr.run_stats.passed, 1)
    self.assertEqual(self.rr.run_stats.failed, 0)
    self.assertFalse(self.rr.run_stats.run_errors)
    self.assertEqual(self.rr.failed_tests, [])
    self.assertEqual(group.passed, 1)
    self.assertEqual(group.failed, 0)
    self.assertEqual(group.ignored, 0)
    self.assertFalse(group.run_errors)
    # Passed Test New Group
    group2 = result_reporter.RunStat()
    self.rr._update_stats(RESULT_PASSED_TEST_MODULE_2, group2)
    self.assertEqual(self.rr.run_stats.passed, 2)
    self.assertEqual(self.rr.run_stats.failed, 0)
    self.assertFalse(self.rr.run_stats.run_errors)
    self.assertEqual(self.rr.failed_tests, [])
    self.assertEqual(group2.passed, 1)
    self.assertEqual(group2.failed, 0)
    self.assertEqual(group.ignored, 0)
    self.assertFalse(group2.run_errors)

  def test_update_stats_failed(self):
    """Test _update_stats method."""
    # Passed Test
    group = result_reporter.RunStat()
    self.rr._update_stats(RESULT_PASSED_TEST, group)
    # Passed Test New Group
    group2 = result_reporter.RunStat()
    self.rr._update_stats(RESULT_PASSED_TEST_MODULE_2, group2)
    # Failed Test Old Group
    self.rr._update_stats(RESULT_FAILED_TEST, group)
    self.assertEqual(self.rr.run_stats.passed, 2)
    self.assertEqual(self.rr.run_stats.failed, 1)
    self.assertFalse(self.rr.run_stats.run_errors)
    self.assertEqual(self.rr.failed_tests, [RESULT_FAILED_TEST.test_name])
    self.assertEqual(group.passed, 1)
    self.assertEqual(group.failed, 1)
    self.assertEqual(group.ignored, 0)
    self.assertEqual(group.total, 2)
    self.assertEqual(group2.total, 1)
    self.assertFalse(group.run_errors)
    # Test Run Failure
    self.rr._update_stats(RESULT_RUN_FAILURE, group)
    self.assertEqual(self.rr.run_stats.passed, 2)
    self.assertEqual(self.rr.run_stats.failed, 1)
    self.assertTrue(self.rr.run_stats.run_errors)
    self.assertEqual(self.rr.failed_tests, [RESULT_FAILED_TEST.test_name])
    self.assertEqual(group.passed, 1)
    self.assertEqual(group.failed, 1)
    self.assertEqual(group.ignored, 0)
    self.assertTrue(group.run_errors)
    self.assertFalse(group2.run_errors)
    # Invocation Failure
    self.rr._update_stats(RESULT_INVOCATION_FAILURE, group)
    self.assertEqual(self.rr.run_stats.passed, 2)
    self.assertEqual(self.rr.run_stats.failed, 1)
    self.assertTrue(self.rr.run_stats.run_errors)
    self.assertEqual(self.rr.failed_tests, [RESULT_FAILED_TEST.test_name])
    self.assertEqual(group.passed, 1)
    self.assertEqual(group.failed, 1)
    self.assertEqual(group.ignored, 0)
    self.assertTrue(group.run_errors)

  def test_update_stats_ignored_and_assumption_failure(self):
    """Test _update_stats method."""
    # Passed Test
    group = result_reporter.RunStat()
    self.rr._update_stats(RESULT_PASSED_TEST, group)
    # Passed Test New Group
    group2 = result_reporter.RunStat()
    self.rr._update_stats(RESULT_PASSED_TEST_MODULE_2, group2)
    # Failed Test Old Group
    self.rr._update_stats(RESULT_FAILED_TEST, group)
    # Test Run Failure
    self.rr._update_stats(RESULT_RUN_FAILURE, group)
    # Invocation Failure
    self.rr._update_stats(RESULT_INVOCATION_FAILURE, group)
    # Ignored Test
    self.rr._update_stats(RESULT_IGNORED_TEST, group)
    self.assertEqual(self.rr.run_stats.passed, 2)
    self.assertEqual(self.rr.run_stats.failed, 1)
    self.assertTrue(self.rr.run_stats.run_errors)
    self.assertEqual(self.rr.failed_tests, [RESULT_FAILED_TEST.test_name])
    self.assertEqual(group.passed, 1)
    self.assertEqual(group.failed, 1)
    self.assertEqual(group.ignored, 1)
    self.assertTrue(group.run_errors)
    # 2nd Ignored Test
    self.rr._update_stats(RESULT_IGNORED_TEST, group)
    self.assertEqual(self.rr.run_stats.passed, 2)
    self.assertEqual(self.rr.run_stats.failed, 1)
    self.assertTrue(self.rr.run_stats.run_errors)
    self.assertEqual(self.rr.failed_tests, [RESULT_FAILED_TEST.test_name])
    self.assertEqual(group.passed, 1)
    self.assertEqual(group.failed, 1)
    self.assertEqual(group.ignored, 2)
    self.assertTrue(group.run_errors)

    # Assumption_Failure test
    self.rr._update_stats(RESULT_ASSUMPTION_FAILED_TEST, group)
    self.assertEqual(group.assumption_failed, 1)
    # 2nd Assumption_Failure test
    self.rr._update_stats(RESULT_ASSUMPTION_FAILED_TEST, group)
    self.assertEqual(group.assumption_failed, 2)

  @mock.patch('atest.metrics.metrics.LocalDetectEvent')
  @mock.patch.object(atest_configs, 'GLOBAL_ARGS', DEFAULT_ARGS)
  def test_print_summary_ret_val(self, mock_detect_event):
    """Test print_summary method's return value."""
    # PASS Case
    self.rr.process_test_result(RESULT_PASSED_TEST)
    self.assertEqual(0, self.rr.print_summary())
    # PASS Case + Fail Case
    self.rr.process_test_result(RESULT_FAILED_TEST)
    self.assertNotEqual(0, self.rr.print_summary())
    # PASS Case + Fail Case + PASS Case
    self.rr.process_test_result(RESULT_PASSED_TEST_MODULE_2)
    self.assertNotEqual(0, self.rr.print_summary())
    mock_detect_event.assert_not_called()

  @mock.patch.object(atest_configs, 'GLOBAL_ARGS', DEFAULT_ARGS)
  def test_print_summary_ret_val_err_stat(self):
    """Test print_summary method's return value."""
    # PASS Case
    self.rr.process_test_result(RESULT_PASSED_TEST)
    self.assertEqual(0, self.rr.print_summary())
    # PASS Case + Fail Case
    self.rr.process_test_result(RESULT_RUN_FAILURE)
    self.assertNotEqual(0, self.rr.print_summary())
    # PASS Case + Fail Case + PASS Case
    self.rr.process_test_result(RESULT_PASSED_TEST_MODULE_2)
    self.assertNotEqual(0, self.rr.print_summary())

  @mock.patch('atest.metrics.metrics.LocalDetectEvent')
  @mock.patch.object(atest_configs, 'GLOBAL_ARGS', DEFAULT_ARGS)
  def test_print_summary_ret_val_err_stat2(self, mock_detect_event):
    """Test print_summary method's return value."""
    # PASS Case
    self.rr.process_test_result(RESULT_PASSED_TEST)
    # PASS Case + Run Error Case
    self.rr.process_test_result(RESULT_RUN_FAILURE)
    # PASS Case + Run Error Case + PASS Case
    self.rr.process_test_result(RESULT_PASSED_TEST_MODULE_2)
    # PASS Case + Run Error Case + PASS Case + Run Error Case
    self.rr.process_test_result(RESULT_RUN_FAILURE_2)

    self.assertNotEqual(0, self.rr.print_summary())
    mock_detect_event.assert_called_with(
        detect_type=atest_enum.DetectType.RUN_ERROR_COUNT,
        result=2,
    )

  @mock.patch.object(atest_configs, 'GLOBAL_ARGS', DEFAULT_ARGS)
  def test_print_summary_ret_val_err_stat_with_run_error_downgraded(self):
    """Test print_summary method's return value."""
    reporter = result_reporter.ResultReporter(runner_errors_as_warnings=True)
    # PASS Case
    reporter.process_test_result(RESULT_PASSED_TEST)
    self.assertEqual(0, reporter.print_summary())
    # PASS Case + Fail Case
    reporter.process_test_result(RESULT_RUN_FAILURE)
    self.assertEqual(0, reporter.print_summary())
    # PASS Case + Fail Case + PASS Case
    reporter.process_test_result(RESULT_PASSED_TEST_MODULE_2)
    self.assertEqual(0, reporter.print_summary())

  def test_collect_tests_only_no_throw(self):
    rr = result_reporter.ResultReporter(collect_only=True)
    rr.process_test_result(RESULT_PASSED_TEST)

    self.assertEqual(0, self.rr.print_collect_tests())


if __name__ == '__main__':
  unittest.main()
