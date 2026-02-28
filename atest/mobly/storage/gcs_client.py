import logging
import pathlib
import subprocess


class GcsClient:
  """A class for uploading local files to a GCS bucket."""

  def __init__(
      self,
      gcs_bucket: str,
      timeout: int = 300,
  ) -> None:
    self.gcs_bucket = gcs_bucket
    self.timeout = timeout

  def upload_dir(
      self, src_dir: pathlib.Path, gcs_dir: str,
  ) -> list[str]:
    """Uploads the given directory to a GCS bucket."""
    dest_uri = f"gs://{self.gcs_bucket}/{gcs_dir}"
    logging.info("Uploading files from %s to %s", src_dir, dest_uri)
    gcs_filepaths = []
    try:
      subprocess.run(
          ["gcloud", "storage", "cp", "-r", ".", dest_uri],
          cwd=str(src_dir),
          timeout=self.timeout,
          check=True,
          capture_output=True,
          text=True,
      )
    except FileNotFoundError as e:
      print(f"Error: {e}, Please ensure google-cloud-cli is installed.")
      logging.error(e)
    except subprocess.CalledProcessError as e:
      print(e.stderr)
      logging.error(e.stderr)
    else:
      logging.info("Successfully uploaded %d files.", len(gcs_filepaths))
      for path in src_dir.rglob("*"):
        if path.is_file():
          gcs_filepaths.append(
              f"{gcs_dir}/{path.relative_to(src_dir).as_posix()}"
          )
    return gcs_filepaths
