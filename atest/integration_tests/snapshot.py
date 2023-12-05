#!/usr/bin/env python3
#
# Copyright 2023, The Android Open Source Project
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


"""Provides a snapshot functionality for preserving and restoring the state of a repository.

This module includes:
- `ISnapshot`: An abstract class defining the interface for snapshot
implementations.
- `TarEverythingSnapshot`: A concrete implementation that creates tarball
snapshots of the repository.

Features:
- Takes snapshots by including and excluding specified paths.
- Preserves a subset of environment variables.
- Restores the repository state from previously taken snapshots.

Usage:
```python
snapshot = Snapshot(name, workspace_dir, artifacts_dir)
snapshot.take(include_paths, exclude_paths, env_keys)
snapshot.restore()
```
"""

import glob
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from typing import abstractmethod, Dict, List, Protocol


class Snapshot(Protocol):
  """Interface for taking snapshots of repo state."""

  @abstractmethod
  def take(
      self,
      include_paths: List[str],
      exclude_paths: List[str],
      env_keys: List[str],
  ) -> None:
    raise NotImplementedError

  @abstractmethod
  def restore(self) -> Dict[str, str]:
    raise NotImplementedError


class TarEverythingSnapshot(Snapshot):
  """Basic implementation that tars everything."""

  _repo_root_placeholder = '<repo_root_placeholder>'
  _artifact_name_prefix = 'ATEST_INTEGRATION_TESTS_PREFIX_'

  def __init__(
      self,
      name: str,
      workspace_dir: Path,
      artifacts_dir: Path,
  ):
    self._name = name
    self._workspace_dir = workspace_dir
    self._artifacts_dir = artifacts_dir
    self._current_snapshot_index = 0

  def take(
      self,
      include_paths: List[str],
      exclude_paths: List[str],
      env_keys: List[str],
  ) -> None:
    self._current_snapshot_index += 1
    self._save_environ(env_keys)
    self._tar(include_paths, exclude_paths)

  def restore(self) -> Dict[str, str]:
    self._current_snapshot_index += 1
    self._untar()
    return self._load_environ()

  def _save_environ(self, env_keys: List[str]) -> None:
    """Save a subset of environment variables."""
    original_env = os.environ.copy()
    subset_env = {
        key: os.environ[key] for key in env_keys if key in original_env
    }
    modified_env = {
        key: value.replace(
            os.environ['ANDROID_BUILD_TOP'], self._repo_root_placeholder
        )
        for key, value in subset_env.items()
    }
    with open(self._get_env_file_path(), 'w') as f:
      json.dump(modified_env, f)

  def _load_environ(self) -> Dict[str, str]:
    """Load saved environment variables."""
    with self._get_env_file_path().open('r') as f:
      loaded_env = json.load(f)
    restored_env = {
        key: value.replace(
            self._repo_root_placeholder,
            self._workspace_dir.as_posix(),
        )
        for key, value in loaded_env.items()
    }
    restored_env_without_path = {
        key: value for key, value in restored_env.items() if key != 'PATH'
    }
    result_env = os.environ.copy() | restored_env_without_path
    result_env['PATH'] = restored_env['PATH'] + ':' + result_env['PATH']
    return result_env

  def _get_env_file_path(self) -> Path:
    """Get environment file path."""
    return self._artifacts_dir / (
        self._artifact_name_prefix
        + self._name
        + str(self._current_snapshot_index)
        + '.json'
    )

  def _get_tar_file_path(self) -> Path:
    """Get tarball file path."""
    return self._artifacts_dir / (
        self._artifact_name_prefix
        + self._name
        + str(self._current_snapshot_index)
        + '.tar'
    )

  def _untar(self) -> None:
    """Untar artifacts."""
    untar_dir = self._workspace_dir
    if untar_dir.exists():
      shutil.rmtree(untar_dir)
    untar_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(self._get_tar_file_path().as_posix(), 'r') as tar:
      tar.extractall(path=untar_dir)

  def _tar(
      self,
      include_paths: List[str],
      exclude_paths: List[str],
  ) -> None:
    """Tar artifacts."""
    tar_include_paths = self._expand_wildcard_paths(include_paths)
    tar_exclude_paths = self._expand_wildcard_paths(exclude_paths)

    self._artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Here we are not using the tarfile module because the filter argument
    # doesn't work as good as the exclude flag in the cmd tool
    subprocess.run(
        ['tar']
        + ['--exclude=' + exclude_path for exclude_path in tar_exclude_paths]
        + ['-cpf', self._get_tar_file_path().as_posix()]
        + tar_include_paths,
        check=True,
    )

  def _expand_wildcard_paths(self, paths: List[str]) -> List[str]:
    """Expand wildcard paths."""
    return [
        expanded_path
        for wildcard_path in paths
        for expanded_path in glob.glob(wildcard_path)
    ]


# Default snapshot impl
Snapshot = TarEverythingSnapshot
