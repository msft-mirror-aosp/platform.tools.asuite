import datetime
import getpass
import json
import logging
import pathlib
import platform
import subprocess
from typing import Any
from urllib import parse
import uuid


JSONABLE = dict[str, Any]


class SpongeClient:
  """A client for uploading test results to Sponge via HTTP."""

  def __init__(self, address: str, api_key: str, authorization_token: str):
    self._address = address
    self._api_key = api_key
    self._authorization_token = authorization_token

  def request(self, method: str, url: str, data: JSONABLE) -> JSONABLE:
    """Makes a request using sso_client."""
    headers = {
        "X-Goog-Api-Key": self._api_key,
        "Content-Type": "application/json",
    }
    headers_str = ";".join([f"{k}: {v}" for k, v in headers.items()])
    body = json.dumps(data)
    try:
      command = [
          "sso_client",
          f"--method={method}",
          f"--url={url}",
          f"--headers={headers_str}",
          f"--data={body}",
      ]
      logging.info("Executing command: %s", " ".join(command))
      result = subprocess.run(
          command,
          capture_output=True,
          text=True,
          check=True,
          encoding="utf-8",
      )

      response_body = result.stdout
      logging.info("Response: %s", response_body)

      # Parse the JSON response into a dictionary
      return json.loads(response_body)
    except subprocess.CalledProcessError as e:
      print(e.stderr)
      logging.error(e.stderr)
    except Exception as e:
      print(e)
      logging.error(e)

  def post(self, url: str, data: JSONABLE) -> JSONABLE:
    """Makes a POST request using sso_client."""
    return self.request("POST", url, data)

  def patch(self, url: str, data: JSONABLE) -> JSONABLE:
    """Makes a PATCH request using sso_client."""
    return self.request("PATCH", url, data)

  def build_url(self, path: str, params: dict[str, str]) -> str:
    """Constructs a URL with query parameters."""
    return f"{self._address}{path}?{parse.urlencode(params)}"

  def create_timing_attributes(self, **kwargs: Any) -> dict[str, str]:
    """Creates a timing attributes dictionary from kwargs."""
    timing_attributes = {}
    if "start_time_str" in kwargs:
      timing_attributes["startTime"] = kwargs["start_time_str"]
    if "duration" in kwargs:
      timing_attributes["duration"] = kwargs["duration"]
    return timing_attributes

  def create_invocation(self, invocation_id: str) -> str:
    """Creates a Sponge invocation via HTTP POST using sso_client."""
    request_id = str(uuid.uuid4())

    start_time_str = (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
    invocation_data = {
        "statusAttributes": {"status": "TESTING"},
        "timing": {"startTime": start_time_str},
        "invocationAttributes": {
            "projectId": "google.com:sponge-resultstore",
            "users": [getpass.getuser()],
            "labels": ["atest", "mobly", "test"],
        },
    }

    url = self.build_url(
        "/v2/invocations",
        {
            "authorization_token": self._authorization_token,
            "invocation_id": invocation_id,
            "request_id": request_id,
        },
    )
    logging.info("Creating invocation with invocation_id %s", invocation_id)
    response_data = self.post(url, invocation_data)
    return response_data.get("name", "")

  def create_files(
      self, gcs_bucket: str, gcs_dir: str, gcs_filepaths: list[str]
  ) -> list[dict[str, str]]:
    """
    Creates a list of Sponge file objects for a given list of GCS file paths.
    """
    files = []
    for path in gcs_filepaths:
      uid = str(pathlib.PurePosixPath(path).relative_to(gcs_dir))
      files.append({
          "uid": uid,
          "uri": f"gs://{gcs_bucket}/{path}",
      })
    return files

  def update_invocation_status(self, invocation_name: str, status: str) -> None:
    """Updates a Sponge invocation via HTTP PATCH using sso_client."""
    invocation_data = {
        "statusAttributes": {"status": status},
    }
    url = self.build_url(
        f"/v2/{invocation_name}",
        {
            "authorization_token": self._authorization_token,
            "update_mask": "statusAttributes",
        },
    )

    logging.info("Updating invocation %s with status %s",
        invocation_name,
        status,
    )
    self.patch(url, invocation_data)

  def update_invocation_files(
      self,
      invocation_name: str,
      gcs_bucket: str,
      gcs_dir: str,
      gcs_filepaths: list[str],
  ) -> None:
    """Updates a Sponge invocation via HTTP PATCH using sso_client."""
    if not gcs_filepaths:
      logging.warning(
          "No files to update for invocation %s",
          invocation_name,
      )
      return

    invocation_data = {
        "files": self.create_files(gcs_bucket, gcs_dir, gcs_filepaths),
    }
    url = self.build_url(
        f"/v2/{invocation_name}",
        {
            "authorization_token": self._authorization_token,
            "update_mask": "files",
        },
    )
    logging.info(
        "Updating invocation %s with files: %s",
        invocation_name,
        gcs_filepaths,
    )
    self.patch(url, invocation_data)

  def create_configuration(
      self,
      invocation_name: str,
      config_id: str,
  ) -> None:
    """Creates a Sponge configuration via HTTP POST using sso_client."""
    request_id = str(uuid.uuid4())

    configuration_data = {
        "configurationAttributes": {"cpu": platform.machine()},
    }

    url = self.build_url(
        f"/v2/{invocation_name}/configs",
        {
            "authorization_token": self._authorization_token,
            "config_id": config_id,
            "request_id": request_id,
        },
    )

    logging.info(
        "Creating configuration with config_id %s",
        config_id,
    )
    self.post(url, configuration_data)

  def create_target(
      self, invocation_name: str, target_id: str
  ) -> str:
    """Creates a Sponge target via HTTP POST using sso_client."""
    request_id = str(uuid.uuid4())

    target_data = {
        "targetAttributes": {
            "type": "TEST",
            "language": "PY",
            "tags": ["external", "local", "manual", "py_strict_test"],
        },
        "visible": True,
    }

    url = self.build_url(
        f"/v2/{invocation_name}/targets",
        {
            "authorization_token": self._authorization_token,
            "target_id": target_id,
            "request_id": request_id,
        },
    )

    logging.info(
        "Creating target with target_id %s",
        target_id,
    )

    response_data = self.post(url, target_data)
    return response_data.get("name", "")

  def create_configured_target(
      self,
      target_name: str,
      config_id: str,
      **kwargs,
  ) -> str:
    """Creates a Sponge configured target via HTTP POST using sso_client."""
    request_id = str(uuid.uuid4())

    configured_target_data = {}
    timing_attributes = self.create_timing_attributes(**kwargs)
    if timing_attributes:
      configured_target_data["timing"] = timing_attributes

    url = self.build_url(
        f"/v2/{target_name}/configuredTargets",
        {
            "authorization_token": self._authorization_token,
            "config_id": config_id,
            "request_id": request_id,
        },
    )

    logging.info(
        "Creating configured target with config_id %s",
        config_id,
    )

    response_data = self.post(url, configured_target_data)
    return response_data.get("name", "")

  def update_configured_target_status(
      self, configured_target_name: str, status: str
  ) -> None:
    """
    Updates a Sponge configured target status via HTTP PATCH using sso_client.
    """
    configured_target_data = {
        "statusAttributes": {"status": status},
    }
    url = self.build_url(
        f"/v2/{configured_target_name}",
        {
            "authorization_token": self._authorization_token,
            "update_mask": "statusAttributes",
        },
    )
    logging.info(
        "Updating configured target %s with status %s",
        configured_target_name,
        status,
    )
    self.patch(url, configured_target_data)

  def update_configured_target_timing(
      self, configured_target_name: str, **kwargs: Any
  ) -> None:
    """
    Updates a Sponge configured target timing via HTTP PATCH using sso_client.
    """
    configured_target_data = {}
    timing_attributes = self.create_timing_attributes(**kwargs)
    if timing_attributes:
      configured_target_data["timing"] = timing_attributes
    url = self.build_url(
        f"/v2/{configured_target_name}",
        {
            "authorization_token": self._authorization_token,
            "update_mask": "timing",
        },
    )
    logging.info(
        "Updating configured target %s with timing attributes %s",
        configured_target_name,
        kwargs,
    )
    self.patch(url, configured_target_data)

  def create_action(
      self,
      configured_target_name: str,
      status: str,
      run_number: int,
      gcs_bucket: str,
      gcs_dir: str,
      gcs_filepaths: list[str],
      **kwargs,
  ) -> str:
    """Creates a Sponge action via HTTP POST using sso_client."""
    action_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())

    action_data = {
        "testAction": {"runNumber": run_number},
        "statusAttributes": {"status": status},
        "actionAttributes": {"executionStrategy": "LOCAL_SEQUENTIAL"},
    }

    if gcs_filepaths:
      action_data["files"] = self.create_files(
          gcs_bucket, gcs_dir, gcs_filepaths
      )

    timing_attributes = self.create_timing_attributes(**kwargs)
    if timing_attributes:
      action_data["timing"] = timing_attributes

    url = self.build_url(
        f"/v2/{configured_target_name}/actions",
        {
            "authorization_token": self._authorization_token,
            "action_id": action_id,
            "request_id": request_id,
        },
    )

    logging.info(
        "Creating action with action_id %s",
        action_id,
    )

    response_data = self.post(url, action_data)
    return response_data.get("name", "")

  def finalize_target(self, target_name: str) -> None:
    """Finalizes a Sponge target via HTTP POST using sso_client."""
    url = self.build_url(
        f"/v2/{target_name}:finalize",
        {"authorization_token": self._authorization_token},
    )

    logging.info(
        "Finalizing target with target_name %s",
        target_name,
    )
    self.post(url, {})

  def finalize_configured_target(self, configured_target_name: str) -> None:
    """Finalizes a Sponge configured target via HTTP POST using sso_client."""
    url = self.build_url(
        f"/v2/{configured_target_name}:finalize",
        {"authorization_token": self._authorization_token},
    )

    logging.info(
        "Finalizing configured target with configured_target_name %s",
        configured_target_name,
    )
    self.post(url, {})

  def finalize_invocation(self, invocation_name: str) -> None:
    """Finalizes a Sponge invocation via HTTP POST using sso_client."""
    url = self.build_url(
        f"/v2/{invocation_name}:finalize",
        {"authorization_token": self._authorization_token},
    )

    logging.info(
        "Finalizing invocation with invocation_name %s",
        invocation_name,
    )
    self.post(url, {})
