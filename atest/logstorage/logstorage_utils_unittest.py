# Copyright (C) 2024 The Android Open Source Project
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

from unittest.mock import patch
from atest import constants
from atest.logstorage import logstorage_utils
from pyfakefs import fake_filesystem_unittest


class LogstorageUtilsTest(fake_filesystem_unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.setUpPyfakefs()

  @patch('atest.constants.GTF_TARGETS', {'google-tradefed'})
  @patch('atest.constants.CREDENTIAL_FILE_NAME', 'creds.txt')
  @patch('atest.constants.TOKEN_FILE_PATH', 'token.txt')
  def test_is_upload_enabled_request_upload_returns_True(self):
    res = logstorage_utils.is_upload_enabled(self._get_request_upload_args())

    self.assertTrue(res)

  @patch('atest.constants.GTF_TARGETS', {'google-tradefed'})
  @patch('atest.constants.CREDENTIAL_FILE_NAME', 'creds.txt')
  @patch('atest.constants.TOKEN_FILE_PATH', 'token.txt')
  def test_is_upload_enabled_disable_upload_returns_False(self):
    res = logstorage_utils.is_upload_enabled(self._get_disable_upload_args())

    self.assertFalse(res)

  @patch('atest.constants.GTF_TARGETS', {'google-tradefed'})
  @patch('atest.constants.CREDENTIAL_FILE_NAME', None)
  @patch('atest.constants.TOKEN_FILE_PATH', None)
  def test_is_upload_enabled_missing_credentials_returns_False(self):
    res = logstorage_utils.is_upload_enabled(self._get_request_upload_args())

    self.assertFalse(res)

  @patch('atest.constants.GTF_TARGETS', {})
  @patch('atest.constants.CREDENTIAL_FILE_NAME', 'creds.txt')
  @patch('atest.constants.TOKEN_FILE_PATH', 'token.txt')
  def test_is_upload_enabled_missing_google_tradefed_returns_False(self):
    res = logstorage_utils.is_upload_enabled(self._get_request_upload_args())

    self.assertFalse(res)

  @patch('atest.constants.GTF_TARGETS', {'google-tradefed'})
  @patch('atest.constants.CREDENTIAL_FILE_NAME', 'creds.txt')
  @patch('atest.constants.TOKEN_FILE_PATH', 'token.txt')
  def test_is_upload_enabled_previously_requested_returns_True(self):
    logstorage_utils.is_upload_enabled(self._get_request_upload_args())

    res = logstorage_utils.is_upload_enabled(
        self._get_unspecified_upload_args()
    )

    self.assertTrue(res)

  @patch('atest.constants.GTF_TARGETS', {'google-tradefed'})
  @patch('atest.constants.CREDENTIAL_FILE_NAME', 'creds.txt')
  @patch('atest.constants.TOKEN_FILE_PATH', 'token.txt')
  def test_is_upload_enabled_previously_disabled_returns_False(self):
    logstorage_utils.is_upload_enabled(self._get_request_upload_args())
    logstorage_utils.is_upload_enabled(self._get_disable_upload_args())

    res = logstorage_utils.is_upload_enabled(
        self._get_unspecified_upload_args()
    )

    self.assertFalse(res)

  @patch('atest.constants.GTF_TARGETS', {'google-tradefed'})
  @patch('atest.constants.CREDENTIAL_FILE_NAME', 'creds.txt')
  @patch('atest.constants.TOKEN_FILE_PATH', 'token.txt')
  def test_is_upload_enabled_never_requested_returns_False(self):
    res = logstorage_utils.is_upload_enabled(
        self._get_unspecified_upload_args()
    )

    self.assertFalse(res)

  def _get_unspecified_upload_args(self):
    """Returns arg dict with no upload flag."""
    return {}

  def _get_disable_upload_args(self):
    """Returns arg dict with disable upload flag."""
    return {constants.DISABLE_UPLOAD_RESULT: True}

  def _get_request_upload_args(self):
    """Returns arg dict with request upload flag."""
    return {constants.REQUEST_UPLOAD_RESULT: True}
