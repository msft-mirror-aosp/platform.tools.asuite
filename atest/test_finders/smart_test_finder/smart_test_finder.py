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

"""The top-most module to automatically select tests based on local change infos."""

import logging
import os
import pathlib
from typing import List
from atest import atest_utils
from atest import constants
from atest import module_info
from atest.test_finders import test_finder_utils
from atest.test_finders import test_info
from atest.test_finders.smart_test_finder import atp_test_selector
from atest.test_finders.smart_test_finder import local_info_collector
from atest.test_finders.smart_test_finder import smart_test_filter
from atest.test_finders.smart_test_finder import test_relevance_client


# TODO(b/412399270): Remove this constant when the issue is fixed.
# Custom args for smart test selection
SMART_TEST_SELECTION_CUSTOM_ARGS = [
    '--test-arg',
    'com.android.tradefed.testtype.AndroidJUnitTest:shell-timeout:600000',
    '--test-arg',
    'com.android.tradefed.testtype.AndroidJUnitTest:test-timeout:600000',
    '--test-arg',
    'com.android.tradefed.testtype.AndroidJUnitTest:exclude-annotation:android.platform.test.annotations.FlakyTest',
    '--test-arg',
    'com.android.tradefed.testtype.AndroidJUnitTest:exclude-annotation:android.support.test.filters.FlakyTest',
    '--test-arg',
    'com.android.tradefed.testtype.AndroidJUnitTest:exclude-annotation:android.test.FlakyTest',
    '--test-arg',
    'com.android.tradefed.testtype.AndroidJUnitTest:exclude-annotation:androidx.test.filters.FlakyTest',
    '--test-arg',
    'com.android.tradefed.testtype.AndroidJUnitTest:exclude-annotation:org.junit.Ignore',
    '--test-arg',
    'com.android.tradefed.testtype.AndroidJUnitTest:exclude-annotation:android.support.test.filters.RequiresDevice',
    '--test-arg',
    'com.android.tradefed.testtype.AndroidJUnitTest:exclude-annotation:androidx.test.filters.RequiresDevice',
    '--test-arg',
    'com.android.tradefed.testtype.AndroidJUnitTest:exclude-annotation:android.platform.test.annotations.RequiresDevice',
    '--test-arg',
    'com.android.compatibility.testtype.LibcoreTest:exclude-annotation:android.support.test.filters.RequiresDevice',
    '--test-arg',
    'com.android.compatibility.testtype.LibcoreTest:exclude-annotation:androidx.test.filters.RequiresDevice',
    '--test-arg',
    'com.android.compatibility.testtype.LibcoreTest:exclude-annotation:android.platform.test.annotations.RequiresDevice',
    '--test-arg',
    'com.android.tradefed.testtype.HostTest:exclude-annotation:android.platform.test.annotations.RequiresDevice',
    '--test-arg',
    'com.android.compatibility.common.tradefed.testtype.JarHostTest:exclude-annotation:android.platform.test.annotations.RequiresDevice',
    '--exclude-filter',
    (
        "'CtsAppSecurityHostTestCases\\"
        " android.appsecurity.cts.ExternalStorageHostTest#testMediaLegacy28'"
    ),
    '--exclude-filter',
    (
        "'CtsQuickAccessWalletTestCases\\"
        " android.quickaccesswallet.cts.QuickAccessWalletClientTest#testAddListener_sendEvent_success'"
    ),
    '--exclude-filter',
    (
        "'CtsGraphicsTestCases\\"
        " android.graphics.cts.FrameRateOverrideTest#testAppBackpressure'"
    ),
]


def _get_selected_host_unit_tests(
    mod_info: module_info.ModuleInfo, root_dir: str
) -> List[str]:
  """Return host unit tests under the root directory."""
  if not (mod_info and root_dir):
    atest_utils.print_and_log_warning(
        'Missing module info or root directory, skip host unit tests searching.'
    )
    return []
  return test_finder_utils.find_host_unit_tests(
      mod_info, str(pathlib.Path(os.getcwd()).relative_to(root_dir))
  )


def _get_selected_tests_with_relevance_scores(
    time_limit_in_minutes: int,
) -> tuple[List[str], List[float]]:
  """Gets score based tests with their scores."""
  local_change_info = local_info_collector.get_local_change_info()
  logging.info('Local change info: %s', local_change_info)
  if not local_change_info.changed_files:
    atest_utils.print_and_log_warning(
        'No local change detected, skip relevance score based tests searching.'
    )
    return ([], [])

  selected_atp_tests = atp_test_selector.get_selected_atp_tests(
      local_change_info
  )
  logging.info('Selected ATP tests: %s', selected_atp_tests)
  if not selected_atp_tests:
    atest_utils.print_and_log_warning(
        'No ATP tests selected, skip relevance score based tests searching.'
    )
    return ([], [])

  atest_utils.colorful_print(
      'Retrieving relevant tests, this may take a few minutes...',
      constants.MAGENTA,
  )
  client = test_relevance_client.TestRelevanceClient()
  dg_outputs = client.get_tests_with_relevance_score_query_by_query(
      local_change_info, selected_atp_tests
  )
  logging.debug('DG_outputs: %s', dg_outputs)

  if not dg_outputs:
    atest_utils.print_and_log_warning(
        'No relevant tests found, skip relevance score based tests searching.'
    )
    return ([], [])

  candidate_test_classes = []
  for dg_output in dg_outputs:
    test_classes = (
        test_relevance_client.get_test_class_infos_from_decision_graph_output(
            dg_output
        )
    )
    candidate_test_classes.extend(test_classes)

  selected_test_classes = smart_test_filter.get_selected_test_classes(
      candidate_test_classes, time_limit_in_minutes
  )

  if not selected_test_classes:
    return ([], [])

  tests = []
  test_scores = []
  for selected_test_class in selected_test_classes:
    # Remove this once b/411508650 is fixed.
    if selected_test_class.module.startswith('art-run-test'):
      selected_test_class_str = selected_test_class.module
    else:
      # Special handling due to b/414872096
      split_class_name = selected_test_class.test_class.split('.')
      if (
          len(split_class_name) == 2
          and split_class_name[0] == selected_test_class.module
      ):
        selected_test_class_str = (
            f'{selected_test_class.module}:{split_class_name[1]}'
        )
      else:
        selected_test_class_str = (
            f'{selected_test_class.module}:{selected_test_class.test_class}'
        )
    tests.append(selected_test_class_str)
    test_scores.append(selected_test_class.score)
  return (tests, test_scores)


def _print_selected_tests(
    host_unit_tests: List[str],
    relevance_score_based_tests: List[str],
    relevance_scores: List[float],
):
  """Print selected tests."""
  atest_utils.colorful_print('\nSelected tests to run:', constants.CYAN)
  if host_unit_tests:
    atest_utils.colorful_print('\nHost unit tests:', constants.CYAN)
    for host_test in host_unit_tests:
      atest_utils.colorful_print(f'\t{host_test}', constants.CYAN)

  if relevance_score_based_tests:
    atest_utils.colorful_print(
        '\nTests based on relevance scores:', constants.CYAN
    )
    for test, score in zip(relevance_score_based_tests, relevance_scores):
      atest_utils.colorful_print(
          f'\t{test}:{score}',
          constants.CYAN,
      )


def get_smartly_selected_tests(
    time_limit_in_minutes: int = constants.SMART_TEST_EXECUTION_TIME_LIMIT_IN_MINUTES,
    include_host_unit_tests: bool = True,
    mod_info: module_info.ModuleInfo = None,
    root_dir: str = None,
) -> List[test_info.TestInfo]:
  """Given a time limit, smartly select tests to run."""
  host_unit_tests = (
      _get_selected_host_unit_tests(mod_info, root_dir)
      if include_host_unit_tests
      else []
  )
  score_based_tests_with_scores = _get_selected_tests_with_relevance_scores(
      time_limit_in_minutes
  )

  if host_unit_tests or score_based_tests_with_scores[0]:
    _print_selected_tests(
        host_unit_tests,
        score_based_tests_with_scores[0],
        score_based_tests_with_scores[1],
    )
  else:
    atest_utils.print_and_log_warning('No tests selected, exiting...')

  return host_unit_tests + score_based_tests_with_scores[0]
