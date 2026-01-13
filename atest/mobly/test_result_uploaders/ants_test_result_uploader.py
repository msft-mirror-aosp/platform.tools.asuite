import logging
import os
import time
from typing import Any, Dict

from atest import atest_enum
from atest import constants
from atest import result_reporter
from atest.logstorage import logstorage_utils
from atest.metrics import metrics
from atest.mobly.rerun_options import RerunOptions

try:
  from googleapiclient import errors, http
except ModuleNotFoundError as err:
  logging.debug('Import error due to: %s', err)

WORKUNIT_ATEST_MOBLY_RUNNER = 'ATEST_MOBLY_RUNNER'
FILE_UPLOAD_RETRIES = 3
WORKUNIT_ATEST_MOBLY_TEST_RUN = 'ATEST_MOBLY_TEST_RUN'


class AntsTestResultUploader:
  """Uploader for Android Build test storage."""

  def __init__(
      self,
      extra_args: Dict[str, Any],
      user_enabled_upload: bool,
  ):
    """Set up the build client."""
    self._build_client = None
    self._legacy_client = None
    self._legacy_result_id = None
    self._test_results = {}

    upload_start = time.monotonic()
    creds, self._invocation = (
        logstorage_utils.do_upload_flow(extra_args)
        if user_enabled_upload and logstorage_utils.credential_exists()
        else (None, None)
    )

    self._root_workunit = None
    self._current_workunit = None

    if creds:
      metrics.LocalDetectEvent(
          detect_type=atest_enum.DetectType.UPLOAD_FLOW_MS,
          result=int((time.monotonic() - upload_start) * 1000),
      )
      self._build_client = logstorage_utils.BuildClient(creds)
      self._legacy_client = logstorage_utils.BuildClient(
          creds,
          api_version=constants.STORAGE_API_VERSION_LEGACY,
          url=constants.DISCOVERY_SERVICE_LEGACY,
      )
      self._setup_root_workunit()
    else:
      logging.debug('Result upload is disabled.')

  def _setup_root_workunit(self):
    """Create and populate fields for the root workunit."""
    self._root_workunit = self._build_client.insert_work_unit(self._invocation)
    self._root_workunit['type'] = WORKUNIT_ATEST_MOBLY_RUNNER
    self._root_workunit['runCount'] = 0

  @property
  def enabled(self):
    """Returns True if the uploader is enabled."""
    return self._build_client is not None

  @property
  def invocation(self):
    """The invocation of the current run."""
    return self._invocation

  @property
  def current_workunit(self):
    """The workunit of the current iteration."""
    return self._current_workunit

  def start_new_workunit(self):
    """Create and start a new workunit for the iteration."""
    if not self.enabled:
      return
    self._current_workunit = self._build_client.insert_work_unit(
        self._invocation
    )
    self._current_workunit['type'] = WORKUNIT_ATEST_MOBLY_TEST_RUN
    self._current_workunit['parentId'] = self._root_workunit['id']

  def set_workunit_iteration_details(
      self, iteration_num: int, rerun_options: RerunOptions
  ):
    """Set iteration-related fields in the current workunit.

    Args:
        iteration_num: Index of the current iteration.
        rerun_options: Rerun options for the test.
    """
    if not self.enabled:
      return
    details = {}
    if rerun_options.retry_any_failure:
      details['childAttemptNumber'] = iteration_num
    else:
      details['childRunNumber'] = iteration_num
    self._current_workunit.update(details)

  def _finalize_workunit(self, workunit: Dict[str, Any]):
    """Finalize the specified workunit."""
    workunit['schedulerState'] = 'completed'
    logging.debug('Finalizing workunit: %s', workunit)
    self._build_client.client.workunit().update(
        resourceId=workunit['id'], body=workunit
    )
    if workunit is not self._root_workunit:
      self._root_workunit['runCount'] += 1

  def finalize_current_workunit(self):
    """Finalize the workunit for the current iteration."""
    if not self.enabled:
      return
    self._test_results.clear()
    self._finalize_workunit(self._current_workunit)
    self._current_workunit = None

  def record_test_result(self, test_result):
    """Record a test result to be uploaded."""
    test_identifier = test_result['testIdentifier']
    class_method = f'{test_identifier["testClass"]}.{test_identifier["method"]}'
    self._test_results[class_method] = test_result

  def upload_test_results(self):
    """Bulk upload all recorded test results."""
    if not (self.enabled and self._test_results):
      return
    response = (
        self._build_client.client.testresult()
        .bulkinsert(
            invocationId=self._invocation['invocationId'],
            body={'testResults': list(self._test_results.values())},
        )
        .execute()
    )
    logging.debug('Uploaded test results: %s', response)

  def _upload_single_file(
      self, path: str, base_dir: str, legacy_result_id: str
  ):
    """Upload a single test file to build storage."""
    invocation_id = self._invocation['invocationId']
    workunit_id = self._current_workunit['id']
    name = os.path.join(workunit_id, os.path.relpath(path, base_dir))
    metadata = {
        'invocationId': invocation_id,
        'workUnitId': workunit_id,
        'name': name,
    }
    logging.debug('Uploading test artifact file %s', name)
    try:
      self._build_client.client.testartifact().update(
          resourceId=name,
          invocationId=invocation_id,
          workUnitId=workunit_id,
          body=metadata,
          legacyTestResultId=legacy_result_id,
          media_body=http.MediaFileUpload(path),
      ).execute(num_retries=FILE_UPLOAD_RETRIES)
    except errors.HttpError as e:
      logging.debug('Failed to upload file %s with error: %s', name, e)

  def upload_test_artifacts(self, log_dir: str):
    """Upload test artifacts and associate them to the workunit.

    Args:
        log_dir: The directory of logs to upload.
    """
    if not self.enabled:
      return
    # Use the legacy API to insert a test result and get a test result
    # id, as it is required for test artifact upload.
    res = (
        self._legacy_client.client.testresult()
        .insert(
            buildId=self.invocation['primaryBuild']['buildId'],
            target=self.invocation['primaryBuild']['buildTarget'],
            attemptId='latest',
            body={
                'status': 'completePass',
            },
        )
        .execute()
    )

    for root, _, file_names in os.walk(log_dir):
      for file_name in file_names:
        self._upload_single_file(
            os.path.join(root, file_name), log_dir, res['id']
        )

  def finalize_invocation(self):
    """Set the root work unit and invocation as complete."""
    if not self.enabled:
      return
    self._finalize_workunit(self._root_workunit)
    self.invocation['runner'] = 'mobly'
    self.invocation['schedulerState'] = 'completed'
    logging.debug('Finalizing invocation: %s', self.invocation)
    self._build_client.update_invocation(self.invocation)
    self._build_client = None

  def add_result_link(self, reporter: result_reporter.ResultReporter):
    """Add the invocation link to the result reporter.

    Args:
        reporter: The result reporter to add to.
    """
    new_result_link = constants.RESULT_LINK % self._invocation['invocationId']
    if isinstance(reporter.test_result_link, list):
      reporter.test_result_link.append(new_result_link)
    elif isinstance(reporter.test_result_link, str):
      reporter.test_result_link = [reporter.test_result_link, new_result_link]
    else:
      reporter.test_result_link = [new_result_link]
