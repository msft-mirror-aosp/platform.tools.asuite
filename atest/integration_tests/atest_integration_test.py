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
import logging
import os
import pathlib
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
run_in_parallel = split_build_test_script.ParallelTestRunner.run_in_parallel
setup_parallel_in_build_env = (
    split_build_test_script.ParallelTestRunner.setup_parallel_in_build_env
)

# Note: The following constants should ideally be imported from their
#       corresponding prod source code, but this makes local execution of the
#       integration test harder due to some special dependencies in the prod
#       code. Therefore we copy the definition here for now in favor of easier
#       local integration test execution. If value changes in the source code
#       breaking the integration test becomes a problem in the future, we can
#       reconsider importing these constants.
# Stdout print prefix for results directory. Defined in atest/atest_main.py
RESULTS_DIR_PRINT_PREFIX = 'Atest results and logs directory: '
DRY_RUN_COMMAND_LOG_PREFIX = 'Internal run command from dry-run: '


class LogEntry:
  """Represents a single log entry."""

  def __init__(
      self,
      timestamp_str,
      src_file_name,
      src_file_line_number,
      log_level,
      content_lines,
  ):
    """Initializes a LogEntry object from a logging line.

    Args:
        timestamp_str: The timestamp header string in each log entry.
        src_file_name: The source file name in the log entry.
        src_file_line_number: The source file line number in the log entry.
        log_level: The log level string in the log entry.
        content_lines: A list of log entry content lines.
    """
    self._timestamp_string = timestamp_str
    self._source_file_name = src_file_name
    self._source_file_line_number = src_file_line_number
    self._log_level = log_level
    self._content_lines = content_lines

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
    return '\n'.join(self._content_lines)


class AtestRunResult:
  """A class to store Atest run result and get detailed run information."""

  def __init__(
      self,
      completed_process: subprocess.CompletedProcess[str],
      env: dict[str, str],
      repo_root: str,
      config: split_build_test_script.IntegrationTestConfiguration,
      elapsed_time: float,
  ):
    self._completed_process = completed_process
    self._env = env
    self._repo_root = repo_root
    self._config = config
    self._elapsed_time = elapsed_time

  def get_elapsed_time(self) -> float:
    """Returns the elapsed time of the atest command execution."""
    return self._elapsed_time

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

  def get_results_dir_path(self, snapshot_ready=False) -> pathlib.Path:
    """Returns the atest results directory path.

    Args:
        snapshot_ready: Whether to make the result root directory snapshot
          ready. When set to True and called in build environment, this method
          will copy the path into <repo_root>/out with dereferencing so that the
          directory can be safely added to snapshot.

    Raises:
        RuntimeError: Failed to parse the result dir path.

    Returns:
        The Atest result directory path.
    """
    results_dir = None
    for line in self.get_stdout().splitlines(keepends=False):
      if line.startswith(RESULTS_DIR_PRINT_PREFIX):
        results_dir = pathlib.Path(line[len(RESULTS_DIR_PRINT_PREFIX) :])
    if not results_dir:
      raise RuntimeError('Failed to parse the result directory from stdout.')

    if self._config.is_test_env or not snapshot_ready:
      return results_dir

    result_dir_copy_path = pathlib.Path(self._env['OUT_DIR']).joinpath(
        'atest_integration_tests', results_dir.name
    )
    if not result_dir_copy_path.exists():
      shutil.copytree(results_dir, result_dir_copy_path, symlinks=False)

    return result_dir_copy_path

  def get_test_result_dict(self) -> dict[str, Any]:
    """Gets the atest results loaded from the test_result json.

    Returns:
        Atest result information loaded from the test_result json file. The test
        result usually contains information about test runners and test
        pass/fail results.
    """
    json_path = self.get_results_dir_path() / 'test_result'
    with open(json_path, 'r', encoding='utf-8') as f:
      return json.load(f)

  def get_passed_count(self) -> int:
    """Gets the total number of passed tests from atest summary."""
    return self.get_test_result_dict()['total_summary']['PASSED']

  def get_failed_count(self) -> int:
    """Gets the total number of failed tests from atest summary."""
    return self.get_test_result_dict()['total_summary']['FAILED']

  def get_ignored_count(self) -> int:
    """Gets the total number of ignored tests from atest summary."""
    return self.get_test_result_dict()['total_summary']['IGNORED']

  def get_atest_log(self) -> str:
    """Gets the log content read from the atest log file."""
    log_path = self.get_results_dir_path() / 'atest.log'
    return log_path.read_text(encoding='utf-8')

  def get_atest_log_entries(self) -> list[LogEntry]:
    """Gets the parsed atest log entries list from the atest log file.

    This method parse the atest log file and construct a new entry when a line
    starts with a time string, source file name, line number, and log level.

    Returns:
      A list of parsed log entries.
    """
    entries = []
    last_content_lines = []
    for line in self.get_atest_log().splitlines():
      regex = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (.+?):(\d+):(\w+): (.*)'
      match = re.match(regex, line)
      if match:
        last_content_lines = [match.group(5)]
        entries.append(
            LogEntry(
                match.group(1),
                match.group(2),
                int(match.group(3)),
                match.group(4),
                last_content_lines,
            )
        )
      else:
        if last_content_lines:
          last_content_lines.append(line)

    return entries

  def get_atest_log_values_from_prefix(self, prefix: str) -> list[str]:
    """Gets log values from lines starting with the given log prefix."""
    res = []
    for entry in self.get_atest_log_entries():
      content = entry.get_content()
      if content.startswith(prefix):
        res.append(content[len(prefix) :])
    return res

  def check_returncode(self) -> None:
    """Checks the return code and raises an exception if non-zero."""

    def add_line_prefix(msg: str):
      return (
          ''.join(('> %s' % line for line in msg.splitlines(keepends=True)))
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

  def setUp(self):
    super().setUp()
    # Default include list of repo paths for snapshot
    self._default_snapshot_include_paths = [
        '$OUT_DIR/host/linux-x86',
        '$OUT_DIR/target/product/*/module-info*',
        '$OUT_DIR/target/product/*/testcases',
        '$OUT_DIR/target/product/*/data',
        '$OUT_DIR/target/product/*/all_modules.txt',
        '$OUT_DIR/soong/module_bp*',
        'tools/asuite/atest/test_runners/roboleaf_launched.txt',
        '.repo/manifest.xml',
        'build/soong/soong_ui.bash',
        'prebuilts/build-tools/path/linux-x86/python3',
        'prebuilts/build-tools/linux-x86/bin/py3-cmd',
        'prebuilts/build-tools',
        'prebuilts/asuite/atest/linux-x86',
    ]

    # Default exclude list of repo paths for snapshot
    self._default_snapshot_exclude_paths = [
        '$OUT_DIR/host/linux-x86/bin/go',
        '$OUT_DIR/host/linux-x86/bin/soong_build',
        '$OUT_DIR/host/linux-x86/obj',
    ]

    # Default list of environment variables to take and restore in snapshots
    self._default_snapshot_env_keys = [
        split_build_test_script.ANDROID_BUILD_TOP_KEY,
        'ANDROID_HOST_OUT',
        'ANDROID_PRODUCT_OUT',
        'ANDROID_HOST_OUT_TESTCASES',
        'ANDROID_TARGET_OUT_TESTCASES',
        'OUT',
        'OUT_DIR',
        'PATH',
        'HOST_OUT_TESTCASES',
        'ANDROID_JAVA_HOME',
        'JAVA_HOME',
    ]

  def create_atest_script(self, name: str = None) -> SplitBuildTestScript:
    """Create an instance of atest integration test utility."""
    return self.create_split_build_test_script(name)

  def create_step_output(self) -> StepOutput:
    """Create a step output object with default values."""
    out = StepOutput()
    out.add_snapshot_include_paths(self._default_snapshot_include_paths)
    out.add_snapshot_exclude_paths(self._default_snapshot_exclude_paths)
    out.add_snapshot_env_keys(self._default_snapshot_env_keys)
    out.add_snapshot_include_paths(self._get_jdk_path_list())
    return out

  @classmethod
  def run_atest_command(
      cls,
      cmd: str,
      step_in: split_build_test_script.StepInput,
      include_device_serial: bool,
      print_output: bool = True,
      use_prebuilt_atest_binary=None,
      pipe_to_stdin: str = None,
  ) -> AtestRunResult:
    """Run either `atest-dev` or `atest` command through subprocess.

    Args:
        cmd: command string for Atest. Do not add 'atest-dev' or 'atest' in the
          beginning of the command.
        step_in: The step input object from build or test step.
        include_device_serial: Whether a device is required for the atest
          command. This argument is only used to determine whether to include
          device serial in the command. It does not add device/deviceless
          arguments such as '--host'.
        print_output: Whether to print the stdout and stderr while the command
          is running.
        use_prebuilt_atest_binary: Whether to run the command using the prebuilt
          atest binary instead of the atest-dev binary.
        pipe_to_stdin: A string value to pipe continuously to the stdin of the
          command subprocess.

    Returns:
        An AtestRunResult object containing the run information.
    """
    if use_prebuilt_atest_binary is None:
      use_prebuilt_atest_binary = step_in.get_config().use_prebuilt_atest_binary
    atest_binary = 'atest' if use_prebuilt_atest_binary else 'atest-dev'

    # TODO: b/336839543 - Throw error here when serial is required but not set
    # instead of from step_in.get_device_serial_args_or_empty()
    serial_arg = (
        step_in.get_device_serial_args_or_empty()
        if include_device_serial
        else ''
    )
    complete_cmd = f'{atest_binary}{serial_arg} {cmd}'

    indentation = '  '
    logging.debug('Executing atest command: %s', complete_cmd)
    logging.debug(
        '%sCommand environment variables: %s', indentation, step_in.get_env()
    )
    start_time = time.time()
    shell_result = cls._run_shell_command(
        complete_cmd.split(),
        env=step_in.get_env(),
        cwd=step_in.get_repo_root(),
        print_output=print_output,
        pipe_to_stdin=pipe_to_stdin,
    )
    elapsed_time = time.time() - start_time
    result = AtestRunResult(
        shell_result,
        step_in.get_env(),
        step_in.get_repo_root(),
        step_in.get_config(),
        elapsed_time,
    )

    wrap_output_lines = lambda output_str: ''.join((
        f'{indentation * 2}> %s' % line for line in output_str.splitlines(True)
    ))
    logging.debug(
        '%sCommand stdout:\n%s',
        indentation,
        wrap_output_lines(result.get_stdout()),
    )
    logging.debug(
        '%sAtest log:\n%s',
        indentation,
        wrap_output_lines(result.get_atest_log()),
    )

    return result

  @staticmethod
  def _run_shell_command(
      cmd: list[str],
      env: dict[str, str],
      cwd: str,
      print_output: bool = True,
      pipe_to_stdin: str = None,
  ) -> subprocess.CompletedProcess[str]:
    """Execute shell command with real time output printing and capture."""

    def read_output(process, read_src, print_dst, capture_dst):
      while (output := read_src.readline()) or process.poll() is None:
        if output:
          if print_output:
            print(output, end='', file=print_dst)
          capture_dst.append(output)

    def run_popen(stdin=None):
      with subprocess.Popen(
          cmd,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,
          stdin=stdin,
          text=True,
          env=env,
          cwd=cwd,
      ) as process:
        stdout = []
        stderr = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
          stdout_future = executor.submit(
              read_output, process, process.stdout, sys.stdout, stdout
          )
          stderr_future = executor.submit(
              read_output, process, process.stderr, sys.stderr, stderr
          )
        stdout_future.result()
        stderr_future.result()

        return subprocess.CompletedProcess(
            cmd, process.poll(), ''.join(stdout), ''.join(stderr)
        )

    if pipe_to_stdin:
      with subprocess.Popen(
          ['yes', pipe_to_stdin], stdout=subprocess.PIPE
      ) as yes_process:
        return run_popen(yes_process.stdout)

    return run_popen()

  @staticmethod
  def _get_jdk_path_list() -> str:
    """Get the relative jdk directory in build environment."""
    if split_build_test_script.ANDROID_BUILD_TOP_KEY not in os.environ:
      return []
    absolute_path = pathlib.Path(os.environ['ANDROID_JAVA_HOME'])
    while not absolute_path.name.startswith('jdk'):
      absolute_path = absolute_path.parent
    if not absolute_path.name.startswith('jdk'):
      raise ValueError(
          'Unrecognized jdk directory ' + os.environ['ANDROID_JAVA_HOME']
      )
    repo_root = pathlib.Path(
        os.environ[split_build_test_script.ANDROID_BUILD_TOP_KEY]
    )
    return [absolute_path.relative_to(repo_root).as_posix()]


def sanitize_runner_command(cmd: str) -> str:
  """Sanitize an atest runner command by removing non-essential args."""
  remove_args_starting_with = [
      '--skip-all-system-status-check',
      '--atest-log-file-path',
      'LD_LIBRARY_PATH=',
      '--proto-output-file=',
      '--log-root-path',
  ]
  remove_args_with_values = ['-s', '--serial']
  build_command = 'build/soong/soong_ui.bash'
  original_args = cmd.split()
  result_args = []
  for arg in original_args:
    if arg == build_command:
      result_args.append(f'./{build_command}')
      continue
    if not any(
        (arg.startswith(prefix) for prefix in remove_args_starting_with)
    ):
      result_args.append(arg)
  for arg in remove_args_with_values:
    while arg in result_args:
      idx = result_args.index(arg)
      # Delete value index first.
      del result_args[idx + 1]
      del result_args[idx]

  return ' '.join(result_args)


def main():
  """Main method to run the integration tests."""
  additional_args = [
      split_build_test_script.AddArgument(
          'use_prebuilt_atest_binary',
          '--use-prebuilt-atest-binary',
          action='store_true',
          default=False,
          help=(
              'Set the default atest binary to the prebuilt `atest` instead'
              ' of `atest-dev`.'
          ),
      ),
      split_build_test_script.AddArgument(
          'dry_run_diff_test_cmd_input_file',
          '--dry-run-diff-test-cmd-input-file',
          help=(
              'The path of file containing the list of atest commands to test'
              ' in the dry run diff tests relative to the repo root.'
          ),
      ),
  ]
  split_build_test_script.main(
      argv=sys.argv,
      make_before_build=['atest'],
      additional_args=additional_args,
  )
