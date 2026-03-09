import dataclasses
import datetime
import pathlib
import tempfile
import time
from typing import Any
import uuid

from atest import constants
from atest import result_reporter
from atest.mobly.sponge import sponge_client
from atest.mobly.sponge import status_aggregation
from atest.mobly.storage import gcs_client
from atest.mobly.utils import add_result_link

from sponge_artifact_creator import invocation_level_artifact_creator
from sponge_artifact_creator import target_level_artifact_creator


ATEST_LOG = "atest.log"
UNDECLARED_OUTPUTS = "undeclared_outputs"


@dataclasses.dataclass
class SpongeData:
  """A class for holding the Sponge client data."""
  invocation_id: str = ""
  invocation_name: str = ""
  config_id: str = ""
  target_id: str = ""
  target_name: str = ""
  configured_target_name: str = ""
  action_name: str = ""


@dataclasses.dataclass
class SpongeUrl:
  """A class for holding the Sponge addresses."""
  api_url: str
  test_fusion_url: str


PROD_SPONGE_URL = SpongeUrl(
    api_url=constants.SPONGE_PROD_API_URL,
    test_fusion_url=constants.TEST_FUSION_PROD_URL,
)
QA_SPONGE_URL = SpongeUrl(
    api_url=constants.SPONGE_QA_API_URL,
    test_fusion_url=constants.TEST_FUSION_QA_URL,
)


class AtestSpongeClient:
  """
  A wrapper class for SpongeClient to keep track of the current
  invocation, configuration, target, configured target, and action.
  """

  def __init__(
      self,
      is_prod: bool,
      sponge_api_key: str,
      sponge_authorization_token: str,
      gcs_bucket: str,
      results_dir: str,
      user_enabled_upload: bool = True,
  ):
    self.sponge_url = PROD_SPONGE_URL if is_prod else QA_SPONGE_URL
    self.gcs_bucket = gcs_bucket
    self.results_dir = results_dir
    self.user_enabled_upload = user_enabled_upload
    self._sponge_client = sponge_client.SpongeClient(
        self.sponge_url.api_url, sponge_api_key, sponge_authorization_token
    )
    self._gcs_client = gcs_client.GcsClient(gcs_bucket=gcs_bucket)
    self._status_aggregator = status_aggregation.SpongeStatusAggregator()
    self.sponge_data = SpongeData()
    self.target_start_time = 0.0

  @property
  def enabled(self) -> bool:
    """Returns whether the Sponge client is enabled."""
    return self.user_enabled_upload

  def _get_result_url(self) -> str:
    """Returns the result URL for the given Sponge invocation."""
    return f"{self.sponge_url.test_fusion_url}{self.sponge_data.invocation_id}"

  def _create_invocation(self, invocation_id: str) -> None:
    """Creates a Sponge invocation."""
    self.sponge_data.invocation_id = invocation_id
    self.sponge_data.invocation_name = self._sponge_client.create_invocation(
        invocation_id
    )

  def _update_invocation_status(self, status: str) -> None:
    """Updates the status of the Sponge invocation."""
    self._sponge_client.update_invocation_status(
        self.sponge_data.invocation_name, status
    )

  def _update_invocation_files(
      self, gcs_bucket: str, gcs_dir: str, gcs_filepaths: list[str]
  ) -> None:
    """Updates the files for the Sponge invocation."""
    self._sponge_client.update_invocation_files(
        self.sponge_data.invocation_name, gcs_bucket, gcs_dir, gcs_filepaths
    )

  def _create_configuration(self, config_id: str) -> None:
    """Creates a Sponge configuration."""
    self.sponge_data.config_id = config_id
    self._sponge_client.create_configuration(
        self.sponge_data.invocation_name, config_id
    )

  def _create_target(self, target_id: str) -> None:
    """Creates a Sponge target."""
    self.sponge_data.target_id = target_id
    self.sponge_data.target_name = self._sponge_client.create_target(
        self.sponge_data.invocation_name, target_id
    )

  def _create_configured_target(self, **kwargs: Any) -> None:
    """Creates a Sponge configured target."""
    self.sponge_data.configured_target_name = (
        self._sponge_client.create_configured_target(
            self.sponge_data.target_name, self.sponge_data.config_id, **kwargs
        )
    )

  def _update_configured_target_status(self, status: str) -> None:
    """Updates the status of the Sponge configured target."""
    self._sponge_client.update_configured_target_status(
        self.sponge_data.configured_target_name, status
    )

  def _update_configured_target_timing(self, **kwargs: Any) -> None:
    """Updates the timing of the Sponge configured target."""
    self._sponge_client.update_configured_target_timing(
        self.sponge_data.configured_target_name, **kwargs
    )

  def _create_action(
      self,
      status: str,
      run_number: int,
      gcs_bucket: str,
      gcs_dir: str,
      gcs_filepaths: list[str],
      **kwargs: Any,
  ) -> None:
    """Creates a Sponge action."""
    self.sponge_data.action_name = self._sponge_client.create_action(
        self.sponge_data.configured_target_name,
        status,
        run_number,
        gcs_bucket,
        gcs_dir,
        gcs_filepaths,
        **kwargs,
    )

  def _finalize_target(self) -> None:
    """Finalizes a Sponge target."""
    self._sponge_client.finalize_target(self.sponge_data.target_name)

  def _finalize_configured_target(self) -> None:
    """Finalizes a Sponge configured target."""
    self._sponge_client.finalize_configured_target(
        self.sponge_data.configured_target_name
    )

  def _finalize_invocation(self) -> None:
    """Finalizes a Sponge invocation."""
    self._sponge_client.finalize_invocation(self.sponge_data.invocation_name)

  def preprocess_invocation(self) -> None:
    """Preprocesses the Sponge Invocation."""
    invocation_id = str(uuid.uuid4())
    self._create_invocation(invocation_id)
    print(f"Streaming test results to: {self._get_result_url()}")
    config_id = str(uuid.uuid4())
    self._create_configuration(config_id)

  def postprocess_invocation(self) -> None:
    """Postprocesses the Sponge Invocation."""
    # Create Sponge invocation-level artifacts.
    with tempfile.TemporaryDirectory() as tmp_dir:
      tmp_dir = pathlib.Path(tmp_dir)
      invocation_level_artifact_creator.InvocationLevelArtifactCreator(
          src_dir=pathlib.Path(self.results_dir),
          dst_dir=tmp_dir,
          src_log_filename=ATEST_LOG,
      ).create_artifacts()

      gcs_dir = f"{self.sponge_data.invocation_id}"
      gcs_filepaths = self._gcs_client.upload_dir(tmp_dir, gcs_dir)
      # Upload invocation-level artifacts to Sponge.
      self._update_invocation_files(
          gcs_bucket=self.gcs_bucket,
          gcs_dir=gcs_dir,
          gcs_filepaths=gcs_filepaths,
      )

    # Finalize Sponge invocation.
    self._update_invocation_status(
        status=self._status_aggregator.get_current_invocation_status(),
    )
    self._finalize_invocation()
    print(f"Streaming test results to: {self._get_result_url()}")

  def reset_target_data(self) -> None:
    """Resets the target data."""
    self.target_start_time = 0.0

  def preprocess_target(self, target_id: str) -> None:
    """Preprocesses the Sponge target."""
    # Create Sponge target and configured target.
    self._create_target(target_id)
    self._create_configured_target()
    self.target_start_time = time.time()

  def postprocess_target(self) -> None:
    """Postprocesses the Sponge target."""
    self._update_configured_target_status(
        status=self._status_aggregator.get_current_configured_target_status(),
    )
    start_time_str = (
        datetime.datetime.fromtimestamp(
            self.target_start_time, datetime.timezone.utc
        )
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    duration = time.time() - self.target_start_time
    self._update_configured_target_timing(
        start_time_str=start_time_str,
        duration=f"{duration:.2f}s",
    )
    self._finalize_configured_target()
    self._finalize_target()
    self.reset_target_data()

  def upload_test_result(
      self, log_dir: str, summary_file: str, iteration_num: int
  ) -> None:
    """Uploads the test result to Sponge and GCS."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      tmp_dir = pathlib.Path(tmp_dir)
      target_level_artifact_creator.TargetLevelArtifactCreator(
          src_dir=pathlib.Path(log_dir), dst_dir=tmp_dir
      ).create_artifacts()

      gcs_dir = (
          f"{self.sponge_data.invocation_id}/{self.sponge_data.target_id}/"
          f"run{iteration_num}"
      )
      gcs_filepaths = self._gcs_client.upload_dir(tmp_dir, gcs_dir)
      gcs_filepaths.extend(
          self._gcs_client.upload_dir(
              pathlib.Path(log_dir), f"{gcs_dir}/{UNDECLARED_OUTPUTS}"
          )
      )

      # Create a Sponge action for the test run.
      self._create_action(
          status=self._status_aggregator.get_action_status(summary_file),
          run_number=iteration_num,
          gcs_bucket=self.gcs_bucket,
          gcs_dir=gcs_dir,
          gcs_filepaths=gcs_filepaths,
      )

  def add_result_link(self, reporter: result_reporter.ResultReporter):
    """Add the Sponge result link to the result reporter."""
    add_result_link(self._get_result_url(), reporter)
