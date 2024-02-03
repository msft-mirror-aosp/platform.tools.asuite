#!/usr/bin/env python3
# Copyright 2019, The Android Open Source Project
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

"""Run at preupload hook to perform necessary checks and formatting."""

import argparse
import pathlib
import shlex
import subprocess
import sys

ASUITE_HOME = pathlib.Path(__file__).resolve().parent


def check_run_shell_command(cmd: str, cwd: str = None) -> None:
  """Run a shell command and raise error if failed."""
  if subprocess.run(shlex.split(cmd), cwd=cwd, check=False).returncode:
    print('Preupload files did not pass Asuite preupload hook script.')
    sys.exit(1)


def run_pylint(files: list[pathlib.Path]) -> None:
  """Run pylint on python files."""
  for file in files:
    if file.suffix != '.py':
      continue
    check_run_shell_command('pylint ' + file.as_posix(), ASUITE_HOME.as_posix())


def run_gpylint(files: list[pathlib.Path]) -> None:
  """Run gpylint on python files if gpylint is available."""
  if subprocess.run(
      shlex.split('which gpylint'),
      check=False,
  ).returncode:
    print('gpylint not available. Will use pylint instead.')
    run_pylint(files)
    return

  has_format_issue = False
  for file in files:
    if file.suffix != '.py':
      continue
    if subprocess.run(
        shlex.split('gpylint ' + file.as_posix()), check=False
    ).returncode:
      has_format_issue = True
  if has_format_issue:
    sys.exit(1)


def run_pyformat(files: list[pathlib.Path]) -> None:
  """Run pyformat on certain projects."""
  if subprocess.run(
      shlex.split('which pyformat'),
      check=False,
  ).returncode:
    print('pyformat not available. Will skip auto formatting.')
    return

  need_reformat = False
  for file in files:
    if not need_reformat:
      completed_process = subprocess.run(
          shlex.split('pyformat --force_quote_type single ' + file.as_posix()),
          capture_output=True,
          check=False,
      )
      if completed_process.stdout:
        need_reformat = True

    if need_reformat:
      subprocess.run(
          shlex.split(
              'pyformat -i --force_quote_type single ' + file.as_posix()
          ),
          check=False,
      )

  if need_reformat:
    print(
        'Reformatting completed. Please add the modified files to git and rerun'
        ' the repo preupload hook.'
    )
    sys.exit(1)


def run_legacy_unittests() -> None:
  """Run unittests for asuite_plugin."""
  asuite_plugin_path = ASUITE_HOME.joinpath('asuite_plugin').as_posix()
  check_run_shell_command(
      f'{asuite_plugin_path}/gradlew test', asuite_plugin_path
  )


def filter_files_for_projects(
    files: list[pathlib.Path], projects: list[str], root_files: bool
) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
  """Filter a list of files according to project names.

  Args:
      files: list of files to filter.
      projects: list of project names to match, e.g. ['atest'].
      root_files: whether to treat files under the asuite root directory as
        matched files.

  Returns:
      A tuple of a list of files matching the projects and a list of files not
      matching the projects.
  """
  matched_files = []
  not_matched_files = []
  project_paths = [
      ASUITE_HOME.joinpath(project).resolve().as_posix() for project in projects
  ]
  for file in files:
    if file.as_posix().startswith(tuple(project_paths)):
      matched_files.append(file)
    elif root_files and file.parent == ASUITE_HOME:
      matched_files.append(file)
    else:
      not_matched_files.append(file)

  return matched_files, not_matched_files


def get_preupload_files() -> list[pathlib.Path]:
  """Get the list of files to be uploaded."""
  parser = argparse.ArgumentParser()
  parser.add_argument('preupload_files', nargs='*', help='Files to upload.')
  args = parser.parse_args()
  files_to_upload = args.preupload_files
  if not files_to_upload:
    # When running by users directly, only consider:
    # added(A), renamed(R) and modified(M) files
    # and store them in files_to_upload.
    cmd = "git status --short | egrep [ARM] | awk '{print $NF}'"
    files_to_upload = subprocess.check_output(
        cmd, shell=True, encoding='utf-8'
    ).splitlines()
    if files_to_upload:
      print('Modified files: %s' % files_to_upload)
  file_paths_to_upload = [
      pathlib.Path(file).resolve() for file in files_to_upload
  ]
  return [file for file in file_paths_to_upload if file.exists()]


if __name__ == '__main__':
  preupload_files = get_preupload_files()

  gpylint_project_files, other_files = filter_files_for_projects(
      preupload_files, ['atest'], root_files=True
  )
  run_pylint(other_files)
  run_pyformat(gpylint_project_files)
  run_gpylint(gpylint_project_files)

  asuite_plugin_files, _ = filter_files_for_projects(
      preupload_files, ['asuite_plugin'], root_files=False
  )
  if asuite_plugin_files:
    run_legacy_unittests()
