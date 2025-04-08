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
from atest.test_finders.smart_test_finder import atp_test_selector
from atest.test_finders.smart_test_finder import local_info_collector
from atest.test_finders.smart_test_finder import test_relevance_client
import googleapiclient
import httplib2
from pyfakefs import fake_filesystem_unittest


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


# pylint: disable=protected-access
class TestRelevanceClientUnittests(unittest.TestCase):
  """Unit tests for test_relevance_client.py."""

  @mock.patch('uuid.uuid4', side_effect=['001-002-003', '002-003-004'])
  def test_create_query(self, _):
    self.maxDiff = None
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


if __name__ == '__main__':
  unittest.main()
