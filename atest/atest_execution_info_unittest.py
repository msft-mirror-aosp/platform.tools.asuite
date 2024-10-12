#!/usr/bin/env python3
#
# Copyright 2019, The Android Open Source Project
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

"""Unittest for atest_execution_info."""


import os
import pathlib
import time
import unittest
from unittest.mock import patch
from atest import arg_parser
from atest import atest_execution_info as aei
from atest import constants
from atest import result_reporter
from atest.metrics import metrics
from atest.test_runners import test_runner_base
from pyfakefs import fake_filesystem_unittest

RESULT_TEST_TEMPLATE = test_runner_base.TestResult(
    runner_name='someRunner',
    group_name='someModule',
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


class CopyBuildTraceToLogsTests(fake_filesystem_unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.setUpPyfakefs()
    self.fs.create_dir(constants.ATEST_RESULT_ROOT)

  def test_copy_build_artifacts_to_log_dir_new_trace_copy(self):
    start_time = 10
    log_path = pathlib.Path('/logs')
    self.fs.create_dir(log_path)
    out_path = pathlib.Path('/out')
    build_trace_path = out_path / 'build.trace'
    self.fs.create_file(build_trace_path)
    # Set the trace file's mtime greater than start time
    os.utime(build_trace_path, (20, 20))
    end_time = 30

    aei.AtestExecutionInfo._copy_build_artifacts_to_log_dir(
        start_time, end_time, out_path, log_path, 'build.trace'
    )

    self.assertTrue(
        self._is_dir_contains_files_with_prefix(log_path, 'build.trace')
    )

  def test_copy_build_artifacts_to_log_dir_old_trace_does_not_copy(self):
    start_time = 10
    log_path = pathlib.Path('/logs')
    self.fs.create_dir(log_path)
    out_path = pathlib.Path('/out')
    build_trace_path = out_path / 'build.trace'
    self.fs.create_file(build_trace_path)
    # Set the trace file's mtime smaller than start time
    os.utime(build_trace_path, (5, 5))
    end_time = 30

    aei.AtestExecutionInfo._copy_build_artifacts_to_log_dir(
        start_time, end_time, out_path, log_path, 'build.trace'
    )

    self.assertFalse(
        self._is_dir_contains_files_with_prefix(log_path, 'build.trace')
    )

  def test_copy_multiple_build_trace_to_log_dir(self):
    start_time = 10
    log_path = pathlib.Path('/logs')
    self.fs.create_dir(log_path)
    out_path = pathlib.Path('/out')
    build_trace_path1 = out_path / 'build.trace.1.gz'
    build_trace_path2 = out_path / 'build.trace.2.gz'
    self.fs.create_file(build_trace_path1)
    self.fs.create_file(build_trace_path2)
    # Set the trace file's mtime greater than start time
    os.utime(build_trace_path1, (20, 20))
    os.utime(build_trace_path2, (20, 20))
    end_time = 30

    aei.AtestExecutionInfo._copy_build_artifacts_to_log_dir(
        start_time, end_time, out_path, log_path, 'build.trace'
    )

    self.assertTrue(
        self._is_dir_contains_files_with_prefix(log_path, 'build.trace.1.gz')
    )
    self.assertTrue(
        self._is_dir_contains_files_with_prefix(log_path, 'build.trace.2.gz')
    )

  def _is_dir_contains_files_with_prefix(
      self, dir: pathlib.Path, prefix: str
  ) -> bool:
    for file in dir.iterdir():
      if file.is_file() and file.name.startswith(prefix):
        return True
    return False


# pylint: disable=protected-access
class AtestExecutionInfoUnittests(unittest.TestCase):
  """Unit tests for atest_execution_info.py"""

  @patch('atest.metrics.metrics.is_internal_user', return_value=False)
  def test_create_bug_report_url_is_external_user_return_empty(self, _):
    url = aei.AtestExecutionInfo._create_bug_report_url()

    self.assertFalse(url)

  @patch('atest.metrics.metrics.is_internal_user', return_value=True)
  def test_create_bug_report_url_is_internal_user_return_url(self, _):
    url = aei.AtestExecutionInfo._create_bug_report_url()

    self.assertTrue(url)

  @patch('atest.metrics.metrics.is_internal_user', return_value=True)
  @patch('atest.logstorage.log_uploader.is_uploading_logs', return_value=True)
  def test_create_bug_report_url_is_uploading_logs_use_contains_run_id(
      self, _, __
  ):
    url = aei.AtestExecutionInfo._create_bug_report_url()

    self.assertIn(metrics.get_run_id(), url)

  @patch('atest.metrics.metrics.is_internal_user', return_value=True)
  @patch('atest.logstorage.log_uploader.is_uploading_logs', return_value=False)
  def test_create_bug_report_url_is_not_uploading_logs_use_contains_run_id(
      self, _, __
  ):
    url = aei.AtestExecutionInfo._create_bug_report_url()

    self.assertNotIn(metrics.get_run_id(), url)

  def test_arrange_test_result_one_module(self):
    """Test _arrange_test_result method with only one module."""
    pass_1 = self._create_test_result(status=test_runner_base.PASSED_STATUS)
    pass_2 = self._create_test_result(status=test_runner_base.PASSED_STATUS)
    pass_3 = self._create_test_result(status=test_runner_base.PASSED_STATUS)
    fail_1 = self._create_test_result(status=test_runner_base.FAILED_STATUS)
    fail_2 = self._create_test_result(status=test_runner_base.FAILED_STATUS)
    ignore_1 = self._create_test_result(status=test_runner_base.IGNORED_STATUS)
    reporter_1 = result_reporter.ResultReporter()
    reporter_1.all_test_results.extend([pass_1, pass_2, pass_3])
    reporter_2 = result_reporter.ResultReporter()
    reporter_2.all_test_results.extend([fail_1, fail_2, ignore_1])
    info_dict = {}
    aei.AtestExecutionInfo._arrange_test_result(
        info_dict, [reporter_1, reporter_2]
    )
    expect_summary = {
        aei._STATUS_IGNORED_KEY: 1,
        aei._STATUS_FAILED_KEY: 2,
        aei._STATUS_PASSED_KEY: 3,
    }
    self.assertEqual(expect_summary, info_dict[aei._TOTAL_SUMMARY_KEY])

  def test_arrange_test_result_multi_module(self):
    """Test _arrange_test_result method with multi module."""
    group_a_pass_1 = self._create_test_result(
        group_name='grpup_a', status=test_runner_base.PASSED_STATUS
    )
    group_b_pass_1 = self._create_test_result(
        group_name='grpup_b', status=test_runner_base.PASSED_STATUS
    )
    group_c_pass_1 = self._create_test_result(
        group_name='grpup_c', status=test_runner_base.PASSED_STATUS
    )
    group_b_fail_1 = self._create_test_result(
        group_name='grpup_b', status=test_runner_base.FAILED_STATUS
    )
    group_c_fail_1 = self._create_test_result(
        group_name='grpup_c', status=test_runner_base.FAILED_STATUS
    )
    group_c_ignore_1 = self._create_test_result(
        group_name='grpup_c', status=test_runner_base.IGNORED_STATUS
    )
    reporter_1 = result_reporter.ResultReporter()
    reporter_1.all_test_results.extend(
        [group_a_pass_1, group_b_pass_1, group_c_pass_1]
    )
    reporter_2 = result_reporter.ResultReporter()
    reporter_2.all_test_results.extend(
        [group_b_fail_1, group_c_fail_1, group_c_ignore_1]
    )

    info_dict = {}
    aei.AtestExecutionInfo._arrange_test_result(
        info_dict, [reporter_1, reporter_2]
    )
    expect_group_a_summary = {
        aei._STATUS_IGNORED_KEY: 0,
        aei._STATUS_FAILED_KEY: 0,
        aei._STATUS_PASSED_KEY: 1,
    }
    self.assertEqual(
        expect_group_a_summary,
        info_dict[aei._TEST_RUNNER_KEY]['someRunner']['grpup_a'][
            aei._SUMMARY_KEY
        ],
    )

    expect_group_b_summary = {
        aei._STATUS_IGNORED_KEY: 0,
        aei._STATUS_FAILED_KEY: 1,
        aei._STATUS_PASSED_KEY: 1,
    }
    self.assertEqual(
        expect_group_b_summary,
        info_dict[aei._TEST_RUNNER_KEY]['someRunner']['grpup_b'][
            aei._SUMMARY_KEY
        ],
    )

    expect_group_c_summary = {
        aei._STATUS_IGNORED_KEY: 1,
        aei._STATUS_FAILED_KEY: 1,
        aei._STATUS_PASSED_KEY: 1,
    }
    self.assertEqual(
        expect_group_c_summary,
        info_dict[aei._TEST_RUNNER_KEY]['someRunner']['grpup_c'][
            aei._SUMMARY_KEY
        ],
    )

    expect_total_summary = {
        aei._STATUS_IGNORED_KEY: 1,
        aei._STATUS_FAILED_KEY: 2,
        aei._STATUS_PASSED_KEY: 3,
    }
    self.assertEqual(expect_total_summary, info_dict[aei._TOTAL_SUMMARY_KEY])

  def test_preparation_time(self):
    """Test preparation_time method."""
    start_time = time.time()
    aei.PREPARE_END_TIME = None
    self.assertTrue(aei.preparation_time(start_time) is None)
    aei.PREPARE_END_TIME = time.time()
    self.assertFalse(aei.preparation_time(start_time) is None)

  def test_arrange_test_result_multi_runner(self):
    """Test _arrange_test_result method with multi runner."""
    runner_a_pass_1 = self._create_test_result(
        runner_name='runner_a', status=test_runner_base.PASSED_STATUS
    )
    runner_a_pass_2 = self._create_test_result(
        runner_name='runner_a', status=test_runner_base.PASSED_STATUS
    )
    runner_a_pass_3 = self._create_test_result(
        runner_name='runner_a', status=test_runner_base.PASSED_STATUS
    )
    runner_b_fail_1 = self._create_test_result(
        runner_name='runner_b', status=test_runner_base.FAILED_STATUS
    )
    runner_b_fail_2 = self._create_test_result(
        runner_name='runner_b', status=test_runner_base.FAILED_STATUS
    )
    runner_b_ignore_1 = self._create_test_result(
        runner_name='runner_b', status=test_runner_base.IGNORED_STATUS
    )

    reporter_1 = result_reporter.ResultReporter()
    reporter_1.all_test_results.extend(
        [runner_a_pass_1, runner_a_pass_2, runner_a_pass_3]
    )
    reporter_2 = result_reporter.ResultReporter()
    reporter_2.all_test_results.extend(
        [runner_b_fail_1, runner_b_fail_2, runner_b_ignore_1]
    )
    info_dict = {}
    aei.AtestExecutionInfo._arrange_test_result(
        info_dict, [reporter_1, reporter_2]
    )
    expect_group_a_summary = {
        aei._STATUS_IGNORED_KEY: 0,
        aei._STATUS_FAILED_KEY: 0,
        aei._STATUS_PASSED_KEY: 3,
    }
    self.assertEqual(
        expect_group_a_summary,
        info_dict[aei._TEST_RUNNER_KEY]['runner_a']['someModule'][
            aei._SUMMARY_KEY
        ],
    )

    expect_group_b_summary = {
        aei._STATUS_IGNORED_KEY: 1,
        aei._STATUS_FAILED_KEY: 2,
        aei._STATUS_PASSED_KEY: 0,
    }
    self.assertEqual(
        expect_group_b_summary,
        info_dict[aei._TEST_RUNNER_KEY]['runner_b']['someModule'][
            aei._SUMMARY_KEY
        ],
    )

    expect_total_summary = {
        aei._STATUS_IGNORED_KEY: 1,
        aei._STATUS_FAILED_KEY: 2,
        aei._STATUS_PASSED_KEY: 3,
    }
    self.assertEqual(expect_total_summary, info_dict[aei._TOTAL_SUMMARY_KEY])

  def _create_test_result(self, **kwargs):
    """A Helper to create TestResult"""
    test_info = test_runner_base.TestResult(**RESULT_TEST_TEMPLATE._asdict())
    return test_info._replace(**kwargs)


if __name__ == '__main__':
  unittest.main()
