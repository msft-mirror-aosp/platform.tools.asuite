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
from typing import List
from atest import atest_utils
from atest import constants
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
        'CtsAppSecurityHostTestCases'
        ' android.appsecurity.cts.ExternalStorageHostTest#testMediaLegacy28'
    ),
    '--exclude-filter',
    (
        'CtsQuickAccessWalletTestCases'
        ' android.quickaccesswallet.cts.QuickAccessWalletClientTest#testAddListener_sendEvent_success'
    ),
    '--exclude-filter',
    (
        'CtsGraphicsTestCases'
        ' android.graphics.cts.FrameRateOverrideTest#testAppBackpressure'
    ),
]


def get_smartly_selected_tests(
    time_limit_in_minutes: int = 5,
) -> List[test_info.TestInfo]:
  """Given a time limit, smartly select tests to run."""
  local_change_info = local_info_collector.get_local_change_info()
  logging.info('Local change info: %s', local_change_info)
  selected_atp_tests = atp_test_selector.get_selected_atp_tests(
      local_change_info
  )
  logging.info('Selected ATP tests: %s', selected_atp_tests)
  if not selected_atp_tests:
    atest_utils.print_and_log_warning('No ATP tests selected, exiting...')
    return []
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
    atest_utils.print_and_log_warning('No relevant tests found, exiting...')
    return []

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
    atest_utils.print_and_log_warning('No relevant tests selected, exiting...')
    return []

  final_selected_tests = []
  atest_utils.colorful_print('\nSelected tests to run:', constants.CYAN)
  for selected_test_class in selected_test_classes:
    selected_test_class_str = (
        f'{selected_test_class.module}:{selected_test_class.test_class}'
    )
    atest_utils.colorful_print(
        f'\t{selected_test_class_str}:{selected_test_class.score}',
        constants.CYAN,
    )
    final_selected_tests.append(selected_test_class_str)

  return final_selected_tests
