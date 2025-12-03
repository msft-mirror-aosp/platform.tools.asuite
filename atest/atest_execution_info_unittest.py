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
from atest import atest_enum
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
      self, directory_path: pathlib.Path, prefix: str
  ) -> bool:
    """Returns True if dir contains any file that starts with prefix."""
    return any(
        file.is_file() and file.name.startswith(prefix)
        for file in directory_path.iterdir()
    )


class SendIncrementalSetupStatTests(fake_filesystem_unittest.TestCase):

  _HOST_LOG_1_CONTENT = """\
[ApkChangeDetector] Skipping the installation of SystemUIApp
Installing apk android.CtsApp
[ApkChangeDetector] Skipping the uninstallation of SystemUIApp"""

  _HOST_LOG_2_CONTENT = """\
[ApkChangeDetector] Skipping the installation of SysUIRobolectricApp
 Installing apk a.b.c.d
 [UnrelatedClass] Skipping the installation of SomeClass"""

  def setUp(self):
    super().setUp()
    self.setUpPyfakefs()
    self.fs.create_dir(constants.ATEST_RESULT_ROOT)
    self._log_path = pathlib.Path('/tmp')

  def tearDown(self):
    if os.path.exists(str(self._log_path)):
      self.fs.remove_object(str(self._log_path))
    super().tearDown()

  @patch('atest.metrics.metrics.LocalDetectEvent', autospec=True)
  def test_parse_test_log_and_send_app_installation_stats_metrics_get_stats_successful(
      self,
      mock_detect_event,
  ):
    host_log_path1 = self._log_path / 'host_log_1.txt'
    host_log_path2 = self._log_path / 'invocation' / 'host_log_2.txt'
    self.fs.create_file(
        host_log_path1,
        contents=self._HOST_LOG_1_CONTENT,
        create_missing_dirs=True,
    )
    self.fs.create_file(
        host_log_path2,
        contents=self._HOST_LOG_2_CONTENT,
        create_missing_dirs=True,
    )
    expected_calls = [
        unittest.mock.call(
            detect_type=atest_enum.DetectType.APP_INSTALLATION_SKIPPED_COUNT,
            result=2,
        ),
        unittest.mock.call(
            detect_type=atest_enum.DetectType.APP_INSTALLATION_NOT_SKIPPED_COUNT,
            result=2,
        ),
    ]

    aei.parse_test_log_and_send_app_installation_stats_metrics(self._log_path)

    mock_detect_event.assert_has_calls(expected_calls, any_order=True)

  @patch('atest.metrics.metrics.LocalDetectEvent', autospec=True)
  def test_parse_test_log_and_send_app_installation_stats_metrics_no_host_log(
      self,
      mock_detect_event,
  ):
    aei.parse_test_log_and_send_app_installation_stats_metrics(self._log_path)

    mock_detect_event.assert_not_called()

  @patch('atest.metrics.metrics.LocalDetectEvent', autospec=True)
  def test_parse_test_log_and_send_app_installation_stats_metrics_no_info_in_host_log(
      self,
      mock_detect_event,
  ):
    host_log_path1 = self._log_path / 'host_log_1.txt'
    host_log_path2 = self._log_path / 'invocation' / 'host_log_2.txt'
    self.fs.create_file(host_log_path1, contents='', create_missing_dirs=True)
    self.fs.create_file(host_log_path2, contents='', create_missing_dirs=True)
    expected_calls = [
        unittest.mock.call(
            detect_type=atest_enum.DetectType.APP_INSTALLATION_SKIPPED_COUNT,
            result=0,
        ),
        unittest.mock.call(
            detect_type=atest_enum.DetectType.APP_INSTALLATION_NOT_SKIPPED_COUNT,
            result=0,
        ),
    ]

    aei.parse_test_log_and_send_app_installation_stats_metrics(self._log_path)

    mock_detect_event.assert_has_calls(expected_calls, any_order=True)


# pylint: disable=protected-access
class AtestExecutionInfoUnittests(unittest.TestCase):
  """Unit tests for atest_execution_info.py"""

  @patch(
      'atest.metrics.metrics.is_internal_user',
      return_value=False,
      autospec=True,
  )
  def test_create_bug_report_url_is_external_user_return_empty(self, _):
    url = aei.AtestExecutionInfo._create_bug_report_url()

    self.assertFalse(url)

  @patch(
      'atest.metrics.metrics.is_internal_user', return_value=True, autospec=True
  )
  def test_create_bug_report_url_is_internal_user_return_url(self, _):
    url = aei.AtestExecutionInfo._create_bug_report_url()

    self.assertTrue(url)

  @patch(
      'atest.metrics.metrics.is_internal_user', return_value=True, autospec=True
  )
  @patch(
      'atest.logstorage.log_uploader.is_uploading_logs',
      return_value=True,
      autospec=True,
  )
  def test_create_bug_report_url_is_uploading_logs_use_contains_run_id(
      self, _, __
  ):
    url = aei.AtestExecutionInfo._create_bug_report_url()

    self.assertIn(metrics.get_run_id(), url)

  @patch(
      'atest.metrics.metrics.is_internal_user', return_value=True, autospec=True
  )
  @patch(
      'atest.logstorage.log_uploader.is_uploading_logs',
      return_value=False,
      autospec=True,
  )
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
    """Helper to create a TestResult object, optionally overriding default values."""
    test_info = test_runner_base.TestResult(**RESULT_TEST_TEMPLATE._asdict())
    return test_info._replace(**kwargs)


class RenameInvocationPathnamesTest(fake_filesystem_unittest.TestCase):

  def setUp(self):
    self.setUpPyfakefs()
    self.fs.create_dir(pathlib.Path('/logs'))

  def test_append_test_info_to_invocation_pathnames_inv_paths_successfully_renamed(
      self,
  ):
    log_path = pathlib.Path('/logs')
    inv_path1 = log_path / 'log/stub/local_atest/inv_1'
    self.fs.create_dir(inv_path1)
    host_log_path1 = inv_path1 / 'host_log_test1.txt'
    self.fs.create_file(
        host_log_path1,
        contents="""
        Running tests with filter --some-filter filter_value --atest-include-filter TestAModule:com.package.TestAClass --some-other-filter other_filter_value
        Creating temp file at /logs/log/stub/local_atest/inv_1
        """,
    )
    inv_path2 = log_path / 'log/stub/local_atest/inv_2'
    self.fs.create_dir(inv_path2)
    inv_path3 = log_path / 'log/stub/local_atest/inv_3'
    self.fs.create_dir(inv_path3)
    host_log_path2 = inv_path2 / 'host_log_test2.txt'
    self.fs.create_file(
        host_log_path2,
        contents="""
        Running tests with filter --some-filter filter_value --atest-include-filter TestBModule:com.package.TestBClass#testBMethod --some-other-filter other_filter_value
        Creating temp file at /logs/log/stub/local_atest/inv_2
        Creating temp file at /logs/log/stub/local_atest/inv_3
        """,
    )
    inv_path4 = log_path / 'log/stub/local_atest/inv_4'
    self.fs.create_dir(inv_path4)
    self.fs.create_dir(
        log_path
        / 'log/stub/local_atest/inv_4__TestCModule_com.package.TestCClass'
    )
    host_log_path4 = inv_path4 / 'host_log_test4.txt'
    self.fs.create_file(
        host_log_path4,
        contents="""
        Running tests with filter --some-filter filter_value --atest-include-filter TestCModule:com.package.TestCClass --some-other-filter other_filter_value --include-filter Cts*Test?MyModule
        Creating temp file at /logs/log/stub/local_atest/inv_4
        """,
    )

    aei.append_test_info_to_invocation_pathnames(log_path)

    self.assertFalse(os.path.exists('/logs/log/stub/local_atest/inv_1'))
    self.assertFalse(os.path.exists('/logs/log/stub/local_atest/inv_2'))
    self.assertTrue(os.path.exists('/logs/log/stub/local_atest/inv_3'))
    self.assertFalse(os.path.exists('/logs/log/stub/local_atest/inv_4'))
    self.assertTrue(
        os.path.exists(
            '/logs/log/stub/local_atest/inv_1__TestAModule_com.package.TestAClass'
        )
    )
    self.assertTrue(
        os.path.exists(
            '/logs/log/stub/local_atest/inv_2__TestBModule_com.package.TestBClass_testBMethod'
        )
    )
    self.assertFalse(
        os.path.exists(
            '/logs/log/stub/local_atest/inv_3__TestBModule_com.package.TestBClass_testBMethod'
        )
    )
    self.assertTrue(
        os.path.exists(
            '/logs/log/stub/local_atest/inv_4__TestCModule_com.package.TestCClass/host_log_test4.txt'
        )
    )

  def test_append_test_info_to_invocation_pathnames_inv_paths_no_rename_due_to_no_test_filter(
      self,
  ):
    log_path = pathlib.Path('/logs')
    inv_path1 = log_path / 'log/stub/local_atest/inv_1'
    self.fs.create_dir(inv_path1)
    host_log_path1 = inv_path1 / 'host_log_test1.txt'
    self.fs.create_file(
        host_log_path1,
        contents="""
        Running tests with filter --some-filter filter_value --include-filter TestAModule:com.package.TestAClass --some-other-filter other_filter_value
        Creating temp file at /logs/log/stub/local_atest/inv_1
        """,
    )

    aei.append_test_info_to_invocation_pathnames(log_path)

    self.assertTrue(os.path.exists('/logs/log/stub/local_atest/inv_1'))
    self.assertFalse(
        os.path.exists(
            '/logs/log/stub/local_atest/inv_1__TestAModule_com.package.TestAClass'
        )
    )

  def test_append_test_info_to_invocation_pathnames_inv_paths_no_rename_due_to_no_inv_path(
      self,
  ):
    log_path = pathlib.Path('/logs')
    inv_path1 = log_path / 'log/stub/local_atest/inv_1'
    self.fs.create_dir(inv_path1)
    host_log_path1 = inv_path1 / 'host_log_test1.txt'
    self.fs.create_file(
        host_log_path1,
        contents="""
        Running tests with filter --some-filter filter_value --atest-include-filter TestAModule:com.package.TestAClass --some-other-filter other_filter_value
        Creating super awesome log at /logs/log/stub/local_atest/inv_1
        """,
    )

    aei.append_test_info_to_invocation_pathnames(log_path)

    self.assertTrue(os.path.exists('/logs/log/stub/local_atest/inv_1'))
    self.assertFalse(
        os.path.exists(
            '/logs/log/stub/local_atest/inv_1__TestAModule_com.package.TestAClass'
        )
    )


if __name__ == '__main__':
  unittest.main()
