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
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys

import split_build_test_script

# Exporting for test modules' typing reference
SplitBuildTestScript = split_build_test_script.SplitBuildTestScript
StepInput = split_build_test_script.StepInput
StepOutput = split_build_test_script.StepOutput


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

    def check_returncode(self) -> None:
        """Checks the return code and raises an exception if non-zero."""
        self._completed_process.check_returncode()

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
        script = self.create_split_build_test_script(self.id())
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

    def run_atest_dev(
        self,
        cmd: str,
        step_in: split_build_test_script.StepInput,
        print_output: bool = True,
    ) -> AtestRunResult:
        """Run an atest-dev command through subprocess.

        Args:
            cmd: command string for Atest. Do not add 'atest-dev' or 'atest' in
              the beginning of the command.
            step_in: The step input object from build or test step.
            print_output: Whether to print the stdout and stderr while the
              command is running.

        Returns:
            An AtestRunResult object containing the run information.
        """
        complete_cmd = (
            'atest-dev ' + cmd + step_in.get_device_serial_args_or_empty()
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

        def read_stdout(process, stdout):
            while output := process.stdout.readline() or process.poll() is None:
                if print_output:
                    print(output, end='', file=sys.stdout)
                stdout.append(output)

        def read_stderr(process, stderr):
            while output := process.stderr.readline() or process.poll() is None:
                if print_output:
                    print(output, end='', file=sys.stdout)
                stderr.append(output)

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
            stdout_reading_process = multiprocessing.Process(
                target=read_stdout, args=(process, stdout)
            )
            stderr_reading_process = multiprocessing.Process(
                target=read_stderr, args=(process, stderr)
            )
            stdout_reading_process.start()
            stderr_reading_process.start()
            stdout_reading_process.join()
            stderr_reading_process.join()
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
    split_build_test_script.main(make_before_build=['atest'])
