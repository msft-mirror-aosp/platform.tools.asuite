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

"""Unittests for local_info_collector."""

# pylint: disable=invalid-name

import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock
from atest import atest_utils
from atest.test_finders.smart_test_finder import local_info_collector
from pyfakefs import fake_filesystem_unittest


_REPO_INFO_OUTPUT = b"""Manifest branch: fake_branch
Manifest merge branch: fake_merge_branch
----------------------------
Project: fake_project
"""

_MANIFEST_XML_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
    <manifest>
      <remote  name="remote_symbol"
               fetch=".."
               review="sso://stuff-to-be-selected/" />
      <default revision="main"
               remote="remote_symbol"
               sync-j="32"
        />
      <remote  name="not_selected_remote_symbol" fetch=".." review="sso://not-selected-stuff/" />
    </manifest>
"""


_FAKE_CHANGED_FILE_DETAILS = frozenset([
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
])


# pylint: disable=protected-access
class LocalInfoCollectorFileSystemUnittests(fake_filesystem_unittest.TestCase):
  """Unit tests for local_info_collector.py with file access."""

  def setUp(self):
    super().setUp()
    self.setUpPyfakefs()
    self.mock_getuser = self.enterContext(
        mock.patch('getpass.getuser', return_value='fake_user')
    )
    self.mock_get_modified_files_with_details = self.enterContext(
        mock.patch.object(
            atest_utils,
            'get_modified_files_with_details',
            return_value=_FAKE_CHANGED_FILE_DETAILS,
        )
    )

  @mock.patch('subprocess.check_output', return_value=_REPO_INFO_OUTPUT)
  def test_get_local_change_info(self, _):
    fake_temp_file_name = next(tempfile._get_candidate_names())
    self.fs.create_file(
        fake_temp_file_name,
        contents=_MANIFEST_XML_CONTENT,
    )

    with mock.patch.object(
        atest_utils,
        'get_build_top',
        return_value=pathlib.Path(fake_temp_file_name),
    ):
      expected_change_info = local_info_collector.ChangeInfo(
          project='fake_project',
          branch='fake_branch',
          remote_hostname='stuff-to-be-selected',
          changed_files=_FAKE_CHANGED_FILE_DETAILS,
          user_key='fake_user',
      )

      change_info = local_info_collector.get_local_change_info()

      self.assertEqual(change_info, expected_change_info)

  @mock.patch(
      'subprocess.check_output',
      side_effect=subprocess.CalledProcessError(
          returncode=1, cmd='repo info .'
      ),
  )
  def test_get_local_change_info_failed_to_get_repo_info(self, _):
    fake_temp_file_name = next(tempfile._get_candidate_names())
    self.fs.create_file(
        fake_temp_file_name,
        contents=_MANIFEST_XML_CONTENT,
    )

    with mock.patch.object(
        atest_utils,
        'get_build_top',
        return_value=pathlib.Path(fake_temp_file_name),
    ):
      expected_change_info = local_info_collector.ChangeInfo(
          project='',
          branch='',
          remote_hostname='stuff-to-be-selected',
          changed_files=_FAKE_CHANGED_FILE_DETAILS,
          user_key='fake_user',
      )

      change_info = local_info_collector.get_local_change_info()

      self.assertEqual(change_info, expected_change_info)

  @mock.patch('subprocess.check_output', return_value=_REPO_INFO_OUTPUT)
  def test_get_local_change_info_failed_to_get_remote_hostname(self, _):
    fake_temp_file_name = next(tempfile._get_candidate_names())

    with mock.patch.object(
        atest_utils,
        'get_build_top',
        return_value=pathlib.Path(fake_temp_file_name),
    ):
      expected_change_info = local_info_collector.ChangeInfo(
          project='fake_project',
          branch='fake_branch',
          remote_hostname='',
          changed_files=_FAKE_CHANGED_FILE_DETAILS,
          user_key='fake_user',
      )

      change_info = local_info_collector.get_local_change_info()

      self.assertEqual(change_info, expected_change_info)


if __name__ == '__main__':
  unittest.main()
