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
#
"""Unittests for test_relevance_client."""

# pylint: disable=invalid-name

import json
import unittest
from unittest import mock
from atest import atest_utils
from atest.proto import decision_graph_pb2
from atest.test_finders.smart_test_finder import atp_test_selector
from atest.test_finders.smart_test_finder import local_info_collector
from atest.test_finders.smart_test_finder import smart_test_filter
from atest.test_finders.smart_test_finder import test_relevance_client
from google.protobuf import json_format


_FAKE_CHANGED_FILE_DETAILS = [
    atest_utils.ChangedFileDetails(
        filename='/a/b/c',
        number_of_lines_inserted=14,
        number_of_lines_deleted=25,
    ),
    atest_utils.ChangedFileDetails(
        filename='/d/e/f',
        number_of_lines_inserted=36,
        number_of_lines_deleted=47,
    ),
]
_EXPECTED_QUERY = """{
  "graph": {
    "name": "smart_test_selection_graph",
    "stages": [
      {
        "stage": {
          "id": "local_smart_test_selection",
          "name": "local_smart_test_selection_stage"
        },
        "executionOptions": {
          "location": "GSLB",
          "address": "blade:moneyball-test-relevance-prod",
          "prepare": false,
          "maxDuration": {
            "seconds": "600"
          },
          "blocking": "BLOCKING"
        }
      }
    ]
  },
  "input": [
    {
      "stage": {
        "id": "local_smart_test_selection",
        "name": "local_smart_test_selection_stage"
      },
      "input": [
        {
          "checks": [
            {
              "identifier": {
                "id": "001-002-003",
                "antsTest": {
                  "buildDescriptor": {
                    "branch": "some_aosp-branch2",
                    "buildTarget": "aosp_cf_x86_64_phone-trunk_staging-userdebug"
                  },
                  "testDefinition": {
                    "name": "v2/android-virtual-infra/test_mapping/presubmit-avd"
                  }
                }
              }
            },
            {
              "identifier": {
                "id": "002-003-004",
                "antsTest": {
                  "buildDescriptor": {
                    "branch": "some_aosp-branch2",
                    "buildTarget": "aosp_cf_x86_64_phone-trunk_staging-userdebug"
                  },
                  "testDefinition": {
                    "name": "v2/android-test-harness-team/tradefed/host_unit_tests_zip_validation"
                  }
                }
              }
            }
          ],
          "privateContext": {
            "changes": [
              {
                "host": "stuff-to-be-selected",
                "project": "fake_project",
                "branch": "fake_branch",
                "revisions": [
                  {
                    "fileInfo": [
                      {
                        "path": "/a/b/c",
                        "linesInserted": 14,
                        "linesDeleted": 25
                      }
                    ]
                  },
                  {
                    "fileInfo": [
                      {
                        "path": "/d/e/f",
                        "linesInserted": 36,
                        "linesDeleted": 47
                      }
                    ]
                  }
                ],
                "owner": {
                  "name": "fake_user",
                  "accountId": "1"
                }
              }
            ]
          }
        }
      ]
    }
  ]
}"""
_EXPECTED_QUERY_WITH_SINGLE_CHECK1 = """{
  "graph": {
    "name": "smart_test_selection_graph",
    "stages": [
      {
        "stage": {
          "id": "local_smart_test_selection",
          "name": "local_smart_test_selection_stage"
        },
        "executionOptions": {
          "location": "GSLB",
          "address": "blade:moneyball-test-relevance-prod",
          "prepare": false,
          "maxDuration": {
            "seconds": "600"
          },
          "blocking": "BLOCKING"
        }
      }
    ]
  },
  "input": [
    {
      "stage": {
        "id": "local_smart_test_selection",
        "name": "local_smart_test_selection_stage"
      },
      "input": [
        {
          "checks": [
            {
              "identifier": {
                "id": "001-002-003",
                "antsTest": {
                  "buildDescriptor": {
                    "branch": "some_aosp-branch2",
                    "buildTarget": "aosp_cf_x86_64_phone-trunk_staging-userdebug"
                  },
                  "testDefinition": {
                    "name": "v2/android-virtual-infra/test_mapping/presubmit-avd"
                  }
                }
              }
            }
          ],
          "privateContext": {
            "changes": [
              {
                "host": "stuff-to-be-selected",
                "project": "fake_project",
                "branch": "fake_branch",
                "revisions": [
                  {
                    "fileInfo": [
                      {
                        "path": "/a/b/c",
                        "linesInserted": 14,
                        "linesDeleted": 25
                      }
                    ]
                  },
                  {
                    "fileInfo": [
                      {
                        "path": "/d/e/f",
                        "linesInserted": 36,
                        "linesDeleted": 47
                      }
                    ]
                  }
                ],
                "owner": {
                  "name": "fake_user",
                  "accountId": "1"
                }
              }
            ]
          }
        }
      ]
    }
  ]
}"""
_EXPECTED_QUERY_WITH_SINGLE_CHECK2 = """{
  "graph": {
    "name": "smart_test_selection_graph",
    "stages": [
      {
        "stage": {
          "id": "local_smart_test_selection",
          "name": "local_smart_test_selection_stage"
        },
        "executionOptions": {
          "location": "GSLB",
          "address": "blade:moneyball-test-relevance-prod",
          "prepare": false,
          "maxDuration": {
            "seconds": "600"
          },
          "blocking": "BLOCKING"
        }
      }
    ]
  },
  "input": [
    {
      "stage": {
        "id": "local_smart_test_selection",
        "name": "local_smart_test_selection_stage"
      },
      "input": [
        {
          "checks": [
            {
              "identifier": {
                "id": "002-003-004",
                "antsTest": {
                  "buildDescriptor": {
                    "branch": "some_aosp-branch2",
                    "buildTarget": "aosp_cf_x86_64_phone-trunk_staging-userdebug"
                  },
                  "testDefinition": {
                    "name": "v2/android-test-harness-team/tradefed/host_unit_tests_zip_validation"
                  }
                }
              }
            }
          ],
          "privateContext": {
            "changes": [
              {
                "host": "stuff-to-be-selected",
                "project": "fake_project",
                "branch": "fake_branch",
                "revisions": [
                  {
                    "fileInfo": [
                      {
                        "path": "/a/b/c",
                        "linesInserted": 14,
                        "linesDeleted": 25
                      }
                    ]
                  },
                  {
                    "fileInfo": [
                      {
                        "path": "/d/e/f",
                        "linesInserted": 36,
                        "linesDeleted": 47
                      }
                    ]
                  }
                ],
                "owner": {
                  "name": "fake_user",
                  "accountId": "1"
                }
              }
            ]
          }
        }
      ]
    }
  ]
}"""


# pylint: disable=protected-access
class TestRelevanceClientUnittests(unittest.TestCase):
  """Unit tests for test_relevance_client.py."""

  @mock.patch('uuid.uuid4', side_effect=['001-002-003', '002-003-004'])
  def test_create_query(self, _):
    fake_change_info = local_info_collector.ChangeInfo(
        project='fake_project',
        branch='fake_branch',
        remote_hostname='stuff-to-be-selected',
        changed_files=_FAKE_CHANGED_FILE_DETAILS,
        user_key='fake_user',
    )
    fake_selected_tests = [
        atp_test_selector.AtpTestInfo(
            name='v2/android-virtual-infra/test_mapping/presubmit-avd',
            target='aosp_cf_x86_64_phone-trunk_staging-userdebug',
            branch='some_aosp-branch2',
        ),
        atp_test_selector.AtpTestInfo(
            name='v2/android-test-harness-team/tradefed/host_unit_tests_zip_validation',
            target='aosp_cf_x86_64_phone-trunk_staging-userdebug',
            branch='some_aosp-branch2',
        ),
    ]

    query = test_relevance_client.create_query(
        fake_change_info, fake_selected_tests
    )

    self.assertDictEqual(json.loads(query), json.loads(_EXPECTED_QUERY))

  @mock.patch('uuid.uuid4', side_effect=['001-002-003', '002-003-004'])
  def test_create_queries(self, _):
    fake_change_info = local_info_collector.ChangeInfo(
        project='fake_project',
        branch='fake_branch',
        remote_hostname='stuff-to-be-selected',
        changed_files=_FAKE_CHANGED_FILE_DETAILS,
        user_key='fake_user',
    )
    fake_selected_tests = [
        atp_test_selector.AtpTestInfo(
            name='v2/android-virtual-infra/test_mapping/presubmit-avd',
            target='aosp_cf_x86_64_phone-trunk_staging-userdebug',
            branch='some_aosp-branch2',
        ),
        atp_test_selector.AtpTestInfo(
            name='v2/android-test-harness-team/tradefed/host_unit_tests_zip_validation',
            target='aosp_cf_x86_64_phone-trunk_staging-userdebug',
            branch='some_aosp-branch2',
        ),
    ]

    queries = test_relevance_client.create_queries(
        fake_change_info, fake_selected_tests
    )

    self.assertDictEqual(
        json.loads(queries[0]), json.loads(_EXPECTED_QUERY_WITH_SINGLE_CHECK1)
    )
    self.assertDictEqual(
        json.loads(queries[1]), json.loads(_EXPECTED_QUERY_WITH_SINGLE_CHECK2)
    )

  def test_get_test_class_infos_from_decision_graph_output(self):
    ants_test_input = decision_graph_pb2.AnTSTest(
        aggregation_level=decision_graph_pb2.AggregationLevel.CLASS,
        build_descriptor=decision_graph_pb2.BuildDescriptor(
            branch='git_main',
            build_target='cf-x86-64-some-target',
        ),
        test_definition=decision_graph_pb2.TestDefinition(
            name='v2/some-atp-test/name',
        ),
    )
    check_input = decision_graph_pb2.Check(
        identifier=decision_graph_pb2.Check.Identifier(
            ants_test=ants_test_input,
        ),
    )
    ants_test_output1 = decision_graph_pb2.AnTSTest(
        test_identifier=decision_graph_pb2.TestIdentifier(
            module='TestAModule',
            test_class='AClassTest',
        ),
        test_identifier_id='id_1',
    )
    check_reason1 = decision_graph_pb2.Check.Reason(relevance_score=0.99)
    check_output1 = decision_graph_pb2.Check(
        identifier=decision_graph_pb2.Check.Identifier(
            ants_test=ants_test_output1,
        ),
        reason=check_reason1,
    )
    ants_test_output2 = decision_graph_pb2.AnTSTest(
        test_identifier=decision_graph_pb2.TestIdentifier(
            module='TestBModule',
            test_class='BClassTest',
            method='bMethod',
        ),
    )
    check_reason2 = decision_graph_pb2.Check.Reason(relevance_score=0.37)
    check_output2 = decision_graph_pb2.Check(
        identifier=decision_graph_pb2.Check.Identifier(
            ants_test=ants_test_output2,
        ),
        reason=check_reason2,
    )
    dg_outputs = [
        json_format.MessageToDict(
            decision_graph_pb2.DecisionGraphOutput(
                outputs=[
                    decision_graph_pb2.StageOutput(
                        checks=[check_input, check_output1, check_output2]
                    )
                ],
            )
        ),
    ]
    expected_test_class_infos = [
        smart_test_filter.TestClassInfo(
            test_id='id_1',
            module='TestAModule',
            test_class='AClassTest',
            score=0.99,
        ),
    ]

    test_class_infos = []
    for dg_output in dg_outputs:
      test_classes = (
          test_relevance_client.get_test_class_infos_from_decision_graph_output(
              dg_output
          )
      )
      test_class_infos.extend(test_classes)

    self.assertEqual(len(test_class_infos), len(expected_test_class_infos))
    for i in range(len(test_class_infos)):
      self.assertTestClassInfoAlmostEqual(
          test_class_infos[i],
          expected_test_class_infos[i],
          tolerance=1e-6,
      )

  def test_get_test_class_infos_from_decision_graph_output_no_test_returned(
      self,
  ):
    check_reason1 = decision_graph_pb2.Check.Reason(relevance_score=0.99)
    check1 = decision_graph_pb2.Check(
        identifier=decision_graph_pb2.Check.Identifier(
            id='id_1',
        ),
        reason=check_reason1,
    )
    check_reason2 = decision_graph_pb2.Check.Reason(relevance_score=0.37)
    check2 = decision_graph_pb2.Check(
        identifier=decision_graph_pb2.Check.Identifier(
            id='id_2',
        ),
        reason=check_reason2,
    )
    dg_output = json_format.MessageToDict(
        decision_graph_pb2.DecisionGraphOutput(
            outputs=[decision_graph_pb2.StageOutput(checks=[check1, check2])],
        )
    )

    test_class_infos = (
        test_relevance_client.get_test_class_infos_from_decision_graph_output(
            dg_output
        )
    )

    self.assertCountEqual(test_class_infos, [])

  def assertTestClassInfoAlmostEqual(self, info1, info2, tolerance):
    """Assert test class infos equal within tolerance.

    This function asserts the equality of two class infos. This indicates that
    the relevance scores are within the specified tolerance, while all other
    fields are equal.
    """
    self.assertAlmostEqual(info1.score, info2.score, delta=tolerance)

    info1_without_score = smart_test_filter.TestClassInfo(
        test_id=info1.test_id,
        atp_test_name=info1.atp_test_name,
        branch=info1.branch,
        target=info1.target,
        run_time=info1.run_time,
        pass_rate=info1.pass_rate,
        module=info1.module,
        test_class=info1.test_class,
        score=None,
    )
    info2_without_score = smart_test_filter.TestClassInfo(
        test_id=info2.test_id,
        atp_test_name=info2.atp_test_name,
        branch=info2.branch,
        target=info2.target,
        run_time=info2.run_time,
        pass_rate=info2.pass_rate,
        module=info2.module,
        test_class=info2.test_class,
        score=None,
    )

    self.assertEqual(info1_without_score, info2_without_score)


if __name__ == '__main__':
  unittest.main()
