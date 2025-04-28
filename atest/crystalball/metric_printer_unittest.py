#!/usr/bin/env python
#
# Copyright 2025, The Android Open Source Project
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

import unittest

from atest import arg_parser
from atest import result_reporter
from atest.crystalball import metric_printer
from atest.test_finders import test_info
from atest.test_runners import test_runner_base


class TestPerfInfo(unittest.TestCase):

  def setUp(self):
    self.rr = result_reporter.ResultReporter()

  def test_update_perf_info(self):
    """Test update_perf_info method."""
    group = result_reporter.RunStat()
    # 1. Test PerfInfo after RESULT_PERF01_TEST01
    # _update_stats() will call _update_perf_info()
    self.rr._update_stats(RESULT_PERF01_TEST01, group)
    correct_perf_info = []
    trim_perf01_test01 = {
        'repetition_index': '0',
        'cpu_time': '10001.10001',
        'name': 'perfName01',
        'repetitions': '0',
        'run_type': 'iteration',
        'label': '2123',
        'threads': '1',
        'time_unit': 'ns',
        'iterations': '1001',
        'run_name': 'perfName01',
        'real_time': '11001.11001',
        'test_name': 'somePerfClass01#perfName01',
    }
    correct_perf_info.append(trim_perf01_test01)
    self.assertEqual(self.rr.run_stats.perf_info.perf_info, correct_perf_info)
    # 2. Test PerfInfo after RESULT_PERF01_TEST01
    self.rr._update_stats(RESULT_PERF01_TEST02, group)
    trim_perf01_test02 = {
        'repetition_index': '0',
        'cpu_time': '10002.10002',
        'name': 'perfName02',
        'repetitions': '0',
        'run_type': 'iteration',
        'label': '2123',
        'threads': '1',
        'time_unit': 'ns',
        'iterations': '1002',
        'run_name': 'perfName02',
        'real_time': '11002.11002',
        'test_name': 'somePerfClass01#perfName02',
    }
    correct_perf_info.append(trim_perf01_test02)
    self.assertEqual(self.rr.run_stats.perf_info.perf_info, correct_perf_info)
    # 3. Test PerfInfo after RESULT_PERF02_TEST01
    self.rr._update_stats(RESULT_PERF02_TEST01, group)
    trim_perf02_test01 = {
        'repetition_index': '0',
        'cpu_time': '20001.20001',
        'name': 'perfName11',
        'repetitions': '0',
        'run_type': 'iteration',
        'label': '2123',
        'threads': '1',
        'time_unit': 'ns',
        'iterations': '2001',
        'run_name': 'perfName11',
        'real_time': '21001.21001',
        'test_name': 'somePerfClass02#perfName11',
    }
    correct_perf_info.append(trim_perf02_test01)
    self.assertEqual(self.rr.run_stats.perf_info.perf_info, correct_perf_info)
    # 4. Test PerfInfo after RESULT_PERF01_TEST03_NO_CPU_TIME
    self.rr._update_stats(RESULT_PERF01_TEST03_NO_CPU_TIME, group)
    # Nothing added since RESULT_PERF01_TEST03_NO_CPU_TIME lack of cpu_time
    self.assertEqual(self.rr.run_stats.perf_info.perf_info, correct_perf_info)

  def test_classify_perf_info(self):
    """Test _classify_perf_info method."""
    group = result_reporter.RunStat()
    self.rr._update_stats(RESULT_PERF01_TEST01, group)
    self.rr._update_stats(RESULT_PERF01_TEST02, group)
    self.rr._update_stats(RESULT_PERF02_TEST01, group)
    # trim the time form 10001.10001 to 10001
    trim_perf01_test01 = {
        'repetition_index': '0',
        'cpu_time': '10001.10001',
        'name': 'perfName01',
        'repetitions': '0',
        'run_type': 'iteration',
        'label': '2123',
        'threads': '1',
        'time_unit': 'ns',
        'iterations': '1001',
        'run_name': 'perfName01',
        'real_time': '11001.11001',
        'test_name': 'somePerfClass01#perfName01',
    }
    trim_perf01_test02 = {
        'repetition_index': '0',
        'cpu_time': '10002.10002',
        'name': 'perfName02',
        'repetitions': '0',
        'run_type': 'iteration',
        'label': '2123',
        'threads': '1',
        'time_unit': 'ns',
        'iterations': '1002',
        'run_name': 'perfName02',
        'real_time': '11002.11002',
        'test_name': 'somePerfClass01#perfName02',
    }
    trim_perf02_test01 = {
        'repetition_index': '0',
        'cpu_time': '20001.20001',
        'name': 'perfName11',
        'repetitions': '0',
        'run_type': 'iteration',
        'label': '2123',
        'threads': '1',
        'time_unit': 'ns',
        'iterations': '2001',
        'run_name': 'perfName11',
        'real_time': '21001.21001',
        'test_name': 'somePerfClass02#perfName11',
    }
    correct_classify_perf_info = {
        'somePerfClass01': [trim_perf01_test01, trim_perf01_test02],
        'somePerfClass02': [trim_perf02_test01],
    }
    classify_perf_info, max_len = (
        self.rr.run_stats.perf_info._classify_perf_info()
    )
    correct_max_len = {
        'real_time': 11,
        'cpu_time': 11,
        'name': 10,
        'iterations': 9,
        'time_unit': 2,
    }
    self.assertEqual(max_len, correct_max_len)
    self.assertEqual(classify_perf_info, correct_classify_perf_info)

  def test_print_perf_test_metrics_perf_tests_print_attempted(self):
    args = arg_parser.parse_args(['--perf', 'MyModule'])
    test_infos = [
        test_info.TestInfo(
            'some_module',
            'TestRunner',
            set(),
            compatibility_suites=['performance-tests'],
        )
    ]
    is_print_attempted = metric_printer.PerfInfo.print_perf_test_metrics(
        test_infos, 'log_path', args
    )

    self.assertTrue(is_print_attempted)

  def test_print_perf_test_metrics_not_perf_tests_print__not_attempted(self):
    args = arg_parser.parse_args(['MyModule'])
    test_infos = [
        test_info.TestInfo(
            'some_module',
            'TestRunner',
            set(),
            compatibility_suites=['not-perf-test'],
        )
    ]
    is_print_attempted = metric_printer.PerfInfo.print_perf_test_metrics(
        test_infos, 'log_path', args
    )

    self.assertFalse(is_print_attempted)


ADDITIONAL_INFO_PERF01_TEST01 = {
    'repetition_index': '0',
    'cpu_time': '10001.10001',
    'name': 'perfName01',
    'repetitions': '0',
    'run_type': 'iteration',
    'label': '2123',
    'threads': '1',
    'time_unit': 'ns',
    'iterations': '1001',
    'run_name': 'perfName01',
    'real_time': '11001.11001',
}

RESULT_PERF01_TEST01 = test_runner_base.TestResult(
    runner_name='someTestRunner',
    group_name='someTestModule',
    test_name='somePerfClass01#perfName01',
    status=test_runner_base.PASSED_STATUS,
    details=None,
    test_count=1,
    test_time='(10ms)',
    runner_total=None,
    group_total=2,
    additional_info=ADDITIONAL_INFO_PERF01_TEST01,
    test_run_name='com.android.UnitTests',
)

RESULT_PERF01_TEST02 = test_runner_base.TestResult(
    runner_name='someTestRunner',
    group_name='someTestModule',
    test_name='somePerfClass01#perfName02',
    status=test_runner_base.PASSED_STATUS,
    details=None,
    test_count=1,
    test_time='(10ms)',
    runner_total=None,
    group_total=2,
    additional_info={
        'repetition_index': '0',
        'cpu_time': '10002.10002',
        'name': 'perfName02',
        'repetitions': '0',
        'run_type': 'iteration',
        'label': '2123',
        'threads': '1',
        'time_unit': 'ns',
        'iterations': '1002',
        'run_name': 'perfName02',
        'real_time': '11002.11002',
    },
    test_run_name='com.android.UnitTests',
)

RESULT_PERF01_TEST03_NO_CPU_TIME = test_runner_base.TestResult(
    runner_name='someTestRunner',
    group_name='someTestModule',
    test_name='somePerfClass01#perfName03',
    status=test_runner_base.PASSED_STATUS,
    details=None,
    test_count=1,
    test_time='(10ms)',
    runner_total=None,
    group_total=2,
    additional_info={
        'repetition_index': '0',
        'name': 'perfName03',
        'repetitions': '0',
        'run_type': 'iteration',
        'label': '2123',
        'threads': '1',
        'time_unit': 'ns',
        'iterations': '1003',
        'run_name': 'perfName03',
        'real_time': '11003.11003',
    },
    test_run_name='com.android.UnitTests',
)

RESULT_PERF02_TEST01 = test_runner_base.TestResult(
    runner_name='someTestRunner',
    group_name='someTestModule',
    test_name='somePerfClass02#perfName11',
    status=test_runner_base.PASSED_STATUS,
    details=None,
    test_count=1,
    test_time='(10ms)',
    runner_total=None,
    group_total=2,
    additional_info={
        'repetition_index': '0',
        'cpu_time': '20001.20001',
        'name': 'perfName11',
        'repetitions': '0',
        'run_type': 'iteration',
        'label': '2123',
        'threads': '1',
        'time_unit': 'ns',
        'iterations': '2001',
        'run_name': 'perfName11',
        'real_time': '21001.21001',
    },
    test_run_name='com.android.UnitTests',
)

if __name__ == '__main__':
  unittest.main()
