import functools
import logging
from typing import Any
from urllib import parse

from atest import result_reporter

from resultdb_uploader import resultdb_uploader_wrapper

TEST_RESULT_URL_PROD = (
  "https://ci.chromium.org/ui/test-investigate/invocations/"
)
TEST_RESULT_URL_DEV = (
  "https://luci-milo-dev.appspot.com/ui/test-investigate/invocations/"
)


def get_resultdb_invocation_id(ants_invocation_id: str) -> str:
  """Converts an AnTS invocation ID to a ResultDB invocation ID."""
  return f"u-ants-{ants_invocation_id}"


class ResultDBUploader:
  """Uploader for ResultDB."""

  def __init__(
    self,
    user_enabled_upload: bool,
    base_log_path: str | None = None,
    is_prod: bool = False,
  ):
    self.ants_invocation_id = None
    self.user_enabled_upload = user_enabled_upload
    self.base_log_path = base_log_path
    self.is_prod = is_prod
    self.test_results = []

  def set_ants_invocation_id(self, ants_invocation_id: str):
    """Sets the AnTS invocation ID."""
    self.ants_invocation_id = ants_invocation_id.lower()

  @functools.cached_property
  def enabled(self) -> bool:
    """Checks if the ResultDB uploader is enabled."""
    return self.user_enabled_upload and resultdb_uploader_wrapper.enabled()

  def add_test_result(self, test_result: dict[str, Any]):
    """Add a test result to the list of test results to upload."""
    test_result["ants_work_unit_id"] = test_result["ants_work_unit_id"].lower()
    self.test_results.append(test_result)
    logging.debug(f"Added test result for ResultDB upload: {test_result}")

  def upload(self) -> bool:
    """Upload test results to ResultDB."""
    if not self.test_results:
      logging.warning("No test results to upload.")
      return False

    if not self.ants_invocation_id:
      logging.error("Something is wrong. No AnTS invocation ID set.")
      return False

    if resultdb_uploader_wrapper.upload(
      self.ants_invocation_id,
      self.test_results,
      base_log_path=self.base_log_path,
      is_prod=self.is_prod,
    ):
      logging.debug("Successfully uploaded test results to ResultDB.")
    else:
      logging.error("Failed to upload test results to ResultDB.")
      return False
    return True

  def get_test_result_url(self) -> str:
    """Returns the test investigate URL for the given ResultDB instance."""
    resultdb_invocation_id = get_resultdb_invocation_id(self.ants_invocation_id)
    base_url = TEST_RESULT_URL_PROD if self.is_prod else TEST_RESULT_URL_DEV
    return parse.urljoin(base_url, resultdb_invocation_id)

  def add_result_link(self, reporter: result_reporter.ResultReporter):
    """Add the invocation link to the result reporter.

    Args:
        reporter: The result reporter to add to.
    """
    new_result_link = self.get_test_result_url()
    if isinstance(reporter.test_result_link, list):
      reporter.test_result_link.append(new_result_link)
    elif isinstance(reporter.test_result_link, str):
      reporter.test_result_link = [reporter.test_result_link, new_result_link]
    else:
      reporter.test_result_link = [new_result_link]

