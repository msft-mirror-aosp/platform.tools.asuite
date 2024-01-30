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

"""Base test module for Atest integration tests."""
import concurrent.futures
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any

import split_build_test_script

# Exporting for test modules' typing reference
SplitBuildTestScript = split_build_test_script.SplitBuildTestScript
StepInput = split_build_test_script.StepInput
StepOutput = split_build_test_script.StepOutput

# Printed before the html log line. Defined in atest/atest_utils.py.
_HTML_LOG_PRINT_PREFIX = 'To access logs, press "ctrl" and click on'


class LogEntry:
    """Represents a single log entry."""

    def __init__(self, log_line: str):
        """Initializes a LogEntry object from a logging line.

        Args:
            log_line: The logging line to parse.
        """
        self._log_line = log_line
        self._regex = (
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.+?):(\d+):(\w+): (.*)'
        )
        match = re.match(self._regex, log_line)
        if match:
            self._timestamp_string = match.group(1)
            self._source_file_name = match.group(2)
            self._source_file_line_number = int(match.group(3))
            self._log_level = match.group(4)
            self._content = match.group(5)
        else:
            raise ValueError('Invalid log line format.')

    def get_log_line(self) -> str:
        """Returns the raw log line used to parse the log entry."""
        return self._log_line

    def get_timestamp(self) -> float:
        """Returns the timestamp of the log entry as an epoch time."""
        return time.mktime(
            time.strptime(self._timestamp_string, '%Y-%m-%d %H:%M:%S')
        )

    def get_timestamp_string(self) -> str:
        """Returns the timestamp of the log entry as a string."""
        return self._timestamp_string

    def get_source_file_name(self) -> str:
        """Returns the source file name of the log entry."""
        return self._source_file_name

    def get_source_file_line_number(self) -> int:
        """Returns the source file line number of the log entry."""
        return self._source_file_line_number

    def get_log_level(self) -> str:
        """Returns the log level of the log entry."""
        return self._log_level

    def get_content(self) -> str:
        """Returns the content of the log entry."""
        return self._content


class AtestRunResult:
    """A class to store Atest run result and get detailed run information."""

    def __init__(
        self,
        completed_process: subprocess.CompletedProcess,
        env: dict[str, str],
        repo_root: str,
        config: split_build_test_script.IntegrationTestConfiguration,
    ):
        self._completed_process = completed_process
        self._env = env
        self._repo_root = repo_root
        self._config = config

    def get_returncode(self) -> int:
        """Returns the return code of the completed process."""
        return self._completed_process.returncode

    def get_stdout(self) -> str:
        """Returns the standard output of the completed process."""
        return self._completed_process.stdout

    def get_stderr(self) -> str:
        """Returns the standard error of the completed process."""
        return self._completed_process.stderr

    def get_cmd_list(self) -> list[str]:
        """Returns the command list used in the process run."""
        return self._completed_process.args

    def get_result_root_path(self, snapshot_ready=False) -> Path:
        """Returns the atest result root path.

        Args:
            snapshot_ready: Whether to make the result root directory snapshot
              ready. When set to True and called in build environment, this
              method will copy the path into <repo_root>/out with dereferencing
              so that the directory can be safely added to snapshot.
        """
        stdout_lines = self.get_stdout().splitlines(keepends=False)
        html_line_index = None
        for index, line in enumerate(stdout_lines):
            if line.startswith(_HTML_LOG_PRINT_PREFIX):
                html_line_index = index + 1
                break
        if not html_line_index or html_line_index >= len(stdout_lines):
            if 'bazel-result-reporter-host' in self.get_stdout():
                raise RuntimeError(
                    'Getting result root path in bazel build only mode is not'
                    ' supported yet.'
                )
            raise RuntimeError('Result root path not found in stdout.')
        html_path_search = re.search(
            r'file://(.*)/log/test_logs.html', stdout_lines[html_line_index]
        )
        if not html_path_search:
            raise RuntimeError(
                'Failed to parse the result root path from stdout.'
            )
        result_root_path = Path(html_path_search.group(1))

        if self._config.is_test_env or not snapshot_ready:
            return result_root_path

        result_root_copy_path = Path(self._repo_root).joinpath(
            'out/atest_integration_tests', result_root_path.name
        )
        if not result_root_copy_path.exists():
            shutil.copytree(
                result_root_path, result_root_copy_path, symlinks=False
            )

        return result_root_copy_path

    def get_test_result_dict(self) -> dict[str, Any]:
        """Gets the atest result dictionary loaded from the output json."""
        json_path = self.get_result_root_path() / 'test_result'
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_atest_log_entries(self) -> list[LogEntry]:
        """Gets the parsed atest log entries list from atest log file."""
        log_path = self.get_result_root_path() / 'atest.log'
        lines = log_path.read_text(encoding='utf-8').splitlines()
        return [LogEntry(line) for line in lines if line]

    def check_returncode(self) -> None:
        """Checks the return code and raises an exception if non-zero."""

        def add_line_prefix(msg: str):
            return (
                ''.join(
                    ('> %s' % line for line in msg.splitlines(keepends=True))
                )
                if msg
                else msg
            )

        stderr = (
            f'stderr:\n{add_line_prefix(self.get_stderr())}\n'
            if self.get_stderr() and self.get_stderr().strip()
            else ''
        )

        if self.get_returncode() != 0:
            raise RuntimeError(
                f'Atest command {self.get_cmd_list()} finished with exit code'
                f' {self.get_returncode()}.\n'
                f'stdout:\n{add_line_prefix(self.get_stdout())}\n{stderr}'
            )

    def get_local_reproduce_debug_cmd(self) -> str:
        """Returns a full reproduce command for local debugging purpose.

        Returns:
            A command that can be executed directly in command line to
            reproduce the atest command.
        """
        return '(cd {dir} && {env} {cmd})'.format(
            dir=self._repo_root,
            env=' '.join((k + '=' + v for k, v in self._env.items())),
            cmd=' '.join(self.get_cmd_list()),
        )


class AtestTestCase(split_build_test_script.SplitBuildTestTestCase):
    """Base test case for build-test environment split integration tests."""

    # Default include list of repo paths for snapshot
    _default_snapshot_include_paths = [
        'out/host/linux-x86',
        'out/target/product/*/module-info*',
        'out/target/product/*/testcases',
        'out/target/product/*/data',
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
        'prebuilts/asuite/atest/linux-x86/atest-py3',
    ]

    # Default exclude list of repo paths for snapshot
    _default_snapshot_exclude_paths = [
        'out/host/linux-x86/bin/go',
        'out/host/linux-x86/bin/soong_build',
        'out/host/linux-x86/obj',
    ]

    # Default list of environment variables to take and restore in snapshots
    _default_snapshot_env_keys = [
        split_build_test_script.ANDROID_BUILD_TOP_KEY,
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

    def create_atest_script(self) -> SplitBuildTestScript:
        """Create an instance of atest integration test utility."""
        script = self.create_split_build_test_script()
        script.add_snapshot_restore_exclude_paths(['out/atest_bazel_workspace'])
        return script

    def create_step_output(self) -> StepOutput:
        """Create a step output object with default values."""
        out = StepOutput()
        out.add_snapshot_include_paths(self._default_snapshot_include_paths)
        out.add_snapshot_exclude_paths(self._default_snapshot_exclude_paths)
        out.add_snapshot_env_keys(self._default_snapshot_env_keys)
        out.add_snapshot_include_paths(self._get_jdk_path_list())
        return out

    def run_atest_command(
        self,
        cmd: str,
        step_in: split_build_test_script.StepInput,
        print_output: bool = True,
        use_prebuilt_atest_binary=None,
    ) -> AtestRunResult:
        """Run either `atest-dev` or `atest` command through subprocess.

        Args:
            cmd: command string for Atest. Do not add 'atest-dev' or 'atest' in
              the beginning of the command.
            step_in: The step input object from build or test step.
            print_output: Whether to print the stdout and stderr while the
              command is running.
            use_prebuilt_atest_binary: Whether to run the command using the
              prebuilt atest binary instead of the atest-dev binary.

        Returns:
            An AtestRunResult object containing the run information.
        """
        if use_prebuilt_atest_binary is None:
            use_prebuilt_atest_binary = (
                step_in.get_config().use_prebuilt_atest_binary
            )
        complete_cmd = (
            f'{"atest" if use_prebuilt_atest_binary else "atest-dev"}'
            f' {cmd}{step_in.get_device_serial_args_or_empty()}'
        )

        return AtestRunResult(
            self._run_shell_command(
                complete_cmd.split(),
                env=step_in.get_env(),
                cwd=step_in.get_repo_root(),
                print_output=print_output,
            ),
            step_in.get_env(),
            step_in.get_repo_root(),
            step_in.get_config(),
        )

    def _run_shell_command(
        self,
        cmd: list[str],
        env: dict[str, str],
        cwd: str,
        print_output: bool = True,
    ) -> subprocess.CompletedProcess:
        """Execute shell command with real time output printing and capture."""

        def read_output(read_src, print_dst, capture_dst):
            while (output := read_src.readline()) or process.poll() is None:
                if output:
                    if print_output:
                        print(output, end='', file=print_dst)
                    capture_dst.append(output)

        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            cwd=cwd,
        ) as process:
            stdout = []
            stderr = []
            with concurrent.futures.ThreadPoolExecutor() as executor:
                stdout_future = executor.submit(
                    read_output, process.stdout, sys.stdout, stdout
                )
                stderr_future = executor.submit(
                    read_output, process.stderr, sys.stderr, stderr
                )
            stdout_future.result()
            stderr_future.result()

            return subprocess.CompletedProcess(
                cmd, process.poll(), ''.join(stdout), ''.join(stderr)
            )

    def _get_jdk_path_list(self) -> str:
        """Get the relative jdk directory in build environment."""
        if split_build_test_script.ANDROID_BUILD_TOP_KEY not in os.environ:
            return []
        absolute_path = Path(os.environ['ANDROID_JAVA_HOME'])
        while not absolute_path.name.startswith('jdk'):
            absolute_path = absolute_path.parent
        if not absolute_path.name.startswith('jdk'):
            raise ValueError(
                'Unrecognized jdk directory ' + os.environ['ANDROID_JAVA_HOME']
            )
        repo_root = Path(
            os.environ[split_build_test_script.ANDROID_BUILD_TOP_KEY]
        )
        return [absolute_path.relative_to(repo_root).as_posix()]


def main():
    """Main method to run the integration tests."""

    def argparser_update_func(parser):
        parser.add_argument(
            '--use-prebuilt-atest-binary',
            action='store_true',
            default=False,
            help=(
                'Set the default atest binary to the prebuilt `atest` instead'
                ' of `atest-dev`.'
            ),
        )

    def config_update_function(config, args):
        config.use_prebuilt_atest_binary = args.use_prebuilt_atest_binary

    split_build_test_script.main(
        argv=sys.argv,
        make_before_build=['atest'],
        argparser_update_func=argparser_update_func,
        config_update_function=config_update_function,
    )
