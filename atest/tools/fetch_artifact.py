#!/usr/bin/env python3
# Copyright 2025, The Android Open Source Project
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

"""Utilities for fetching and linking artifacts from Android Build."""

import concurrent.futures
import itertools
import json
import logging
import pathlib
import shutil
import subprocess
import time
from typing import Any, Iterator, Sequence, Tuple
import uuid

from atest import atest_utils
from atest import constants
from atest.module_info import ModuleInfo
from atest.test_finders.test_info import TestInfo


_ARCH_64_DIR_PATTERN = '64/'
_BUILD_INFO_FILE = 'BUILD_INFO'
_CACHE_DIR = '/tmp/atest_artifact/cache'
_SWAP_DIR = '/tmp/atest_artifact/swap'
_FETCH_ARTIFACT_BIN = '/google/data/ro/projects/android/fetch_artifact'
_EXECUTABLE_SUFFIXES = frozenset(('', '.sh'))
_SUPPORTED_SUITES = frozenset(('cts', 'cts-v-host', 'vts'))
_MAX_WORKERS = 128
_MAX_ZIP_ENTRY_BATCH = 3


class CrossBranchArtifactError(Exception):
  """Error related to cross-branch artifacts."""


class ArtifactContextManager:
  """Manages cross-branch aritifacts."""

  def __init__(
      self,
      test_infos: Sequence[TestInfo],
      mod_info: ModuleInfo,
      build_target: str,
  ):
    self._test_infos = test_infos
    self._mod_info = mod_info
    self._backup_to_original_paths = {}
    self._symlinks = []
    self._swap_dir = pathlib.Path(_SWAP_DIR, str(uuid.uuid4()))
    self._cache_dir = next(
        pathlib.Path(_CACHE_DIR).glob(f'*/{build_target}'), None
    )
    if not self._cache_dir:
      raise CrossBranchArtifactError(
          f'Unable to find downloaded artifacts for {build_target}'
      )
    logging.debug('Found artifact directory %s', self._cache_dir)

  def __enter__(self):
    if not self._swap_dir.exists():
      self._swap_dir.mkdir(parents=True)

    done = set()
    try:
      for test_info in self._test_infos:
        if test_info.raw_test_name in done:
          continue
        self._symlink_artifacts(test_info)
        done.add(test_info.raw_test_name)
    except Exception as _:
      # Clean up created symlinks if any exception is raised
      self._cleanup()
      raise

  def __exit__(self, *_: Any) -> None:
    self._cleanup()

  def _symlink_artifacts(self, test_info: TestInfo):
    """Symlinks artifacts from downloaded directory to the out directory."""
    test_name = test_info.raw_test_name
    # For test supports both modes, xTS test suites include the device one.
    if constants.DEVICE_TEST in test_info.install_locations:
      out_dir = atest_utils.get_product_out()
      testcase_dir = atest_utils.get_target_out_testcases(test_name)
    else:
      out_dir = atest_utils.get_host_out()
      testcase_dir = atest_utils.get_host_out_testcases(test_name)

    logging.debug('Replacing %s with artifacts from AB.', testcase_dir)
    self._symlink_testcases_dir(testcase_dir, test_name)

    for path in self._mod_info.get_installed_paths(test_name):
      if not path.is_relative_to(out_dir) or path.is_relative_to(testcase_dir):
        continue
      self._symlink_installed_file(path, out_dir, test_name)

  def _cleanup(self) -> None:
    for symlink in self._symlinks:
      logging.debug('Cleanup: unlink %s', symlink)
      symlink.unlink(missing_ok=True)
    for backup, target in self._backup_to_original_paths.items():
      logging.debug('Cleanup: mv %s -> %s', backup, target)
      shutil.move(backup, target)
    shutil.rmtree(self._swap_dir)

  def _symlink_testcases_dir(self, target_dir: pathlib.Path, test_name: str):
    """Symlinks the testcases directory to a downloaded directory."""
    source_dir = _find_downloaded_testcases_dir(self._cache_dir, test_name)
    if not source_dir:
      raise CrossBranchArtifactError(
          f'Unable to find the downloaded testcases directory for {test_name}.'
      )
    if target_dir.exists():
      test_dir = self._swap_dir / 'testcases'
      test_dir.mkdir(parents=True)
      logging.debug('Backup: mv %s -> %s', target_dir, test_dir)
      backup_dir = shutil.move(target_dir, test_dir)
      self._backup_to_original_paths[backup_dir] = target_dir
    logging.debug('Symlink %s -> %s', target_dir, source_dir)
    target_dir.symlink_to(source_dir)
    self._symlinks.append(target_dir)

  def _symlink_installed_file(
      self, target_file: pathlib.Path, out_dir: pathlib.Path, test_name: str
  ):
    """Symlinks the installed file to a downloaded file."""
    if target_file.exists():
      relative_path = target_file.relative_to(out_dir)
      swap_file = self._swap_dir / relative_path
      swap_file.parent.mkdir(parents=True, exist_ok=True)
      logging.debug(
          'Backup: mv installed files %s -> %s', target_file, swap_file
      )
      shutil.move(target_file, swap_file)
      self._backup_to_original_paths[swap_file] = target_file
    else:
      target_file.parent.mkdir(parents=True, exist_ok=True)
    source_file = self._find_downloaded_installed_files(test_name, target_file)
    if source_file:
      logging.debug(
          'Symlink installed files %s -> %s', target_file, source_file
      )
      target_file.symlink_to(source_file)
      self._symlinks.append(target_file)

  def _find_downloaded_installed_files(
      self, test_name: str, installed_path: pathlib.Path
  ) -> pathlib.Path:
    """Finds the downloaded file with the given test name and installed path."""
    # If the installed file is in a 64-bit directory, find the downloaded file
    # in relevant directories (e.g. nativetest64/arm64/x86_64)
    if _ARCH_64_DIR_PATTERN in str(installed_path):
      file_filter = lambda p: _ARCH_64_DIR_PATTERN in str(p)
    else:
      file_filter = lambda p: _ARCH_64_DIR_PATTERN not in str(p)
    # If the installed file is in a test directory, search the file with the
    # relative path. Otherwise directly search the file name.
    parts = str(installed_path).split(f'/{test_name}/', 1)
    pattern = (
        f'{test_name}/**/{parts[1]}'
        if len(parts) == 2
        else f'{test_name}/**/{installed_path.name}'
    )
    # Find the shallowest matched file
    matched_files = sorted(
        [
            path
            for path in self._cache_dir.rglob(pattern=pattern)
            if file_filter(path.relative_to(self._cache_dir))
        ],
        key=lambda p: len(str(p).split('/')),
    )
    if not matched_files:
      logging.warning(
          'Unable to find the downloaded file for %s with pattern "%s".',
          installed_path,
          pattern,
      )
      return None
    if len(matched_files) > 1:
      logging.warning(
          (
              'Found mutilple downloaded files for %s with pattern "%s",'
              ' only the first (shallowest) one will be returned:\n- %s'
          ),
          installed_path,
          pattern,
          '\n- '.join([str(file) for file in matched_files]),
      )
    return matched_files[0]


def fetch_artifacts(
    test_infos: Sequence[TestInfo],
    build_target: str,
    branch: str | None = None,
    build_id: str | None = None,
) -> bool:
  """Fetches artifacts for TestInfos from Android Build."""
  if not _is_fetch_artifact_available():
    return False

  try:
    root_dir = _prepare_cache_dir(build_target, branch, build_id)
  except CrossBranchArtifactError as e:
    atest_utils.print_and_log_error(e)
    return False

  done = set()
  for test_info in test_infos:
    if test_info.raw_test_name in done:
      continue
    done.add(test_info.raw_test_name)

    testcases_dir = _find_downloaded_testcases_dir(
        root_dir, test_info.raw_test_name
    )
    if testcases_dir:
      atest_utils.print_and_log_info(
          'Found downloaded caches for %s at %s, skip downloading.',
          test_info.raw_test_name,
          testcases_dir,
      )
      continue

    atest_utils.print_and_log_info(
        'Fetching %s with fetch_artifact', test_info.raw_test_name
    )
    suite_name = _get_test_suite_name(test_info.compatibility_suites)
    if not suite_name:
      atest_utils.print_and_log_error(
          (
              'No supported suite for %s, supported: %s.'
              ' Unable to download test artifacts from Android Build.'
          )
          % (test_info.raw_test_name, _SUPPORTED_SUITES)
      )
      return False

    start_time = time.time()
    try:
      batches = itertools.batched(
          _list_artifacts(
              test_info.raw_test_name,
              suite_name,
              build_target,
              branch,
              build_id,
          ),
          _MAX_ZIP_ENTRY_BATCH,
      )
      failed_files = _fetch_parallel(
          batches, str(root_dir), suite_name, build_target, branch, build_id
      )
      if failed_files:
        # Attempt to fetch each item individually.
        # This can resolve issues caused by empty files in the batch.
        failed_files = _fetch_parallel(
            ((file,) for file in failed_files),
            str(root_dir),
            suite_name,
            build_target,
            branch,
            build_id,
        )
      if failed_files:
        atest_utils.print_and_log_warning(
            'Failed to fetch files:\n'
            f'{"\n".join(failed_files)}\n'
            'This may be due to the files being empty. Testing will proceed.'
        )
      testcases_dir = _find_downloaded_testcases_dir(
          root_dir, test_info.raw_test_name
      )
      if not testcases_dir:
        atest_utils.print_and_log_error(
            'Failed to download artifacts for %s', test_info.raw_test_name
        )
        return False
      _chmod_executables(testcases_dir)
      end_time = time.time()
      atest_utils.print_and_log_info(
          f'Finished all fetch_artifact commands for {test_info.raw_test_name}'
          f' in {end_time - start_time:.2f} seconds.'
      )
    except subprocess.CalledProcessError as e:
      atest_utils.print_and_log_error(e)
      if e.stdout:
        atest_utils.print_and_log_error(_decode_subprocess_err(e.stdout))
      return False

  return True


def _is_fetch_artifact_available() -> bool:
  """Checks whether fetch_artifact is available."""
  cmd = (_FETCH_ARTIFACT_BIN, '--version')
  try:
    proc = subprocess.run(cmd, check=True, text=True, capture_output=True)
    logging.debug('fetch_artifact info:\n%s', proc.stdout)
    return True
  except (subprocess.CalledProcessError, OSError) as e:
    atest_utils.print_and_log_error(
        'fetch_artifact is unavailable.'
        ' Make sure gcert credentials are up to date: %s',
        e,
    )
    return False


def _prepare_cache_dir(
    build_target: str,
    branch: str | None = None,
    build_id: str | None = None,
) -> pathlib.Path:
  """Prepares the cache directory for a build and clears outdated caches."""
  pathlib.Path(_CACHE_DIR).mkdir(parents=True, exist_ok=True)
  if not build_id or build_id == '0':
    cmd = [_FETCH_ARTIFACT_BIN]
    cmd.extend(_get_build_args(build_target, branch, build_id))
    cmd.append(_BUILD_INFO_FILE)
    cmd.append(_CACHE_DIR)
    proc = subprocess.run(
        cmd,
        text=True,
        check=False,
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
    )
    build_info = pathlib.Path(_CACHE_DIR, _BUILD_INFO_FILE)
    if not build_info.exists():
      err_msg = (
          f'Failed to get build info on ({build_target}, {branch}, {build_id}).'
      )
      if proc.stdout:
        err_msg += '\n' + _decode_subprocess_err(proc.stdout)
      raise CrossBranchArtifactError(err_msg)
    with open(build_info, 'r', encoding='utf-8') as f:
      try:
        build_id = json.load(f)['bid']
      except (json.JSONDecodeError, KeyError) as e:
        raise CrossBranchArtifactError(
            f'Invalid build info {build_info}.'
        ) from e
    build_info.unlink()
  build_dir = pathlib.Path(_CACHE_DIR, build_id)
  if not build_dir.exists():
    # Clear caches to keep only 1 build
    shutil.rmtree(_CACHE_DIR)
  cache_dir = build_dir / build_target
  cache_dir.mkdir(parents=True, exist_ok=True)
  return cache_dir


def _find_downloaded_testcases_dir(
    root_dir: pathlib.Path, test_name: str
) -> pathlib.Path:
  return next(root_dir.rglob(pattern=f'testcases/{test_name}/'), None)


def _get_test_suite_name(compatibility_suites: Sequence[str]) -> str | None:
  filtered_suites = [
      suite_tag
      for suite_tag in compatibility_suites
      if suite_tag in _SUPPORTED_SUITES
  ]
  if not filtered_suites:
    return None
  suite_tag = filtered_suites[0]
  if suite_tag == 'cts-v-host':
    return 'android-cts-verifier.zip'
  return f'android-{suite_tag}.zip'


def _list_artifacts(
    module_name: str,
    suite_name: str,
    build_target: str,
    branch: str | None = None,
    build_id: str | None = None,
) -> Iterator[str]:
  """Lists zip entries in a suite."""
  cmd = [_FETCH_ARTIFACT_BIN, '--list_zip_entries']
  cmd.extend(_get_build_args(build_target, branch, build_id))
  cmd.append(suite_name)
  module_dir = f'testcases/{module_name}'
  with subprocess.Popen(
      cmd,
      text=True,
      bufsize=1,
      stderr=subprocess.PIPE,
      stdout=subprocess.PIPE,
  ) as proc:
    for line in proc.stdout:
      entry = line.strip()
      if not entry.endswith('/') and module_dir in entry:
        yield entry
    return_code = proc.wait()
    if return_code:
      raise subprocess.CalledProcessError(
          proc.returncode, cmd, proc.stderr.read()
      )


def _get_build_args(
    build_target: str,
    branch: str | None = None,
    build_id: str | None = None,
):
  """Gets build related args for fetch_artifact."""
  args = ['--target', build_target]
  if branch:
    args.extend(('--branch', branch))
  if build_id:
    args.extend(('--bid', build_id))
  else:
    args.append('--latest')
  return args


def _fetch_parallel(
    batches: Iterator[Tuple[str, ...]],
    target_dir: str,
    suite_name: str,
    build_target: str,
    branch: str | None = None,
    build_id: str | None = None,
):
  """Fetches batches of files parallelly."""
  success_num = 0
  failed_files = []
  with concurrent.futures.ThreadPoolExecutor(
      max_workers=_MAX_WORKERS
  ) as executor:
    future_to_files = {
        executor.submit(
            _fetch,
            batch,
            target_dir,
            suite_name,
            build_target,
            branch,
            build_id,
        ): batch
        for batch in batches
    }

    for future in concurrent.futures.as_completed(future_to_files):
      files = future_to_files[future]
      try:
        future.result()
        success_num += len(files)
      except subprocess.CalledProcessError:
        failed_files.extend(files)

  logging.info(
      'Fetch artifacts: success: %d; fail: %d', success_num, len(failed_files)
  )

  return failed_files


def _fetch(
    files: Tuple[str, ...],
    target_dir: str,
    suite_name: str,
    build_target: str,
    branch: str | None = None,
    build_id: str | None = None,
):
  """Fetches files with one command."""
  cmd = [_FETCH_ARTIFACT_BIN]
  cmd.extend(_get_build_args(build_target, branch, build_id))
  for file in files:
    cmd.append('--zip_entry')
    cmd.append(file)
  cmd.append(suite_name)
  cmd.append(target_dir)
  subprocess.run(
      cmd,
      check=True,
      text=True,
      stderr=subprocess.STDOUT,
      stdout=subprocess.PIPE,
  )


def _chmod_executables(root_dir: pathlib.Path):
  for dir_path, _, file_names in root_dir.walk():
    for file_name in file_names:
      file_path = dir_path / file_name
      if file_path.suffix in _EXECUTABLE_SUFFIXES:
        file_path.chmod(0o755)  # rwxr-xr-x


def _decode_subprocess_err(err: str):
  return err.replace('\\n', '\n').replace('\\t', '\t')
