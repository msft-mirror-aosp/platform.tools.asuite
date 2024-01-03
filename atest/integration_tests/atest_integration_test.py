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

"""Module to facilitate integration testing within the Android build and test environments.

This module provides utilities for running tests in both build and test
environments, managing environment variables, and snapshotting the workspace for
restoration later.
"""

import argparse
import atexit
import glob
import inspect
import os
from pathlib import Path
import shutil
import sys
import tarfile
from typing import Any, Dict, List, Sequence, Text
import unittest

from snapshot import Snapshot


# Export the TestCase class to reduce the number of imports tests have to list.
TestCase: unittest.TestCase = unittest.TestCase

_DEVICE_SERIAL: Text = None
_IS_BUILD_ENV: bool = False
_IS_TEST_ENV: bool = False
_ARTIFACTS_DIR: Path = None
_ARTIFACT_PACK_PATH: Path = None
_DEFAULT_ARTIFACT_PATH_FILE_NAME = 'atest_integration_tests.tar'
_SNAPSHOT_STORAGE_DIR_NAME = 'ATEST_INTEGRATION_TESTS_SNAPSHOT_STORAGE'


class AtestIntegrationTest:
  """Utility class for running atest integration test in build and test environment."""

  _default_include_paths = [
      'out/host/linux-x86',
      'out/target/product/*/module-info*',
      'out/target/product/*/testcases',
      'out/target/product/*/all_modules.txt',
      'out/soong/module_bp*',
      'tools/asuite/atest/test_runners/roboleaf_launched.txt',
      '.repo/manifest.xml',
      'build/soong/soong_ui.bash',
      'build/bazel_common_rules/rules/python/stubs',
      'build/bazel/bin',
      'external/bazelbuild-rules_java',
      'tools/asuite/atest/bazel/resources/bazel.sh',
      'prebuilts/bazel/linux-x86_64',
      'prebuilts/build-tools/path/linux-x86/python3',
      'prebuilts/build-tools/linux-x86/bin/py3-cmd',
      'prebuilts/build-tools',
  ]

  _default_exclude_paths = [
      'out/host/linux-x86/bin/go',
      'out/host/linux-x86/bin/soong_build',
      'out/host/linux-x86/obj',
  ]

  _default_env_keys = [
      'ANDROID_BUILD_TOP',
      'ANDROID_HOST_OUT',
      'ANDROID_PRODUCT_OUT',
      'ANDROID_HOST_OUT_TESTCASES',
      'ANDROID_TARGET_OUT_TESTCASES',
      'OUT',
      'PATH',
      'HOST_OUT_TESTCASES',
      'ANDROID_JAVA_HOME',
      'JAVA_HOME',
  ]

  def __init__(self, id: Text) -> None:
    self._include_paths: List[str] = self._default_include_paths
    self._exclude_paths: List[str] = self._default_exclude_paths
    self._env_keys: List[str] = self._default_env_keys
    self._id: Text = id
    self._env: Dict[Text, Text] = None
    self._snapshot: Snapshot = Snapshot(_get_snapshot_storage_path())
    self._add_jdk_to_include_path()
    self._snapshot_count = 0

  def _add_jdk_to_include_path(self) -> None:
    """Get the relative jdk directory in build env."""
    if is_in_test_env():
      return
    absolute_path = Path(os.environ['ANDROID_JAVA_HOME'])
    while not absolute_path.name.startswith('jdk'):
      absolute_path = absolute_path.parent
    if not absolute_path.name.startswith('jdk'):
      raise ValueError(
          'Unrecognized jdk directory ' + os.environ['ANDROID_JAVA_HOME']
      )
    repo_root = Path(os.environ['ANDROID_BUILD_TOP'])
    self._include_paths.append(absolute_path.relative_to(repo_root).as_posix())

  def add_artifact_paths(self, *paths: str) -> None:
    """Add paths to include in snapshot artifacts."""
    self._include_paths.extend(paths)

  def add_artifact_exclude_paths(self, *paths: str) -> None:
    """Add paths to exclude from snapshot artifacts."""
    self._exclude_paths.extend(paths)

  def add_env_keys(self, *keys: str) -> None:
    """Add environment variable keys for snapshot."""
    self._env_set_keys.extend(keys)

  def take_snapshot(self, name: str) -> None:
    self._snapshot.take_snapshot(
        name,
        self.get_repo_root(),
        self._include_paths,
        self._exclude_paths,
        self._env_keys,
    )

  def restore_snapshot(self, name: str) -> None:
    self._env = self._snapshot.restore_snapshot(
        name, _get_workspace_dir().as_posix()
    )

  def in_build_env(self) -> bool:
    """Whether to executes test codes written for build environment only."""
    return is_in_build_env()

  def in_test_env(self) -> bool:
    """Whether to executes test codes written for test environment only."""

    if is_in_build_env():
      self.take_snapshot(self._id + '_' + str(self._snapshot_count))
      self._snapshot_count += 1
    if is_in_test_env():
      self.restore_snapshot(self._id + '_' + str(self._snapshot_count))
      self._snapshot_count += 1
    return is_in_test_env()

  def get_env(self) -> Dict[Text, Text]:
    """Get environment variables."""
    if is_in_build_env():
      return os.environ.copy()
    return self._env

  def get_device_serial(self) -> Text:
    """Returns the serial of the connected device."""
    if not _DEVICE_SERIAL:
      raise RuntimeError('device serial is not set')
    return _DEVICE_SERIAL

  def get_repo_root(self) -> str:
    """Get repo root directory."""
    if is_in_build_env():
      return os.environ['ANDROID_BUILD_TOP']
    return self._env['ANDROID_BUILD_TOP']

  def _get_caller_name(self) -> str:
    """Get name of calling function."""
    current_stack_frame = inspect.stack()[2]
    calling_class = current_stack_frame.frame.f_locals['self'].__class__
    return (
        calling_class.__name__
        + '_'
        + inspect.currentframe().f_back.f_back.f_code.co_name
    )


def is_in_build_env() -> bool:
  """Check if we are in the build env."""
  return _IS_BUILD_ENV


def is_in_test_env() -> bool:
  """Check if we are in the test env."""
  return _IS_TEST_ENV


def _get_artifacts_path(*sub_paths: str) -> Path:
  """Get the output directory."""
  return Path(_ARTIFACTS_DIR, *sub_paths)


def _get_snapshot_storage_path() -> Path:
  return _get_artifacts_path(_SNAPSHOT_STORAGE_DIR_NAME)


def _get_workspace_dir() -> Path:
  """Get the directory for restoring the repo files."""
  # TODO use temp dir after the prototype is verified in pipeline
  return _get_artifacts_path('workspace')


def _process_artifacts() -> None:
  """Pack artifacts into a tarball and clean up."""
  if is_in_build_env():
    with tarfile.open(_ARTIFACT_PACK_PATH.as_posix(), 'w') as tar:
      tar.add(
          _get_snapshot_storage_path(),
          arcname=_get_snapshot_storage_path().relative_to(
              _get_artifacts_path().as_posix()
          ),
      )
  shutil.rmtree(_get_snapshot_storage_path())


def _unpack_artifacts() -> None:
  """Unpack artifacts from a tarball."""
  with tarfile.open(_ARTIFACT_PACK_PATH.as_posix(), 'r') as tar:
    tar.extractall(_get_artifacts_path().as_posix())


def create_arg_parser(add_help: bool = False) -> argparse.ArgumentParser:
  """Creates a new parser that can handle the default command-line flags.

  The object returned by this function can be used by other modules that want to
  add their own command-line flags. The returned parser is intended to be passed
  to the 'parents' argument of ArgumentParser and extend the set of default
  flags with additional ones.

  Args:
      add_help: whether to add an option which simply displays the parser’s help
        message; this is typically false when used from other modules that want
        to use the returned parser as a parent argument parser.

  Returns:
      A new arg parser that can handle the default flags expected by this
      module.
  """

  parser = argparse.ArgumentParser(add_help=add_help)

  parser.add_argument(
      '-b',
      '--build',
      action='store_true',
      default=False,
      help='Run in a build environment.',
  )
  parser.add_argument(
      '-t',
      '--test',
      action='store_true',
      default=False,
      help='Run in a test environment.',
  )
  parser.add_argument(
      '--artifacts_dir',
      help='directory where test artifacts are saved',
  )
  parser.add_argument(
      '--artifact_pack_path', help='path to the artifact pack file'
  )

  # The below flags are passed in by the TF Python test runner.
  parser.add_argument('-s', '--serial', help='the device serial')
  parser.add_argument(
      '--test-output-file',
      help='the file in which to store the test results',
  )

  return parser


def run_tests(args: Any, unittest_argv: Sequence[Text]) -> None:
  """Executes atest integration test cases.

  This function unpacks the artifacts before running the tests if in a test
  environment, and packs the artifacts after running the tests if in a build
  environment.

  Args:
    args: an object that contains at least the set of attributes defined in
      objects returned when using the default argument parser.
    unittest_argv: the list of command-line arguments to forward to
      unittest.main.
  """
  Path(_ARTIFACTS_DIR).mkdir(parents=True, exist_ok=True)

  if is_in_test_env():
    _unpack_artifacts()

  def execute_after_tests() -> None:
    # Code to execute after unittest.main()
    if _get_workspace_dir().exists():
      shutil.rmtree(_get_workspace_dir())
    _process_artifacts()

  atexit.register(execute_after_tests)

  if args.test_output_file:
    Path(args.test_output_file).parent.mkdir(exist_ok=True)

    with open(args.test_output_file, 'w') as test_output_file:
      # Note that we use a type and not an instance for 'testRunner' since
      # TestProgram forwards its constructor arguments when creating an instance
      # of the runner type. Not doing so would require us to make sure that the
      # parameters passed to TestProgram are aligned with those for creating a
      # runner instance.
      class TestRunner(unittest.TextTestRunner):
        """A test runner that writes test results to the TF-provided file."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
          super().__init__(stream=test_output_file, *args, **kwargs)

      # Setting verbosity is required to generate output that the TradeFed test
      # runner can parse.
      unittest.TestProgram(
          verbosity=3, testRunner=TestRunner, argv=unittest_argv
      )
  else:
    unittest.main(argv=unittest_argv, verbosity=2)


def main() -> None:
  """Executes a set of Python unit tests."""
  global _DEVICE_SERIAL, _ARTIFACTS_DIR, _IS_BUILD_ENV, _IS_TEST_ENV, _ARTIFACT_PACK_PATH
  parser = create_arg_parser(add_help=True)
  args, unittest_argv = parser.parse_known_args(sys.argv)

  print(f'The os environ is: {os.environ}')

  if args.build and args.test:
    parser.error('running build and test env together is not supported yet')
  if not args.build and not args.test:
    parser.error('must specify to run either in build or test env')
  if args.build and not args.artifacts_dir:
    parser.error('running in build env requires artifacts_dir be set')
  if args.test and not args.artifact_pack_path:
    parser.error('running in test env requires artifact_pack_path be set')

  _IS_BUILD_ENV = args.build
  _IS_TEST_ENV = args.test
  _DEVICE_SERIAL = args.serial
  _ARTIFACTS_DIR = (
      Path(args.artifacts_dir)
      if args.artifacts_dir
      else Path(args.artifact_pack_path).parent
  )
  _ARTIFACT_PACK_PATH = (
      Path(args.artifact_pack_path)
      if args.artifact_pack_path
      else _ARTIFACTS_DIR.joinpath(_DEFAULT_ARTIFACT_PATH_FILE_NAME)
  )

  run_tests(args, unittest_argv)
