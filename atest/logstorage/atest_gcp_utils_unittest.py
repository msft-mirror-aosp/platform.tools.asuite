#!/usr/bin/env python3
#
# Copyright 2021, The Android Open Source Project
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

"""Unittests for atest_gcp_utils."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from atest import constants
from atest.logstorage import atest_gcp_utils


class AtestGcpUtilsUnittests(unittest.TestCase):
  """Unit tests for atest_gcp_utils.py"""

  @mock.patch.object(atest_gcp_utils, '_prepare_data')
  @mock.patch.object(atest_gcp_utils, 'fetch_credential')
  def test_do_upload_flow(self, mock_request, mock_prepare):
    """test do_upload_flow method."""
    fake_extra_args = {}
    fake_creds = mock.Mock()
    fake_creds.token_response = {'access_token': 'fake_token'}
    mock_request.return_value = fake_creds
    fake_inv = {'invocationId': 'inv_id'}
    fake_workunit = {'id': 'workunit_id'}
    fake_local_build_id = 'L1234567'
    fake_build_target = 'build_target'
    mock_prepare.return_value = (
        fake_inv,
        fake_workunit,
        fake_local_build_id,
        fake_build_target,
    )
    fake_build_client_creator = lambda cred: None
    constants.TOKEN_FILE_PATH = tempfile.NamedTemporaryFile().name
    creds, inv = atest_gcp_utils.do_upload_flow(
        fake_extra_args, fake_build_client_creator
    )
    self.assertEqual(fake_creds, creds)
    self.assertEqual(fake_inv, inv)
    self.assertEqual(
        fake_extra_args[constants.INVOCATION_ID], fake_inv['invocationId']
    )
    self.assertEqual(
        fake_extra_args[constants.WORKUNIT_ID], fake_workunit['id']
    )
    self.assertEqual(
        fake_extra_args[constants.LOCAL_BUILD_ID], fake_local_build_id
    )
    self.assertEqual(fake_extra_args[constants.BUILD_TARGET], fake_build_target)

    mock_request.return_value = None
    creds, inv = atest_gcp_utils.do_upload_flow(
        fake_extra_args, fake_build_client_creator
    )
    self.assertEqual(None, creds)
    self.assertEqual(None, inv)
