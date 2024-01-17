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

"""Module to facilitate integration test within the build and test environment.

This module provides utilities for running tests in both build and test
environments, managing environment variables, and snapshotting the workspace for
restoration later.
"""

import argparse
import atexit
from concurrent.futures import ThreadPoolExecutor
import copy
import multiprocessing
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import Any, Dict, List
import unittest

from snapshot import Snapshot

# Env key for the storage tar path.
SNAPSHOT_STORAGE_TAR_KEY = 'SNAPSHOT_STORAGE_TAR_PATH'

# Relative path to the repo root for storing the snapshots and workspace
_INTEGRATION_TEST_OUT_DIR_REL_PATH = 'out/atest_integration_tests'

# Env key for the repo root
_ANDROID_BUILD_TOP_KEY = 'ANDROID_BUILD_TOP'


class AtestTestCase(unittest.TestCase):
    """Base test case for build-test environment split integration tests."""

    injected_config = None

    def create_atest_integration_test(self):
        """Create an instance of atest integration test utility."""
        return AtestIntegrationTest(self.id(), self.injected_config)


class _IntegrationTestConfiguration:
    """Internal class to store integration test configuration."""

    device_serial: str = None
    is_build_env: bool = False
    is_test_env: bool = False
    is_device_serial_required = True
    snapshot_storage_path: Path = None
    snapshot_storage_tar_path: Path = None
    workspace_path: Path = None


class AtestIntegrationTest:
    """Utility for running integration test in build and test environment."""

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

    _default_restore_exclude_paths = ['out/atest_bazel_workspace']

    _default_env_keys = [
        _ANDROID_BUILD_TOP_KEY,
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

    def __init__(
        self, name: str, config: _IntegrationTestConfiguration
    ) -> None:
        self._config = config
        self._include_paths: List[str] = self._default_include_paths
        self._exclude_paths: List[str] = self._default_exclude_paths
        self._env_keys: List[str] = self._default_env_keys
        self._id: str = name
        self._env: Dict[str, str] = None
        self._snapshot: Snapshot = Snapshot(self._config.snapshot_storage_path)
        self._add_jdk_to_include_path()
        self._snapshot_count = 0

    def _add_jdk_to_include_path(self) -> None:
        """Get the relative jdk directory in build environment."""
        if self._config.is_test_env:
            return
        absolute_path = Path(os.environ['ANDROID_JAVA_HOME'])
        while not absolute_path.name.startswith('jdk'):
            absolute_path = absolute_path.parent
        if not absolute_path.name.startswith('jdk'):
            raise ValueError(
                'Unrecognized jdk directory ' + os.environ['ANDROID_JAVA_HOME']
            )
        repo_root = Path(os.environ[_ANDROID_BUILD_TOP_KEY])
        self._include_paths.append(
            absolute_path.relative_to(repo_root).as_posix()
        )

    def add_snapshot_include_paths(self, *paths: str) -> None:
        """Add paths to include in snapshot artifacts."""
        self._include_paths.extend(paths)

    def set_snapshot_include_paths(self, *paths: str) -> None:
        """Set the snapshot include paths.

        Note that the default include paths will be removed.
        Use add_snapshot_include_paths if that's not intended.
        """
        self._include_paths.clear()
        self._include_paths.extend(paths)

    def add_snapshot_exclude_paths(self, *paths: str) -> None:
        """Add paths to exclude from snapshot artifacts."""
        self._exclude_paths.extend(paths)

    def add_env_keys(self, *keys: str) -> None:
        """Add environment variable keys for snapshot."""
        self._env_keys.extend(keys)

    def take_snapshot(self, name: str) -> None:
        """Take a snapshot of the repository and environment."""
        self._snapshot.take_snapshot(
            name,
            self.get_repo_root(),
            self._include_paths,
            self._exclude_paths,
            self._env_keys,
        )

    def restore_snapshot(self, name: str) -> None:
        """Restore the repository and environment from a snapshot."""
        self._env = self._snapshot.restore_snapshot(
            name,
            self._config.workspace_path.as_posix(),
            exclude_paths=self._default_restore_exclude_paths,
        )

    def in_build_env(self) -> bool:
        """Whether to executes test codes written for build environment only."""
        return self._config.is_build_env

    def in_test_env(self) -> bool:
        """Whether to executes test codes written for test environment only."""

        if self._config.is_build_env:
            self.take_snapshot(self._id + '_' + str(self._snapshot_count))
            self._snapshot_count += 1
        if self._config.is_test_env:
            self.restore_snapshot(self._id + '_' + str(self._snapshot_count))
            self._snapshot_count += 1
        return self._config.is_test_env

    def get_env(self) -> Dict[str, str]:
        """Get environment variables."""
        if self._config.is_build_env:
            return os.environ.copy()
        return self._env

    def get_device_serial(self) -> str:
        """Returns the serial of the connected device. Throws if not set."""
        if not self._config.device_serial:
            raise RuntimeError('Device serial is not set')
        return self._config.device_serial

    def get_device_serial_args_or_empty(self) -> str:
        """Gets atest arguments for device serial. May return empty string."""
        if self._config.device_serial:
            return ' -s ' + self._config.device_serial
        if self._config.is_device_serial_required:
            raise RuntimeError('Device serial is required but not set')
        return ''

    def get_repo_root(self) -> str:
        """Get repo root directory."""
        if self._config.is_build_env:
            return os.environ[_ANDROID_BUILD_TOP_KEY]
        return self._env[_ANDROID_BUILD_TOP_KEY]


class _FileCompressor:
    """Class for compressing and decompressing files."""

    def compress_all_sub_files(self, root_path: Path) -> None:
        """Compresses all files in the given directory and subdirectories.

        Args:
            root_path: Path to the root directory.
        """
        cpu_count = multiprocessing.cpu_count()
        with ThreadPoolExecutor(max_workers=cpu_count) as executor:
            for file_path in root_path.rglob('*'):
                if file_path.is_file():
                    executor.submit(self.compress_file, file_path)

    def compress_file(self, file_path: Path) -> None:
        """Compresses a single file using tarfile.

        Args:
            file_path: Path to the file to compress.
        """
        with tarfile.open(file_path.with_suffix('.bz2'), 'w:bz2') as tar:
            tar.add(file_path, arcname=file_path.name)
        file_path.unlink()

    def decompress_all_sub_files(self, root_path: Path) -> None:
        """Decompresses all compressed sub files in the given directory.

        Args:
            root_path: Path to the root directory.
        """
        cpu_count = multiprocessing.cpu_count()
        with ThreadPoolExecutor(max_workers=cpu_count) as executor:
            for file_path in root_path.rglob('*.bz2'):
                executor.submit(self.decompress_file, file_path)

    def decompress_file(self, file_path: Path) -> None:
        """Decompresses a single file using tarfile.

        Args:
            file_path: Path to the compressed file.
        """
        with tarfile.open(file_path, 'r:bz2') as tar:
            tar.extractall(file_path.parent)
        file_path.unlink()


def parse_known_args(argv: list[str]) -> tuple[argparse.Namespace, List[str]]:
    """Parse command line args and check required args being provided."""

    description = """A script to build and/or run the Atest integration tests.
Usage examples:
   python <script_path>: Runs both the build and test steps.
   python <script_path> -b -t: Runs both the build and test steps.
   python <script_path> -b: Runs only the build steps.
   python <script_path> -t: Runs only the test steps.
"""

    parser = argparse.ArgumentParser(
        add_help=True,
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '-b',
        '--build',
        action='store_true',
        default=False,
        help=(
            'Run build steps. Can be set to true together with the test option.'
            ' If both build and test are unset, will run both steps.'
        ),
    )
    parser.add_argument(
        '-t',
        '--test',
        action='store_true',
        default=False,
        help=(
            'Run test steps. Can be set to true together with the build option.'
            ' If both build and test are unset, will run both steps.'
        ),
    )

    # The below flags are passed in by the TF Python test runner.
    parser.add_argument(
        '-s',
        '--serial',
        help=(
            'The device serial. Required in test mode when ANDROID_BUILD_TOP is'
            ' not set.'
        ),
    )
    parser.add_argument(
        '--test-output-file',
        help=(
            'The file in which to store the unit test results. This option is'
            ' usually set by TradeFed when running the script with python and'
            ' is optional during manual script execution.'
        ),
    )

    return parser.parse_known_args(argv)


def run_test(
    config: _IntegrationTestConfiguration,
    argv: list[str],
    test_output_file_path: str = None,
) -> None:
    """Execute integration tests with given test configuration."""

    if config.is_test_env and not config.snapshot_storage_tar_path.exists():
        raise EnvironmentError(
            f'Snapshot tar {config.snapshot_storage_tar_path} does not exist.'
        )

    compressor = _FileCompressor()

    def cleanup() -> None:
        if config.workspace_path.exists():
            shutil.rmtree(config.workspace_path)
        if config.snapshot_storage_path.exists():
            shutil.rmtree(config.snapshot_storage_path)

    if config.is_test_env:
        with tarfile.open(config.snapshot_storage_tar_path, 'r') as tar:
            tar.extractall(config.snapshot_storage_path.parent.as_posix())
        print('Decompressing the snapshot storage...')
        compressor.decompress_all_sub_files(config.snapshot_storage_path)
        atexit.register(cleanup)

    def unittest_main(stream=None):
        # Note that we use a type and not an instance for 'testRunner'
        # since TestProgram forwards its constructor arguments when creating
        # an instance of the runner type. Not doing so would require us to
        # make sure that the parameters passed to TestProgram are aligned
        # with those for creating a runner instance.
        class TestRunner(unittest.TextTestRunner):
            """Writes test results to the TF-provided file."""

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(stream=stream, *args, **kwargs)

        class TestLoader(unittest.TestLoader):
            """Injects the test configuration to the test classes."""

            def __init__(self, config: _IntegrationTestConfiguration):
                super().__init__()
                self._config = config

            def loadTestsFromTestCase(self, *args, **kwargs):
                tests = super().loadTestsFromTestCase(*args, **kwargs)
                # pylint: disable=protected-access
                for test in tests._tests:
                    test.injected_config = self._config
                return tests

        # Setting verbosity is required to generate output that the TradeFed
        # test runner can parse.
        unittest.main(
            testRunner=TestRunner,
            verbosity=3,
            argv=argv,
            testLoader=TestLoader(config),
            exit=config.is_test_env,
        )

    if test_output_file_path:
        Path(test_output_file_path).parent.mkdir(exist_ok=True)

        with open(
            test_output_file_path, 'w', encoding='utf-8'
        ) as test_output_file:
            unittest_main(stream=test_output_file)
    else:
        unittest_main(stream=None)

    if config.is_build_env:
        print('Compressing the snapshot storage...')
        compressor.compress_all_sub_files(config.snapshot_storage_path)
        with tarfile.open(config.snapshot_storage_tar_path, 'w') as tar:
            tar.add(
                config.snapshot_storage_path,
                arcname=config.snapshot_storage_path.name,
            )
        cleanup()


def main() -> None:
    """Main method to start the integration tests."""

    args, unittest_argv = parse_known_args(sys.argv)

    print(f'The os environ is: {os.environ}')

    snapshot_storage_dir_name = 'snapshot_storage'
    snapshot_storage_tar_name = 'snapshot.tar'

    if _ANDROID_BUILD_TOP_KEY in os.environ:
        integration_test_out_path = Path(
            os.environ[_ANDROID_BUILD_TOP_KEY]
        ).joinpath(_INTEGRATION_TEST_OUT_DIR_REL_PATH)
        integration_test_out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        # pylint: disable=consider-using-with
        integration_test_out_path = Path(tempfile.TemporaryDirectory().name)

    if SNAPSHOT_STORAGE_TAR_KEY in os.environ:
        snapshot_storage_tar_path = Path(os.environ[SNAPSHOT_STORAGE_TAR_KEY])
        snapshot_storage_tar_path.parent.mkdir(parents=True, exist_ok=True)
    elif _ANDROID_BUILD_TOP_KEY in os.environ:
        snapshot_storage_tar_path = integration_test_out_path.joinpath(
            snapshot_storage_tar_name
        )
    else:
        raise EnvironmentError(
            'Cannot determine snapshot storage tar path. Try set the'
            f' {SNAPSHOT_STORAGE_TAR_KEY} environment value.'
        )

    # When the build or test is unset, assume it's a local run for both build
    # and test steps.
    is_build_test_unset = not args.build and not args.test
    config = _IntegrationTestConfiguration()
    config.is_build_env = args.build or is_build_test_unset
    config.is_test_env = args.test or is_build_test_unset
    config.device_serial = args.serial
    config.snapshot_storage_path = integration_test_out_path.joinpath(
        snapshot_storage_dir_name
    )
    config.snapshot_storage_tar_path = snapshot_storage_tar_path
    config.workspace_path = integration_test_out_path.joinpath('workspace')
    # Device serial is not required during local run, and
    # _ANDROID_BUILD_TOP_KEY env being available implies it's local run.
    config.is_device_serial_required = not _ANDROID_BUILD_TOP_KEY in os.environ

    if config.is_build_env:
        if _ANDROID_BUILD_TOP_KEY not in os.environ:
            raise EnvironmentError(
                f'Environment variable {_ANDROID_BUILD_TOP_KEY} is required to'
                ' build the integration test.'
            )

        subprocess.check_call(
            'build/soong/soong_ui.bash --make-mode atest'.split(),
            cwd=os.environ[_ANDROID_BUILD_TOP_KEY],
        )

    if config.is_build_env ^ config.is_test_env:
        run_test(config, unittest_argv, args.test_output_file)
        return

    build_config = copy.deepcopy(config)
    build_config.is_test_env = False

    test_config = copy.deepcopy(config)
    test_config.is_build_env = False

    run_test(build_config, unittest_argv, args.test_output_file)
    run_test(test_config, unittest_argv, args.test_output_file)
