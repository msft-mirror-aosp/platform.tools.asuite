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


"""A module for background python log artifacts uploading."""

import argparse
from importlib import resources
import logging
import multiprocessing
import os
import pathlib
import subprocess
from atest import constants
from atest.logstorage import logstorage_utils

try:
  from googleapiclient import errors
  from googleapiclient import http
except ModuleNotFoundError as err:
  logging.debug('Import error due to: %s', err)


class _SimpleUploadingClient:
  """A proxy class used to interact with the logstorage_utils module."""

  def __init__(self):
    self._client = None
    self._client_legacy = None
    self._invocation_id = None
    self._workunit_id = None
    self._legacy_test_result_id = None
    self._invocation_data = None

  def initialize_invocation(self):
    """Initialize internal build clients and get invocation ID from AnTS."""
    configuration = {constants.REQUEST_UPLOAD_RESULT: True}
    creds, self._invocation_data = logstorage_utils.do_upload_flow(
        configuration
    )

    self._client = logstorage_utils.BuildClient(creds)
    # Legacy test result ID is required when using AnTS' `testartifact` API
    # to upload test artifacts due to a limitation in the API, and we need
    # The legacy client to get the legacy ID.
    self._client_legacy = logstorage_utils.BuildClient(
        creds,
        api_version=constants.STORAGE_API_VERSION_LEGACY,
        url=constants.DISCOVERY_SERVICE_LEGACY,
    )

    self._invocation_id = configuration[constants.INVOCATION_ID]
    self._workunit_id = configuration[constants.WORKUNIT_ID]

    self._legacy_test_result_id = (
        self._client_legacy.client.testresult()
        .insert(
            buildId=self._invocation_data['primaryBuild']['buildId'],
            target=self._invocation_data['primaryBuild']['buildTarget'],
            attemptId='latest',
            body={
                'status': 'completePass',
            },
        )
        .execute()['id']
    )

    logging.debug(
        'Initialized AnTS invocation: http://ab/%s', self._invocation_id
    )

  def complete_invocation(self) -> None:
    """Set schedule state as complete to AnTS for the current invocation."""
    self._invocation_data['schedulerState'] = 'completed'
    self._client.update_invocation(self._invocation_data)
    logging.debug(
        'Finalized AnTS invocation: http://ab/%s', self._invocation_id
    )

  def upload_artifact(
      self,
      resource_id: str,
      metadata: dict[str, str],
      artifact_path: pathlib.Path,
      num_of_retries,
  ) -> None:
    """Upload an artifact to AnTS with retries.

    Args:
        resource_id: The artifact's destination resource ID
        metadata: The metadata for the artifact. Invocation ID and work unit ID
          is not required in the input metadata dict as this method will add the
          values to it.
        artifact_path: The path of the artifact file
        num_of_retries: Number of retries when the upload request failed

    Raises:
        errors.HttpError: When the upload failed.
    """
    metadata['invocationId'] = self._invocation_id
    metadata['workUnitId'] = self._workunit_id

    # TODO: make resourceId unique.
    self._client.client.testartifact().update(
        resourceId=resource_id,
        invocationId=self._invocation_id,
        workUnitId=self._workunit_id,
        body=metadata,
        legacyTestResultId=self._legacy_test_result_id,
        media_body=http.MediaFileUpload(artifact_path),
    ).execute(num_retries=num_of_retries)


class _LogUploadSession:
  """A class to handle log uploading to AnTS."""

  def __init__(self, upload_client: _SimpleUploadingClient = None):
    self._upload_client = upload_client or _SimpleUploadingClient()

  def __enter__(self):
    self._upload_client.initialize_invocation()
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    self._upload_client.complete_invocation()

  @classmethod
  def _get_file_paths(cls, directory: pathlib.Path) -> list[pathlib.Path]:
    """Returns all the files under the given directory following symbolic links.

    Args:
        directory: The root directory path.

    Returns:
        A list of pathlib.Path objects representing the file paths.
    """

    file_paths = []
    with os.scandir(directory) as scan:
      for entry in scan:
        if entry.is_file():
          file_paths.append(pathlib.Path(entry.path))
        elif entry.is_dir():
          file_paths.extend(cls._get_file_paths(entry))

    return file_paths

  @staticmethod
  def _create_artifact_metadata(artifact_path: pathlib.Path) -> dict[str, str]:
    metadata = {
        'name': artifact_path.name,
    }
    if artifact_path.suffix in ['.txt', '.log']:
      metadata['artifactType'] = 'HOST_LOG'
      metadata['contentType'] = 'text/plain'
    return metadata

  def upload_directory(self, artifacts_dir: pathlib.Path) -> None:
    """Upload all artifacts under a directory."""
    logging.debug('Uploading artifact directory %s', artifacts_dir)
    for artifact_path in self._get_file_paths(artifacts_dir):
      self.upload_single_file(artifact_path)

  def upload_single_file(self, artifact_path: pathlib.Path) -> None:
    """Upload an single artifact."""
    logging.debug('Uploading artifact path %s', artifact_path)
    file_upload_retires = 3
    try:
      self._upload_client.upload_artifact(
          artifact_path.name,
          self._create_artifact_metadata(artifact_path),
          artifact_path,
          file_upload_retires,
      )
    except errors.HttpError as e:
      # Upload error may happen due to temporary network issue. We log down
      # an error but do stop the upload loop so that other files may gets
      # uploaded when the network recover.
      logging.error('Failed to upload file %s with error: %s', artifact_path, e)


def upload_logs_detached(logs_dir: pathlib.Path):
  """Upload logs to AnTS in a detached process."""
  if not os.environ.get('ENABLE_ATEST_LOG_UPLOADING', False):
    return

  assert logs_dir, 'artifacts_dir cannot be None.'
  assert logs_dir.as_posix(), 'The path of artifacts_dir should not be empty.'

  def _start_upload():
    # We need to fock a background process instead of calling Popen with
    # start_new_session=True because we want to make sure the atest_log_uploader
    # resource binary is deleted after execution.
    if os.fork() != 0:
      return
    with resources.as_file(
        resources.files('atest').joinpath('atest_log_uploader')
    ) as uploader_path:
      # TODO: Explore whether it's possible to package the binary with
      # executable permission.
      os.chmod(uploader_path, 0o755)

      timeout = 60 * 60 * 24  # 1 day
      # We need to call atest_log_uploader as a binary so that the python
      # environment can be properly loaded.
      subprocess.check_call(
          [uploader_path.as_posix(), logs_dir.as_posix()], timeout=timeout
      )

  proc = multiprocessing.Process(target=_start_upload)
  proc.start()
  proc.join()


if __name__ == '__main__':
  arg_parser = argparse.ArgumentParser(
      description='Internal tool for uploading test artifacts to AnTS.',
      add_help=True,
  )
  arg_parser.add_argument(
      'artifacts_dir', help='Root directory of the test artifacts.'
  )
  args = arg_parser.parse_args()
  with _LogUploadSession() as artifact_upload_session:
    artifact_upload_session.upload_directory(pathlib.Path(args.artifacts_dir))
