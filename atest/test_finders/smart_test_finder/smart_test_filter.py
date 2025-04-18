#!/usr/bin/env python3
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

import csv
from dataclasses import dataclass
import functools
import logging
import pathlib
from typing import Dict
from typing import List
from atest import constants


_NUM_MILLISECONDS_IN_MINUTES = 60000

# Opted-out test modules with reasons of crash or failure.
_OPTED_OUT_TEST_MODULES_WITH_REASONS = {
    'MtsLibcoreBouncyCastleTestCases': 'b/407985613',
    'aconfig_storage_file.test.cpp': 'b/408059183',
    'aconfig_storage_file.test.java': 'b/408059183',
    'aconfig_storage_read_api.test.cpp': 'b/408059183',
    'aconfig.test.cpp': 'b/408059183',
    'aconfig.test.java': 'b/408059183',
    'LauncherIronwoodIntegrationTests': 'b/409376364',
    'rustBinderTestService': 'b/409368039',
    'llvmlibc_tests': 'b/409370336',
    'CellBroadcastReceiverMTS': 'b/409371134',
    'DocumentsUIGoogleTests': 'b/409371134',
    'VibratorHalCs40l26TestSuite': 'b/409372845',
    'CtsWifiTestCases': 'No wifi support',
    'CtsTetheringTest': 'No wifi support',
    'CtsWifiBroadcastsHostTestCases': 'No wifi support',
    'MtsWifiTestCases': 'No wifi support',
}

@dataclass(frozen=True)
class TestClassInfo:
  test_id: str
  atp_test_name: str = ''
  branch: str = ''
  target: str = ''
  run_time: float = -1
  pass_rate: float = 0.0
  module: str = ''
  test_class: str = ''
  score: float = 0.0


@functools.cache
def _get_test_class_history() -> Dict[str, TestClassInfo]:
  """Get the mapping from test ID to test class history."""
  results = {}
  with open(
      str(
          pathlib.Path(constants.SMART_TEST_SELECTION_ROOT_PATH)
          / 'lookup_tables/tests_with_runtime_and_pass_rate.csv'
      ),
      'r',
      newline='',
  ) as csv_file:
    csv_reader = csv.DictReader(csv_file)
    for row in csv_reader:
      test_class_info = TestClassInfo(
          branch=row['branch'],
          target=row['target'],
          atp_test_name=row['test_name'],
          test_id=row['test_id'],
          run_time=float(row['test_run_duration_ms_past7days']),
          pass_rate=float(row['postsubmit_pass_rate']),
      )
      results[row['test_id']] = test_class_info

  return results


def get_selected_test_classes(
    candidate_tests: List[TestClassInfo], time_limit_min: int
) -> List[TestClassInfo]:
  """Get filtered test classes based on history and time limit to execute."""
  results = []
  test_class_history = _get_test_class_history()
  total_test_time = 0.0

  # Sort the candidate tests first by non-increasing score, then by
  # non-decreasing module name.
  for test in sorted(candidate_tests, key=lambda t: (-t.score, t.module)):
    logging.debug(
        'checking test %s:%s with score: %s',
        test.module,
        test.test_class,
        test.score,
    )
    if test.test_id not in test_class_history:
      logging.debug('No history of %s found, skipping', test.test_id)
      continue
    test_class_info = test_class_history[test.test_id]
    if not test.module or not test.test_class:
      logging.debug(
          'Can not find module/test_class info for Test %s, skipping',
          test.test_id,
      )
      continue
    if test.module in _OPTED_OUT_TEST_MODULES_WITH_REASONS:
      logging.debug(
          'Module %s is currently opted out from smart test selection,'
          ' skipping',
          test.module,
      )
      continue

    if test_class_info.pass_rate < 0.95:
      logging.debug('Test %s is flaky, skipping', test.test_id)
      continue
    if test_class_info.run_time < 0:
      logging.debug(
          'Can not determine the test run time for test %s, skipping',
          test.test_id,
      )
      continue
    if (
        total_test_time + test_class_info.run_time
        < time_limit_min * _NUM_MILLISECONDS_IN_MINUTES
    ):
      results.append(test)
      total_test_time += test_class_info.run_time
    else:
      break

  return results
