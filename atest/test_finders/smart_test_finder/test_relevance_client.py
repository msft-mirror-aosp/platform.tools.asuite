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
from typing import List
import uuid
from atest.proto import common_pb2
from atest.proto import decision_graph_pb2
from atest.test_finders.smart_test_finder import atp_test_selector
from atest.test_finders.smart_test_finder import local_info_collector
from google.protobuf import json_format


_DEFAULT_MAX_TIMEOUT = 600
_STAGE_ID_FOR_SMART_TEST_SELECTION = 'local_smart_test_selection'
_STAGE_NAME_FOR_SMART_TEST_SELECTION = (
    f'{_STAGE_ID_FOR_SMART_TEST_SELECTION}_stage'
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
