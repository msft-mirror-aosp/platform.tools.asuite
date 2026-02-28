import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from atest.mobly.storage import gcs_client


class GcsClientTest(unittest.TestCase):
  """Unit tests for GcsClient."""

  def setUp(self):
    self.test_dir = tempfile.mkdtemp()
    self.src_dir = pathlib.Path(self.test_dir)
    self.gcs_bucket = "test_bucket"
    self.gcs_dir = "test_gcs_dir"
    self.client = gcs_client.GcsClient(self.gcs_bucket)

  def tearDown(self):
    shutil.rmtree(self.test_dir)

  @mock.patch("subprocess.run")
  def test_upload_dir_success(self, mock_run):
    """Tests successful directory upload."""
    # Create dummy files in the temporary directory
    (self.src_dir / "file1.txt").touch()
    subdir = self.src_dir / "subdir"
    subdir.mkdir()
    (subdir / "file2.txt").touch()

    dest_uri = f"gs://{self.gcs_bucket}/{self.gcs_dir}"

    # Call the method under test
    uploaded_files = self.client.upload_dir(self.src_dir, self.gcs_dir)

    # Verify subprocess call
    mock_run.assert_called_once_with(
        ["gcloud", "storage", "cp", "-r", ".", dest_uri],
        cwd=str(self.src_dir),
        timeout=300,
        check=True,
        capture_output=True,
        text=True,
    )

    # Verify returned file paths
    expected_files = [
        f"{self.gcs_dir}/file1.txt",
        f"{self.gcs_dir}/subdir/file2.txt",
    ]
    self.assertCountEqual(uploaded_files, expected_files)

  @mock.patch("builtins.print")
  @mock.patch("subprocess.run")
  def test_upload_dir_gcloud_not_found(self, mock_run, mock_print):
    """Tests handling of FileNotFoundError (gcloud missing)."""
    error_msg = "gcloud not found"
    mock_run.side_effect = FileNotFoundError(error_msg)

    uploaded_files = self.client.upload_dir(self.src_dir, self.gcs_dir)

    self.assertEqual(uploaded_files, [])
    mock_print.assert_called_with(
        f"Error: {error_msg}, Please ensure google-cloud-cli is installed."
    )

  @mock.patch("builtins.print")
  @mock.patch("subprocess.run")
  def test_upload_dir_subprocess_error(self, mock_run, mock_print):
    """Tests handling of subprocess.CalledProcessError."""
    stderr_msg = "failed to upload files"
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd="gcloud", stderr=stderr_msg
    )

    uploaded_files = self.client.upload_dir(self.src_dir, self.gcs_dir)

    self.assertEqual(uploaded_files, [])
    mock_print.assert_called_with(stderr_msg)


if __name__ == "__main__":
  unittest.main()
