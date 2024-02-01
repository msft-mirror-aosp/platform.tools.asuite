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

ASUITE_HOME = pathlib.Path(__file__).resolve().parent


def run_legacy_unittests(files):
  """Run unittests for asuite_plugin.

  Args:
      files: a list of files.

  Returns:
      True if subprocess.check_call() returns 0.
  """
  print(ASUITE_HOME)
  asuite_plugin_path = ASUITE_HOME.joinpath('asuite_plugin').as_posix()
  gradel_test = '/gradlew test'
  cmd_dict = {}
  for f in files:
    if 'asuite_plugin' in f:
      cmd = asuite_plugin_path + gradel_test
      cmd_dict.update({cmd: asuite_plugin_path})
  try:
    for cmd, path in cmd_dict.items():
      subprocess.check_call(shlex.split(cmd), cwd=path)
  except subprocess.CalledProcessError as error:
    print('Unit test failed at:\n\n{}'.format(error.output))
    raise


def get_preupload_files():
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
  return files_to_upload


if __name__ == '__main__':
  preupload_files = get_preupload_files()
  run_legacy_unittests(preupload_files)
