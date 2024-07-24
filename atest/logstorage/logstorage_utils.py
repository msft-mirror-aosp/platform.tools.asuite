# Copyright (C) 2020 The Android Open Source Project
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


"""Utility functions for logstorage."""
from __future__ import print_function

import logging
import time
import uuid

from atest import atest_utils
from atest import constants
from atest.logstorage import atest_gcp_utils
from atest.metrics import metrics_base
from googleapiclient.discovery import build
import httplib2
from oauth2client import client as oauth2_client

UPLOAD_REQUESTED_FILE_NAME = 'UPLOAD_REQUESTED'


def is_credential_available() -> bool:
  """Checks whether the credential needed for log upload is available."""
  return constants.CREDENTIAL_FILE_NAME and constants.TOKEN_FILE_PATH


def is_upload_enabled(args: dict[str, str]) -> bool:
  """Determines whether log upload is enabled."""
  if not is_credential_available() or not constants.GTF_TARGETS:
    return False

  config_folder_path = atest_utils.get_config_folder()
  config_folder_path.mkdir(parents=True, exist_ok=True)
  upload_requested_file = config_folder_path.joinpath(
      UPLOAD_REQUESTED_FILE_NAME
  )

  is_request_upload = args.get(constants.REQUEST_UPLOAD_RESULT)
  is_disable_upload = args.get(constants.DISABLE_UPLOAD_RESULT)
  is_previously_requested = upload_requested_file.exists()

  # Note: is_request_upload and is_disable_upload are from mutually exclusive
  # args so they won't be True simutaniously.
  if not is_disable_upload and is_previously_requested:  # Previously enabled
    atest_utils.colorful_print(
        'AnTS result uploading is enabled. (To disable, use'
        ' --disable-upload-result flag)',
        constants.GREEN,
    )
    return True

  if is_request_upload and not is_previously_requested:  # First time enable
    atest_utils.colorful_print(
        'AnTS result uploading is switched on and will apply to the current and'
        ' future TradeFed test runs. To disable it, run a test with the'
        ' --disable-upload-result flag.',
        constants.GREEN,
    )
    upload_requested_file.touch()
    return True

  if is_disable_upload and is_previously_requested:  # First time disable
    atest_utils.colorful_print(
        'AnTS result uploading is switched off and will apply to the current'
        ' and future TradeFed test runs. To re-enable it, run a test with the'
        ' --request-upload-result flag.',
        constants.GREEN,
    )
    upload_requested_file.unlink()
    config_folder_path.joinpath(constants.CREDENTIAL_FILE_NAME).unlink(
        missing_ok=True
    )
    return False

  return False


def do_upload_flow(
    extra_args: dict[str, str], atest_run_id: str = None
) -> tuple:
  """Run upload flow.

  Asking user's decision and do the related steps.

  Args:
      extra_args: Dict of extra args to add to test run.
      atest_run_id: The atest run ID to write into the invocation.

  Return:
      A tuple of credential object and invocation information dict.
  """
  return atest_gcp_utils.do_upload_flow(
      extra_args, lambda cred: BuildClient(cred), atest_run_id
  )


class BuildClient:
  """Build api helper class."""

  def __init__(
      self,
      creds,
      api_version=constants.STORAGE_API_VERSION,
      url=constants.DISCOVERY_SERVICE,
  ):
    """Init BuildClient class.

    Args:
        creds: An oauth2client.OAuth2Credentials instance.
    """
    http_auth = creds.authorize(httplib2.Http())
    self.client = build(
        serviceName=constants.STORAGE_SERVICE_NAME,
        version=api_version,
        cache_discovery=False,
        http=http_auth,
        discoveryServiceUrl=url,
    )

  def list_branch(self):
    """List all branch."""
    return self.client.branch().list(maxResults=10000).execute()

  def list_target(self, branch):
    """List all target in the branch."""
    return self.client.target().list(branch=branch, maxResults=10000).execute()

  def get_branch(self, branch):
    """Get BuildInfo for specific branch.

    Args:
        branch: A string of branch name to query.
    """
    query_branch = ''
    try:
      query_branch = self.client.branch().get(resourceId=branch).execute()
    # pylint: disable=broad-except
    except Exception:
      return ''
    return query_branch

  def insert_local_build(self, external_id, target, branch):
    """Insert a build record.

    Args:
        external_id: unique id of build record.
        target: build target.
        branch: build branch.

    Returns:
        A build record object.
    """
    body = {
        'buildId': '',
        'externalId': external_id,
        'branch': branch,
        'target': {'name': target, 'target': target},
        'buildAttemptStatus': 'complete',
    }
    return self.client.build().insert(buildType='local', body=body).execute()

  def insert_build_attempts(self, build_record):
    """Insert a build attempt record.

    Args:
        build_record: build record.

    Returns:
        A build attempt object.
    """
    build_attempt = {'id': 0, 'status': 'complete', 'successful': True}
    return (
        self.client.buildattempt()
        .insert(
            buildId=build_record['buildId'],
            target=build_record['target']['name'],
            body=build_attempt,
        )
        .execute()
    )

  def insert_invocation(self, build_record, atest_run_id: str):
    """Insert a build invocation record.

    Args:
        build_record: build record.
        atest_run_id: The atest run ID to write into the invocation.

    Returns:
        A build invocation object.
    """
    sponge_invocation_id = str(uuid.uuid4())
    user_email = metrics_base.get_user_email()
    invocation = {
        'primaryBuild': {
            'buildId': build_record['buildId'],
            'buildTarget': build_record['target']['name'],
            'branch': build_record['branch'],
        },
        'schedulerState': 'running',
        'runner': 'atest',
        'scheduler': 'atest',
        'users': [user_email],
        'properties': [
            {
                'name': 'sponge_invocation_id',
                'value': sponge_invocation_id,
            },
            {
                'name': 'test_uri',
                'value': f'{constants.STORAGE2_TEST_URI}{sponge_invocation_id}',
            },
            {'name': 'atest_run_id', 'value': atest_run_id},
        ],
    }
    return self.client.invocation().insert(body=invocation).execute()

  def update_invocation(self, invocation):
    """Insert a build invocation record.

    Args:
        invocation: invocation record.

    Returns:
        A invocation object.
    """
    # Because invocation revision will be update by TF, we need to fetch
    # latest invocation revision to update status correctly.
    count = 0
    invocations = None
    while count < 5:
      invocations = (
          self.client.invocation()
          .list(invocationId=invocation['invocationId'], maxResults=10)
          .execute()
          .get('invocations', [])
      )
      if invocations:
        break
      time.sleep(0.5)
      count = count + 1
    if invocations:
      latest_revision = invocations[-1].get('revision', '')
      if latest_revision:
        logging.debug(
            'Get latest_revision:%s from invocations:%s',
            latest_revision,
            invocations,
        )
        invocation['revision'] = latest_revision
    return (
        self.client.invocation()
        .update(resourceId=invocation['invocationId'], body=invocation)
        .execute()
    )

  def insert_work_unit(self, invocation_record):
    """Insert a workunit record.

    Args:
        invocation_record: invocation record.

    Returns:
        the workunit object.
    """
    workunit = {'invocationId': invocation_record['invocationId']}
    return self.client.workunit().insert(body=workunit).execute()
