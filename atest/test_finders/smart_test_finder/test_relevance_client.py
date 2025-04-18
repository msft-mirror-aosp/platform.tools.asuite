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

import json
import logging
import time
from typing import Any
from typing import Dict
from typing import List
import uuid
from atest import atest_utils
from atest.proto import common_pb2
from atest.proto import decision_graph_pb2
from atest.test_finders.smart_test_finder import atp_test_selector
from atest.test_finders.smart_test_finder import local_info_collector
from atest.test_finders.smart_test_finder import smart_test_filter
from google.protobuf import json_format
from googleapiclient import http
from googleapiclient.discovery import build
import httplib2


_DEFAULT_MAX_TIMEOUT = 600
_STAGE_ID_FOR_SMART_TEST_SELECTION = 'local_smart_test_selection'
_STAGE_NAME_FOR_SMART_TEST_SELECTION = (
    f'{_STAGE_ID_FOR_SMART_TEST_SELECTION}_stage'
)
_DISCOVERY_SERVICE_URL = (
    'https://decisiongraph-pa.googleapis.com/$discovery/rest?version=v1'
)
_STAGE_NODE = decision_graph_pb2.StageNode(
    stage=decision_graph_pb2.Stage(
        id=_STAGE_ID_FOR_SMART_TEST_SELECTION,
        name=_STAGE_NAME_FOR_SMART_TEST_SELECTION,
    ),
    execution_options=decision_graph_pb2.StageNode.ExecutionOptions(
        location=1,
        address='blade:moneyball-test-relevance-prod',
        prepare=False,
        max_duration=common_pb2.Duration(seconds=_DEFAULT_MAX_TIMEOUT),
        blocking=1,
    ),
)


def _get_decision_graph_checks(
    tests: List[atp_test_selector.AtpTestInfo],
) -> List[decision_graph_pb2.Check]:
  """Get decision graph checks including selected test infos."""
  checks = []
  for test in tests:
    check = decision_graph_pb2.Check(
        identifier=decision_graph_pb2.Check.Identifier(
            id=str(uuid.uuid4()),
            ants_test=decision_graph_pb2.AnTSTest(
                build_descriptor=decision_graph_pb2.BuildDescriptor(
                    branch=test.branch, build_target=test.target
                ),
                test_definition=decision_graph_pb2.TestDefinition(
                    name=test.name
                ),
            ),
        )
    )
    checks.append(check)
  return checks


def _get_private_context(
    change_info: local_info_collector.ChangeInfo,
) -> decision_graph_pb2.Stage.PrivateContext:
  """Get private context containing local change info."""
  private_context = decision_graph_pb2.Stage.PrivateContext(
      changes=[
          decision_graph_pb2.Change(
              host=change_info.remote_hostname,
              project=change_info.project,
              branch=change_info.branch,
              owner=decision_graph_pb2.User(
                  account_id=1, name=change_info.user_key
              ),
          )
      ]
  )

  revisions = []
  for file in change_info.changed_files:
    revision = decision_graph_pb2.Revision(
        file_info=[
            decision_graph_pb2.FileInfo(
                path=file.filename,
                lines_inserted=file.number_of_lines_inserted,
                lines_deleted=file.number_of_lines_deleted,
            )
        ]
    )
    revisions.append(revision)
  private_context.changes[0].revisions.extend(revisions)

  return private_context


def create_query(
    change_info: local_info_collector.ChangeInfo,
    tests: List[atp_test_selector.AtpTestInfo],
):
  """Create a query for the relevance score between selected tests and local change info."""
  dg_input = decision_graph_pb2.DecisionGraphInput(
      input=[
          decision_graph_pb2.StageInput(
              stage=decision_graph_pb2.Stage(
                  id=_STAGE_ID_FOR_SMART_TEST_SELECTION,
                  name=_STAGE_NAME_FOR_SMART_TEST_SELECTION,
              ),
              input=[
                  decision_graph_pb2.StageOutput(
                      checks=_get_decision_graph_checks(tests),
                      private_context=_get_private_context(change_info),
                  )
              ],
          )
      ]
  )
  dg_input.graph.name = 'smart_test_selection_graph'
  dg_input.graph.stages.extend([_STAGE_NODE])

  json_query = json_format.MessageToJson(dg_input)
  return json_query


# TODO(b/410945183): Remove this function once the bug is fixed.
def create_queries(
    change_info: local_info_collector.ChangeInfo,
    tests: List[atp_test_selector.AtpTestInfo],
) -> List[str]:
  """Create queries for the relevance score between selected tests and local change info."""
  dg_checks = _get_decision_graph_checks(tests)
  queries = []

  for dg_check in dg_checks:
    dg_input = decision_graph_pb2.DecisionGraphInput(
        input=[
            decision_graph_pb2.StageInput(
                stage=decision_graph_pb2.Stage(
                    id=_STAGE_ID_FOR_SMART_TEST_SELECTION,
                    name=_STAGE_NAME_FOR_SMART_TEST_SELECTION,
                ),
                input=[
                    decision_graph_pb2.StageOutput(
                        checks=[dg_check],
                        private_context=_get_private_context(change_info),
                    )
                ],
            )
        ]
    )
    dg_input.graph.name = 'smart_test_selection_graph'
    dg_input.graph.stages.extend([_STAGE_NODE])
    queries.append(json_format.MessageToJson(dg_input))

  return queries


class TestRelevanceClient:
  """The client to calculate test relevance scores."""

  def __init__(self, max_retry_count=5):
    """Init BuildClient class."""
    self._max_retry_count = max_retry_count
    try:
      with open(atp_test_selector._get_constants_path(), 'r') as file:
        data = json.load(file)
        developer_key = data['developer_key']
        http = httplib2.Http(timeout=_DEFAULT_MAX_TIMEOUT)
        self.client = build(
            serviceName='decisiongraph-pa',
            version='v1',
            cache_discovery=False,
            discoveryServiceUrl=_DISCOVERY_SERVICE_URL,
            http=http,
            developerKey=developer_key,
        )
    except Exception as err:
      atest_utils.print_and_log_error(
          'Error occurred during smart test selection: %s', err
      )

  # def get_tests_with_relevance_score(
  #     self,
  #     change_info: local_info_collector.ChangeInfo,
  #     atp_tests: List[atp_test_selector.AtpTestInfo],
  # ) -> Dict[str, Any]:
  #   """Get test classes with relevance scores."""
  #   query = create_query(change_info, atp_tests)
  #   logging.info(query)
  #   return self.client.v1().rundecisiongraph(body=json.loads(query)).execute()

  # TODO(b/410945183): Replace this function with the one above once the bug is fixed.
  def get_tests_with_relevance_score_query_by_query(
      self,
      change_info: local_info_collector.ChangeInfo,
      atp_tests: List[atp_test_selector.AtpTestInfo],
  ) -> List[Dict[str, Any]]:
    """Get test classes with relevance scores query by query."""
    for try_id in range(self._max_retry_count + 1):
      try:
        dg_outputs = []
        for query in create_queries(change_info, atp_tests):
          logging.info(query)
          dg_outputs.append(
              self.client.v1()
              .rundecisiongraph(body=json.loads(query))
              .execute()
          )
        return dg_outputs
      except Exception as err:
        if try_id < self._max_retry_count:
          seconds_to_be_waited = 2**try_id
          atest_utils.print_and_log_warning(
              'Error occurred when querying test relevance API: %s, will retry'
              ' after %s seconds',
              err,
              seconds_to_be_waited,
          )
          time.sleep(seconds_to_be_waited)
        else:
          atest_utils.print_and_log_warning(
              'Error occurred when querying test relevance API: %s',
              err,
          )
          return []


def get_test_class_infos_from_decision_graph_output(
    dg_output: Dict[str, Any],
) -> List[smart_test_filter.TestClassInfo]:
  """Convert decision graph output to test class infos."""
  if not dg_output:
    return []

  test_classes = []
  for stage_output in dg_output.get('outputs', []):
    for check in stage_output.get('checks', []):
      check_identifier = check.get('identifier')
      if not check_identifier:
        continue
      ants_test = check_identifier.get('antsTest')
      if not ants_test:
        continue
      test_id = ants_test.get('testIdentifierId')
      if not test_id:
        continue

      test_identifier = ants_test.get('testIdentifier')
      if not test_identifier:
        continue
      module = test_identifier.get('module', '')
      test_class = test_identifier.get('testClass', '')
      score = check.get('reason', {}).get('relevanceScore', 0)
      test_classes.append(
          smart_test_filter.TestClassInfo(
              test_id=test_id,
              module=module,
              test_class=test_class,
              score=score,
          )
      )
  return test_classes
