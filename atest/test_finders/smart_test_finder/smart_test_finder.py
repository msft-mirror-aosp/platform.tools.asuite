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
import json
import logging
import os
import pathlib
import sys
from typing import Any
from typing import Dict
from typing import List
from atest import atest_utils
from atest import constants
from atest.proto import decision_graph_pb2
from atest.test_finders import module_finder
from atest.test_finders import test_info
from atest.test_finders.smart_test_finder import atp_test_selector
from atest.test_finders.smart_test_finder import local_info_collector
from atest.test_finders.smart_test_finder import smart_test_filter
from atest.test_finders.smart_test_finder import test_relevance_client
from google.protobuf import json_format


def get_smartly_selected_tests(
    time_limit_in_minutes: int = 5,
) -> List[test_info.TestInfo]:
  """Given a time limit, smartly select tests to run."""
  local_change_info = local_info_collector.get_local_change_info()
  candidate_atp_tests = atp_test_selector.get_selected_atp_tests(
      local_change_info
  )
  client = test_relevance_client.TestRelevanceClient()
  dg_outputs = client.get_tests_with_relevance_score_query_by_query(
      local_change_info, candidate_atp_tests
  )
  if not dg_outputs:
    atest_utils.print_and_log_warning(
        'No results returned from searching for relevance score'
    )
    return []

  candidate_test_classes = []
  for dg_output in dg_outputs:
    test_classes = (
        test_relevance_client.get_test_class_infos_from_decision_graph_output(
            dg_output
        )
    )
    candidate_test_classes.extend(test_classes)

  final_selected_tests = []
  for test_class in smart_test_filter.get_selected_test_classes(
      candidate_test_classes, time_limit_in_minutes
  ):
    final_selected_tests.append(f'{test_class.module}:{test_class.test_class}')
  return final_selected_tests
