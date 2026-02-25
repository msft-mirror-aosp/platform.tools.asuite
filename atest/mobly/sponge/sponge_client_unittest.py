"""Tests for sponge_client."""

import json
import subprocess
import unittest
from unittest import mock
from urllib import parse

from atest.mobly.sponge import sponge_client


class SpongeClientTest(unittest.TestCase):
  """Unit tests for SpongeClient."""

  def setUp(self):
    """Set up the test."""
    self.client = sponge_client.SpongeClient(
        address="http://test_address",
        api_key="test_api_key",
        authorization_token="test_auth_token",
    )

  def test_build_url(self):
    """Test build_url."""
    path = "/v2/invocations"
    params = {"invocation_id": "123", "request_id": "abc"}
    parsed_url = parse.urlparse(self.client.build_url(path, params))
    self.assertEqual(f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}",
                     "http://test_address/v2/invocations")
    self.assertEqual(
        parse.parse_qs(parsed_url.query),
        {"invocation_id": ["123"], "request_id": ["abc"]},
    )

  def test_create_timing_attributes(self):
    """Test create_timing_attributes."""
    start_time = "2023-01-01T00:00:00.000Z"
    duration = "5s"
    self.assertEqual(self.client.create_timing_attributes(), {})
    self.assertEqual(
        self.client.create_timing_attributes(start_time_str=start_time),
        {"startTime": start_time},
    )
    self.assertEqual(
        self.client.create_timing_attributes(duration=duration),
        {"duration": duration},
    )
    self.assertEqual(
        self.client.create_timing_attributes(
            start_time_str=start_time, duration=duration
        ),
        {"startTime": start_time, "duration": duration},
    )

  def test_create_files(self):
    """Test create_files."""
    self.assertEqual(self.client.create_files("bucket", "dir", []), [])
    gcs_filepaths = ["dir/file1.txt", "dir/subdir/file2.log"]
    expected_files = [
        {"uid": "file1.txt", "uri": "gs://bucket/dir/file1.txt"},
        {
            "uid": "subdir/file2.log",
            "uri": "gs://bucket/dir/subdir/file2.log",
        },
    ]
    self.assertEqual(
        self.client.create_files("bucket", "dir", gcs_filepaths),
        expected_files,
    )

  @mock.patch("subprocess.run")
  def test_request_success(self, mock_run):
    """Test request success case."""
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout='{"key": "value"}', stderr=""
    )
    response = self.client.request("POST", "http://test_url", {"data": "test"})
    self.assertEqual(response, {"key": "value"})
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    self.assertIn("sso_client", call_args)
    self.assertIn("--method=POST", call_args)
    self.assertIn("--url=http://test_url", call_args)
    self.assertIn("X-Goog-Api-Key: test_api_key", call_args[3])
    self.assertIn("Content-Type: application/json", call_args[3])
    self.assertEqual(
        json.loads(call_args[4].split("=", 1)[1]), {"data": "test"}
    )

  @mock.patch(
      "subprocess.run",
      side_effect=subprocess.CalledProcessError(1, "cmd", stderr="error"),
  )
  @mock.patch("builtins.print")
  @mock.patch("logging.error")
  def test_request_called_process_error(
      self, mock_log_error, mock_print, mock_run
  ):
    """Test request with CalledProcessError."""
    self.client.request("POST", "http://test_url", {})
    mock_run.assert_called_once()
    mock_log_error.assert_called_with("error")
    mock_print.assert_called_with("error")

  @mock.patch("subprocess.run", side_effect=Exception("generic error"))
  @mock.patch("builtins.print")
  @mock.patch("logging.error")
  def test_request_exception(self, mock_log_error, mock_print, mock_run):
    """Test request with a generic exception."""
    self.client.request("POST", "http://test_url", {})
    mock_run.assert_called_once()
    self.assertIsInstance(mock_log_error.call_args[0][0], Exception)
    self.assertEqual(str(mock_log_error.call_args[0][0]), "generic error")
    self.assertIsInstance(mock_print.call_args[0][0], Exception)
    self.assertEqual(str(mock_print.call_args[0][0]), "generic error")

  @mock.patch.object(sponge_client.SpongeClient, "request")
  def test_post(self, mock_request):
    """Test post."""
    self.client.post("url", {"data": "test"})
    mock_request.assert_called_once_with("POST", "url", {"data": "test"})

  @mock.patch.object(sponge_client.SpongeClient, "request")
  def test_patch(self, mock_request):
    """Test patch."""
    self.client.patch("url", {"data": "test"})
    mock_request.assert_called_once_with("PATCH", "url", {"data": "test"})

  @mock.patch.object(sponge_client.SpongeClient, "post")
  @mock.patch("uuid.uuid4", return_value="test-uuid")
  @mock.patch("getpass.getuser", return_value="test_user")
  @mock.patch("datetime.datetime")
  def test_create_invocation(self, mock_dt, _getuser, _uuid, mock_post):
    """Test create_invocation."""
    mock_now = mock.Mock()
    mock_dt.now.return_value = mock_now
    mock_now.isoformat.return_value.replace.return_value = (
        "2023-01-01T00:00:00.000Z"
    )
    mock_post.return_value = {"name": "invocations/123"}

    invocation_name = self.client.create_invocation("inv-id")
    self.assertEqual(invocation_name, "invocations/123")

    expected_data = {
        "statusAttributes": {"status": "TESTING"},
        "timing": {"startTime": "2023-01-01T00:00:00.000Z"},
        "invocationAttributes": {
            "projectId": "google.com:sponge-resultstore",
            "users": ["test_user"],
            "labels": ["atest", "mobly", "test"],
        },
    }
    mock_post.assert_called_once()
    call_args = mock_post.call_args[0]
    self.assertEqual(call_args[1], expected_data)
    parsed_url = parse.urlparse(call_args[0])
    self.assertEqual(parsed_url.path, "/v2/invocations")
    query_params = parse.parse_qs(parsed_url.query)
    self.assertEqual(query_params["invocation_id"], ["inv-id"])
    self.assertEqual(query_params["request_id"], ["test-uuid"])

  @mock.patch.object(sponge_client.SpongeClient, "patch")
  def test_update_invocation_status(self, mock_patch):
    """Test update_invocation_status."""
    self.client.update_invocation_status("invocations/123", "PASSED")
    expected_data = {"statusAttributes": {"status": "PASSED"}}
    mock_patch.assert_called_once()
    call_args = mock_patch.call_args[0]
    self.assertEqual(call_args[1], expected_data)
    parsed_url = parse.urlparse(call_args[0])
    self.assertEqual(parsed_url.path, "/v2/invocations/123")
    query_params = parse.parse_qs(parsed_url.query)
    self.assertEqual(query_params["update_mask"], ["statusAttributes"])

  @mock.patch.object(sponge_client.SpongeClient, "patch")
  def test_update_invocation_files(self, mock_patch):
    """Test update_invocation_files."""
    gcs_filepaths = ["dir/file1"]
    self.client.update_invocation_files(
        "invocations/123", "bucket", "dir", gcs_filepaths
    )

    expected_files = [{"uid": "file1", "uri": "gs://bucket/dir/file1"}]
    expected_data = {"files": expected_files}

    mock_patch.assert_called_once()
    call_args = mock_patch.call_args[0]
    self.assertEqual(call_args[1], expected_data)
    parsed_url = parse.urlparse(call_args[0])
    self.assertEqual(parsed_url.path, "/v2/invocations/123")
    query_params = parse.parse_qs(parsed_url.query)
    self.assertEqual(query_params["update_mask"], ["files"])

  @mock.patch.object(sponge_client.SpongeClient, "patch")
  @mock.patch("logging.warning")
  def test_update_invocation_files_no_files(
      self, mock_log_warning, mock_patch
  ):
    """Test update_invocation_files with no files."""
    self.client.update_invocation_files("invocations/123", "bucket", "dir", [])
    mock_patch.assert_not_called()
    mock_log_warning.assert_called_once_with(
        "No files to update for invocation %s", "invocations/123"
    )

  @mock.patch.object(sponge_client.SpongeClient, "post")
  @mock.patch("uuid.uuid4", return_value="test-uuid")
  @mock.patch("platform.machine", return_value="test_machine")
  def test_create_configuration(self, _machine, _uuid, mock_post):
    """Test create_configuration."""
    self.client.create_configuration("invocations/123", "config-id")

    expected_data = {"configurationAttributes": {"cpu": "test_machine"}}
    mock_post.assert_called_once()
    call_args = mock_post.call_args[0]
    self.assertEqual(call_args[1], expected_data)
    parsed_url = parse.urlparse(call_args[0])
    self.assertEqual(parsed_url.path, "/v2/invocations/123/configs")
    query_params = parse.parse_qs(parsed_url.query)
    self.assertEqual(query_params["config_id"], ["config-id"])

  @mock.patch.object(sponge_client.SpongeClient, "post")
  @mock.patch("uuid.uuid4", return_value="test-uuid")
  def test_create_target(self, _uuid, mock_post):
    """Test create_target."""
    mock_post.return_value = {"name": "invocations/123/targets/abc"}
    target_name = self.client.create_target("invocations/123", "target-id")
    self.assertEqual(target_name, "invocations/123/targets/abc")

    expected_data = {
        "targetAttributes": {
            "type": "TEST",
            "language": "PY",
            "tags": ["external", "local", "manual", "py_strict_test"],
        },
        "visible": True,
    }
    mock_post.assert_called_once()
    call_args = mock_post.call_args[0]
    self.assertEqual(call_args[1], expected_data)
    parsed_url = parse.urlparse(call_args[0])
    self.assertEqual(parsed_url.path, "/v2/invocations/123/targets")
    query_params = parse.parse_qs(parsed_url.query)
    self.assertEqual(query_params["target_id"], ["target-id"])

  @mock.patch.object(sponge_client.SpongeClient, "post")
  @mock.patch("uuid.uuid4", return_value="test-uuid")
  def test_create_configured_target(self, _uuid, mock_post):
    """Test create_configured_target."""
    mock_post.return_value = {"name": "configured/target/name"}
    ct_name = self.client.create_configured_target(
        "target/name", "config-id", start_time_str="start"
    )
    self.assertEqual(ct_name, "configured/target/name")

    expected_data = {"timing": {"startTime": "start"}}
    mock_post.assert_called_once()
    call_args = mock_post.call_args[0]
    self.assertEqual(call_args[1], expected_data)
    parsed_url = parse.urlparse(call_args[0])
    self.assertEqual(parsed_url.path, "/v2/target/name/configuredTargets")
    query_params = parse.parse_qs(parsed_url.query)
    self.assertEqual(query_params["config_id"], ["config-id"])

  @mock.patch.object(sponge_client.SpongeClient, "patch")
  def test_update_configured_target_status(self, mock_patch):
    """Test update_configured_target_status."""
    self.client.update_configured_target_status("ct/name", "PASSED")
    expected_data = {"statusAttributes": {"status": "PASSED"}}
    mock_patch.assert_called_once()
    call_args = mock_patch.call_args[0]
    self.assertEqual(call_args[1], expected_data)
    parsed_url = parse.urlparse(call_args[0])
    self.assertEqual(parsed_url.path, "/v2/ct/name")
    query_params = parse.parse_qs(parsed_url.query)
    self.assertEqual(query_params["update_mask"], ["statusAttributes"])

  @mock.patch.object(sponge_client.SpongeClient, "patch")
  def test_update_configured_target_timing(self, mock_patch):
    """Test update_configured_target_timing."""
    self.client.update_configured_target_timing(
        "ct/name", start_time_str="start"
    )
    expected_data = {"timing": {"startTime": "start"}}
    mock_patch.assert_called_once()
    call_args = mock_patch.call_args[0]
    self.assertEqual(call_args[1], expected_data)
    parsed_url = parse.urlparse(call_args[0])
    self.assertEqual(parsed_url.path, "/v2/ct/name")
    query_params = parse.parse_qs(parsed_url.query)
    self.assertEqual(query_params["update_mask"], ["timing"])

  @mock.patch.object(sponge_client.SpongeClient, "post")
  @mock.patch("uuid.uuid4")
  def test_create_action(self, mock_uuid, mock_post):
    """Test create_action."""
    mock_uuid.side_effect = ["action-uuid", "request-uuid"]
    mock_post.return_value = {"name": "action/name"}
    action_name = self.client.create_action(
        "ct/name",
        "PASSED",
        1,
        "bucket",
        "dir",
        ["dir/file1"],
        start_time_str="start",
    )
    self.assertEqual(action_name, "action/name")

    expected_data = {
        "testAction": {"runNumber": 1},
        "statusAttributes": {"status": "PASSED"},
        "actionAttributes": {"executionStrategy": "LOCAL_SEQUENTIAL"},
        "files": [{"uid": "file1", "uri": "gs://bucket/dir/file1"}],
        "timing": {"startTime": "start"},
    }

    mock_post.assert_called_once()
    call_args = mock_post.call_args[0]
    self.assertEqual(call_args[1], expected_data)
    parsed_url = parse.urlparse(call_args[0])
    self.assertEqual(parsed_url.path, "/v2/ct/name/actions")
    query_params = parse.parse_qs(parsed_url.query)
    self.assertEqual(query_params["action_id"], ["action-uuid"])
    self.assertEqual(query_params["request_id"], ["request-uuid"])

  @mock.patch.object(sponge_client.SpongeClient, "post")
  def test_finalize_target(self, mock_post):
    """Test finalize_target."""
    self.client.finalize_target("target/name")
    mock_post.assert_called_once_with(
        "http://test_address/v2/target/name:finalize?authorization_token=test_auth_token",
        {},
    )

  @mock.patch.object(sponge_client.SpongeClient, "post")
  def test_finalize_configured_target(self, mock_post):
    """Test finalize_configured_target."""
    self.client.finalize_configured_target("ct/name")
    mock_post.assert_called_once_with(
        "http://test_address/v2/ct/name:finalize?authorization_token=test_auth_token",
        {},
    )

  @mock.patch.object(sponge_client.SpongeClient, "post")
  def test_finalize_invocation(self, mock_post):
    """Test finalize_invocation."""
    self.client.finalize_invocation("invocations/123")
    mock_post.assert_called_once_with(
        "http://test_address/v2/invocations/123:finalize?authorization_token=test_auth_token",
        {},
    )


if __name__ == "__main__":
  unittest.main()
