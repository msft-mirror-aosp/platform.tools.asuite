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
import logging
import pathlib
import shutil
import subprocess
import time
from typing import Iterator, Sequence, Tuple

from atest import atest_utils
from atest.test_finders.test_info import TestInfo


_CACHE_DIR = '/tmp/atest_artifact/cache'
_FETCH_ARTIFACT_BIN = '/google/data/ro/projects/android/fetch_artifact'
_EXECUTABLE_SUFFIXES = frozenset(('', '.sh'))
_SUPPORTED_SUITES = frozenset(('cts', 'cts-v-host', 'vts'))
_MAX_WORKERS = 128
_MAX_ZIP_ENTRY_BATCH = 3


def fetch_artifacts(
    test_infos: Sequence[TestInfo],
    build_target: str,
    branch: str | None = None,
    build_id: str | None = None,
) -> bool:
  """Fetches artifacts for TestInfos from Android Build."""
  if not _is_fetch_artifact_available():
    return False

  pathlib.Path(_CACHE_DIR).mkdir(parents=True, exist_ok=True)

  done = set()
  for test_info in test_infos:
    if test_info.raw_test_name in done:
      continue
    done.add(test_info.raw_test_name)

    atest_utils.print_and_log_info(
        'Fetching %s with fetch_artifact', test_info.raw_test_name
    )
    # TODO(b/390161000): support cache for downloaded files
    testcases_dir = _find_downloaded_testcases_dir(test_info.raw_test_name)
    if testcases_dir:
      shutil.rmtree(testcases_dir)

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
          batches, _CACHE_DIR, suite_name, build_target, branch, build_id
      )
      if failed_files:
        # Attempt to fetch each item individually.
        # This can resolve issues caused by empty files in the batch.
        failed_files = _fetch_parallel(
            ((file,) for file in failed_files),
            _CACHE_DIR,
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
      testcases_dir = _find_downloaded_testcases_dir(test_info.raw_test_name)
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


def _find_downloaded_testcases_dir(test_name: str) -> pathlib.Path:
  return next(
      pathlib.Path(_CACHE_DIR).rglob(pattern=f'testcases/{test_name}/'), None
  )


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
