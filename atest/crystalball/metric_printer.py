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

import argparse
import logging
import pathlib
import re

from atest import atest_utils
from atest import constants
from atest.test_runners import test_runner_base

PERF_TEST_TEMPLATE = 'template/performance-tests-base'
PERF_MODULE_ARG_NAME = '--perf'


BENCHMARK_ESSENTIAL_KEYS = {
    'repetition_index',
    'cpu_time',
    'name',
    'repetitions',
    'run_type',
    'threads',
    'time_unit',
    'iterations',
    'run_name',
    'real_time',
}
# TODO(b/146875480): handle the optional benchmark events
BENCHMARK_OPTIONAL_KEYS = {'bytes_per_second', 'label'}
BENCHMARK_EVENT_KEYS = BENCHMARK_ESSENTIAL_KEYS.union(BENCHMARK_OPTIONAL_KEYS)
INT_KEYS = {}


class PerfInfo:
  """Class for storing performance test of a test run."""

  def __init__(self):
    """Initialize a new instance of PerfInfo class."""
    # perf_info: A list of benchmark_info(dict).
    self.perf_info = []

  def update_perf_info(self, test):
    """Update perf_info with the given result of a single test.

    Args:
        test: A TestResult namedtuple.
    """
    all_additional_keys = set(test.additional_info.keys())
    # Ensure every key is in all_additional_keys.
    if not BENCHMARK_ESSENTIAL_KEYS.issubset(all_additional_keys):
      return
    benchmark_info = {}
    benchmark_info['test_name'] = test.test_name
    for key, data in test.additional_info.items():
      if key in INT_KEYS:
        data_to_int = data.split('.')[0]
        benchmark_info[key] = data_to_int
      elif key in BENCHMARK_EVENT_KEYS:
        benchmark_info[key] = data
    if benchmark_info:
      self.perf_info.append(benchmark_info)

  def print_perf_info(self):
    """Print summary of a perf_info."""
    if not self.perf_info:
      return
    classify_perf_info, max_len = self._classify_perf_info()
    separator = '-' * atest_utils.get_terminal_size()[0]
    print(separator)
    print(
        '{:{name}}    {:^{real_time}}    {:^{cpu_time}}    '
        '{:>{iterations}}'.format(
            'Benchmark',
            'Time',
            'CPU',
            'Iteration',
            name=max_len['name'] + 3,
            real_time=max_len['real_time'] + max_len['time_unit'] + 1,
            cpu_time=max_len['cpu_time'] + max_len['time_unit'] + 1,
            iterations=max_len['iterations'],
        )
    )
    print(separator)
    for module_name, module_perf_info in classify_perf_info.items():
      print('{}:'.format(module_name))
      for benchmark_info in module_perf_info:
        # BpfBenchMark/MapWriteNewEntry/1    1530 ns     1522 ns   460517
        print(
            '  #{:{name}}    {:>{real_time}} {:{time_unit}}    '
            '{:>{cpu_time}} {:{time_unit}}    '
            '{:>{iterations}}'.format(
                benchmark_info['name'],
                benchmark_info['real_time'],
                benchmark_info['time_unit'],
                benchmark_info['cpu_time'],
                benchmark_info['time_unit'],
                benchmark_info['iterations'],
                name=max_len['name'],
                real_time=max_len['real_time'],
                time_unit=max_len['time_unit'],
                cpu_time=max_len['cpu_time'],
                iterations=max_len['iterations'],
            )
        )

  def _classify_perf_info(self):
    """Classify the perf_info by test module name.

    Returns:
        A tuple of (classified_perf_info, max_len), where
        classified_perf_info: A dict of perf_info and each perf_info are
                             belong to different modules.
            e.g.
                { module_name_01: [perf_info of module_1],
                  module_name_02: [perf_info of module_2], ...}
        max_len: A dict which stores the max length of each event.
                 It contains the max string length of 'name', real_time',
                 'time_unit', 'cpu_time', 'iterations'.
            e.g.
                {name: 56, real_time: 9, time_unit: 2, cpu_time: 8,
                 iterations: 12}
    """
    module_categories = set()
    max_len = {}
    all_name = []
    all_real_time = []
    all_time_unit = []
    all_cpu_time = []
    all_iterations = ['Iteration']
    for benchmark_info in self.perf_info:
      module_categories.add(benchmark_info['test_name'].split('#')[0])
      all_name.append(benchmark_info['name'])
      all_real_time.append(benchmark_info['real_time'])
      all_time_unit.append(benchmark_info['time_unit'])
      all_cpu_time.append(benchmark_info['cpu_time'])
      all_iterations.append(benchmark_info['iterations'])
    classified_perf_info = {}
    for module_name in module_categories:
      module_perf_info = []
      for benchmark_info in self.perf_info:
        if benchmark_info['test_name'].split('#')[0] == module_name:
          module_perf_info.append(benchmark_info)
      classified_perf_info[module_name] = module_perf_info
    max_len = {
        'name': len(max(all_name, key=len)),
        'real_time': len(max(all_real_time, key=len)),
        'time_unit': len(max(all_time_unit, key=len)),
        'cpu_time': len(max(all_cpu_time, key=len)),
        'iterations': len(max(all_iterations, key=len)),
    }
    return classified_perf_info, max_len

  @staticmethod
  def print_banchmark_result(test: test_runner_base.TestResult):
    for key, data in sorted(test.additional_info.items()):
      if key not in BENCHMARK_EVENT_KEYS:
        print(f'\t{atest_utils.mark_blue(key)}: {data}')

  @classmethod
  def print_perf_test_metrics(cls, test_infos, log_path, args) -> bool:
    """Print perf test metrics text content to console.

    Returns:
        True if metric printing is attempted; False if not perf tests.
    """
    if not any(
        'performance-tests' in info.compatibility_suites for info in test_infos
    ):
      return False

    if not log_path:
      return True

    aggregated_metric_files = atest_utils.find_files(
        log_path, file_name='*_aggregate_test_metrics_*.txt'
    )

    if args.perf_itr_metrics:
      individual_metric_files = atest_utils.find_files(
          log_path, file_name='test_results_*.txt'
      )
      print('\n{}'.format(atest_utils.mark_cyan('Individual test metrics')))
      print(atest_utils.delimiter('-', 7))
      for metric_file in individual_metric_files:
        metric_file_path = pathlib.Path(metric_file)
        # Skip aggregate metrics as we are printing individual metrics here.
        if '_aggregate_test_metrics_' in metric_file_path.name:
          continue
        print('{}:'.format(atest_utils.mark_cyan(metric_file_path.name)))
        print(
            ''.join(
                f'{" "*4}{line}'
                for line in metric_file_path.read_text(
                    encoding='utf-8'
                ).splitlines(keepends=True)
            )
        )

    print('\n{}'.format(atest_utils.mark_cyan('Aggregate test metrics')))
    print(atest_utils.delimiter('-', 7))
    for metric_file in aggregated_metric_files:
      cls._print_test_metric(pathlib.Path(metric_file), args)

    return True

  @staticmethod
  def _print_test_metric(
      metric_file: pathlib.Path, args: argparse.Namespace
  ) -> None:
    """Print the content of the input metric file."""
    test_metrics_re = re.compile(
        r'test_results.*\s(.*)_aggregate_test_metrics_.*\.txt'
    )
    if not metric_file.is_file():
      return
    matches = re.findall(test_metrics_re, metric_file.as_posix())
    test_name = matches[0] if matches else ''
    if test_name:
      print('{}:'.format(atest_utils.mark_cyan(test_name)))
      with metric_file.open('r', encoding='utf-8') as f:
        matched = False
        filter_res = args.aggregate_metric_filter
        logging.debug('Aggregate metric filters: %s', filter_res)
        test_methods = []
        # Collect all test methods
        if filter_res:
          test_re = re.compile(r'\n\n(\S+)\n\n', re.MULTILINE)
          test_methods = re.findall(test_re, f.read())
          f.seek(0)
          # The first line of the file is also a test method but could
          # not parsed by test_re; add the first line manually.
          first_line = f.readline()
          test_methods.insert(0, str(first_line).strip())
          f.seek(0)
        for line in f.readlines():
          stripped_line = str(line).strip()
          if filter_res:
            if stripped_line in test_methods:
              print()
              atest_utils.colorful_print(
                  ' ' * 4 + stripped_line, constants.MAGENTA
              )
            for filter_re in filter_res:
              if re.match(re.compile(filter_re), line):
                matched = True
                print(' ' * 4 + stripped_line)
          else:
            matched = True
            print(' ' * 4 + stripped_line)
        if not matched:
          atest_utils.colorful_print(
              '  Warning: Nothing returned by the pattern: {}'.format(
                  filter_res
              ),
              constants.RED,
          )
        print()
