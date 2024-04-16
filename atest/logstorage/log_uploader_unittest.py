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

import os
import pathlib
import unittest
from unittest.mock import patch
from atest import constants
from atest.logstorage import log_uploader
from pyfakefs import fake_filesystem_unittest


class LogUploaderModuleTest(unittest.TestCase):

  def setUp(self):
    super().setUp()
    self._set_upload_constants_available(False)
    self._set_upload_env_var(None)

  @patch('multiprocessing.Process.__new__')
  def test_upload_logs_detached_flag_value_unrecognized_process_not_started(
      self, mock_process
  ):
    self._set_upload_constants_available(True)
    self._set_upload_env_var('0')

    log_uploader.upload_logs_detached(pathlib.Path('any'))

    mock_process.assert_not_called()

  @patch('multiprocessing.Process.__new__')
  def test_upload_logs_detached_flag_value_1_process_started(
      self, mock_process
  ):
    self._set_upload_constants_available(True)
    self._set_upload_env_var('1')

    log_uploader.upload_logs_detached(pathlib.Path('any'))

    mock_process.assert_called_once()

  @patch('multiprocessing.Process.__new__')
  def test_upload_logs_detached_flag_value_capitalized_true_process_started(
      self, mock_process
  ):
    self._set_upload_constants_available(True)
    self._set_upload_env_var('TRUE')

    log_uploader.upload_logs_detached(pathlib.Path('any'))

    mock_process.assert_called_once()

  @patch('multiprocessing.Process.__new__')
  def test_upload_logs_detached_flag_value_true_process_started(
      self, mock_process
  ):
    self._set_upload_constants_available(True)
    self._set_upload_env_var('true')

    log_uploader.upload_logs_detached(pathlib.Path('any'))

    mock_process.assert_called_once()

  @patch('multiprocessing.Process.__new__')
  def test_upload_logs_detached_no_creds_process_not_started(
      self, mock_process
  ):
    self._set_upload_constants_available(False)
    self._set_upload_env_var('true')

    log_uploader.upload_logs_detached(pathlib.Path('any'))

    mock_process.assert_not_called()

  @patch('multiprocessing.Process.__new__')
  def test_upload_logs_detached_not_requested_process_not_started(
      self, mock_process
  ):
    self._set_upload_constants_available(True)
    self._set_upload_env_var(None)

    log_uploader.upload_logs_detached(pathlib.Path('any'))

    mock_process.assert_not_called()

  def _set_upload_env_var(self, value) -> None:
    """Set upload environment variable."""
    if value is None:
      os.environ.pop(log_uploader._ENABLE_ATEST_LOG_UPLOADING_ENV_KEY, None)
    else:
      os.environ[log_uploader._ENABLE_ATEST_LOG_UPLOADING_ENV_KEY] = value

  def _set_upload_constants_available(self, enabled: bool) -> None:
    """Make the upload constants available."""
    constants.CREDENTIAL_FILE_NAME = 'creds.txt' if enabled else None
    constants.TOKEN_FILE_PATH = 'token.txt' if enabled else None


class LogUploaderTest(fake_filesystem_unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.setUpPyfakefs()

  def test_upload_single_file_contains_name(self):
    file_path = pathlib.Path('/dir/some_name.log')
    self.fs.create_file(file_path)
    fake_client = self._FakeUploadingClient()

    log_uploader._LogUploadSession(fake_client).upload_single_file(file_path)

    self.assertEqual(
        fake_client.get_received_upload_artifact_arguments()[0]['resource_id'],
        file_path.name,
    )

  def test_upload_single_file_metadata_content_type(self):
    file_path = pathlib.Path('/dir/some_name.log')
    self.fs.create_file(file_path)
    fake_client = self._FakeUploadingClient()

    log_uploader._LogUploadSession(fake_client).upload_single_file(file_path)

    self.assertEqual(
        fake_client.get_received_upload_artifact_arguments()[0]['metadata'][
            'artifactType'
        ],
        'HOST_LOG',
    )

  def test_create_artifact_metadata_use_file_name(self):
    file_path = pathlib.Path('/dir/some_name.log')
    self.fs.create_file(file_path)
    fake_client = self._FakeUploadingClient()

    log_uploader._LogUploadSession(fake_client).upload_single_file(file_path)

    self.assertEqual(
        fake_client.get_received_upload_artifact_arguments()[0]['metadata'][
            'name'
        ],
        file_path.name,
    )

  def test_upload_single_file_duplicate_names_unique_resource_id(self):
    dir_path = pathlib.Path('/test_dir')
    file_name = 'some_name.log'
    file_path1 = dir_path.joinpath(file_name)
    file_path2 = dir_path.joinpath('some_sub_dir').joinpath(file_name)
    self.fs.create_file(file_path1)
    self.fs.create_file(file_path2)
    fake_client = self._FakeUploadingClient()
    suj = log_uploader._LogUploadSession(fake_client)

    suj.upload_single_file(file_path1)
    suj.upload_single_file(file_path2)

    self.assertNotEqual(
        fake_client.get_received_upload_artifact_arguments()[0]['resource_id'],
        fake_client.get_received_upload_artifact_arguments()[1]['resource_id'],
    )

  def test_upload_single_file_duplicate_names_preserve_stem_and_suffix(self):
    dir_path = pathlib.Path('/test_dir')
    file_name = 'filename.extension'
    file_path1 = dir_path.joinpath(file_name)
    file_path2 = dir_path.joinpath('some_sub_dir').joinpath(file_name)
    self.fs.create_file(file_path1)
    self.fs.create_file(file_path2)
    fake_client = self._FakeUploadingClient()
    suj = log_uploader._LogUploadSession(fake_client)
    suj.upload_single_file(file_path1)

    suj.upload_single_file(file_path2)

    self.assertRegex(
        fake_client.get_received_upload_artifact_arguments()[1]['resource_id'],
        r'^filename.+\.extension',
    )

  def test_upload_directory_does_not_upload_empty_directory(self):
    empty_dir = pathlib.Path('/test_dir')
    self.fs.create_dir(empty_dir)
    fake_client = self._FakeUploadingClient()

    log_uploader._LogUploadSession(fake_client).upload_directory(empty_dir)

    self.assertEqual(
        len(fake_client.get_received_upload_artifact_arguments()), 0
    )

  def test_get_file_paths_single_file(self):
    dir_path = pathlib.Path('/test_dir')
    file_path = dir_path.joinpath('file.txt')
    self.fs.create_file(file_path)
    fake_client = self._FakeUploadingClient()

    log_uploader._LogUploadSession(fake_client).upload_directory(dir_path)

    self.assertEqual(
        len(fake_client.get_received_upload_artifact_arguments()), 1
    )

  def test_get_file_paths_multiple_files(self):
    dir_path = pathlib.Path('/test_dir')
    file_path1 = dir_path.joinpath('file1.txt')
    file_path2 = dir_path.joinpath('file2.txt')
    self.fs.create_file(file_path1)
    self.fs.create_file(file_path2)
    fake_client = self._FakeUploadingClient()

    log_uploader._LogUploadSession(fake_client).upload_directory(dir_path)

    self.assertEqual(
        len(fake_client.get_received_upload_artifact_arguments()), 2
    )

  def test_get_file_paths_nested_directories(self):
    dir_path = pathlib.Path('/test_dir')
    file_path = dir_path.joinpath('test_dir2/file2.txt')
    self.fs.create_file(file_path)
    fake_client = self._FakeUploadingClient()

    log_uploader._LogUploadSession(fake_client).upload_directory(dir_path)

    self.assertEqual(
        fake_client.get_received_upload_artifact_arguments()[0][
            'artifact_path'
        ],
        file_path,
    )

  def test_get_file_paths_symbolic_link_file(self):
    dir_path = pathlib.Path('/test_dir')
    link_path = dir_path.joinpath('link.txt')
    target_path = pathlib.Path('/test_dir2/file.txt')
    file_content = 'some content'
    self.fs.create_file(target_path, contents=file_content)
    self.fs.create_symlink(link_path, target_path)
    fake_client = self._FakeUploadingClient()

    log_uploader._LogUploadSession(fake_client).upload_directory(dir_path)

    self.assertEqual(
        fake_client.get_received_upload_artifact_arguments()[0][
            'artifact_path'
        ],
        link_path,
    )

  def test_get_file_paths_symbolic_link_directory(self):
    # Create a directory with a file and a symbolic link to it
    dir_path = pathlib.Path('/test_dir')
    link_path = dir_path.joinpath('link_dir')
    target_path = pathlib.Path('/test_dir2')
    file_name = 'file.txt'
    file_content = 'some content'
    self.fs.create_file(target_path.joinpath(file_name), contents=file_content)
    self.fs.create_symlink(link_path, target_path)
    fake_client = self._FakeUploadingClient()

    log_uploader._LogUploadSession(fake_client).upload_directory(dir_path)

    self.assertEqual(
        fake_client.get_received_upload_artifact_arguments()[0][
            'artifact_path'
        ],
        link_path.joinpath(file_name),
    )

  class _FakeUploadingClient(log_uploader._SimpleUploadingClient):

    def __init__(self):
      self._received_upload_artifact_arguments = []

    # TODO(yuexima): This is basically a mock, switch to use mock directly.
    def get_received_upload_artifact_arguments(self):
      return self._received_upload_artifact_arguments

    def upload_artifact(
        self,
        resource_id: str,
        metadata: dict[str, str],
        artifact_path: pathlib.Path,
        num_of_retries,
    ) -> None:
      self._received_upload_artifact_arguments.append({
          'resource_id': resource_id,
          'metadata': metadata,
          'artifact_path': artifact_path,
      })


if __name__ == '__main__':
  unittest.main()
