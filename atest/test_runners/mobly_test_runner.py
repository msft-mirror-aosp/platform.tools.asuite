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

"""Mobly test runner."""
import dataclasses
import datetime
import json
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
from typing import Any

import yaml

from atest import atest_configs
from atest import atest_enum
from atest import atest_utils
from atest import constants
from atest import result_reporter
from atest.test_finders import test_info
from atest.test_runners import test_runner_base


_ERROR_TEST_FILE_NOT_FOUND = (
    'Required test file %s not found. If this is your first run, please ensure '
    'that the build step is performed.')
_ERROR_NO_MOBLY_TEST_PKG = (
    'No Mobly test package found. Ensure that the Mobly test module is '
    'correctly configured.')
_ERROR_NO_TEST_SUMMARY = 'No Mobly test summary found.'
_ERROR_INVALID_TEST_SUMMARY = (
    'Invalid Mobly test summary. Make sure that it contains a final "Summary" '
    'section.')

# TODO(b/287136126): Use host python once compatibility issue is resolved.
PYTHON_EXECUTABLE = 'python3.10'

FILE_REQUIREMENTS_TXT = 'requirements.txt'
FILE_SUFFIX_APK = '.apk'

CONFIG_KEY_TESTBEDS = 'TestBeds'
CONFIG_KEY_NAME = 'Name'
CONFIG_KEY_CONTROLLERS = 'Controllers'
CONFIG_KEY_ANDROID_DEVICE = 'AndroidDevice'
CONFIG_KEY_MOBLY_PARAMS = 'MoblyParams'
CONFIG_KEY_LOG_PATH = 'LogPath'
LOCAL_TESTBED = 'LocalTestBed'
MOBLY_LOGS_DIR = 'mobly_logs'
CONFIG_FILE = 'mobly_config.json'
LATEST_DIR = 'latest'
TEST_SUMMARY_YAML = 'test_summary.yaml'

SUMMARY_KEY_TYPE = 'Type'
SUMMARY_TYPE_RECORD = 'Record'
SUMMARY_KEY_TEST_CLASS = 'Test Class'
SUMMARY_KEY_TEST_NAME = 'Test Name'
SUMMARY_KEY_BEGIN_TIME = 'Begin Time'
SUMMARY_KEY_END_TIME = 'End Time'
SUMMARY_KEY_RESULT = 'Result'
SUMMARY_RESULT_PASS = 'PASS'
SUMMARY_RESULT_FAIL = 'FAIL'
SUMMARY_RESULT_SKIP = 'SKIP'
SUMMARY_RESULT_ERROR = 'ERROR'
SUMMARY_KEY_STACKTRACE = 'Stacktrace'

MOBLY_RESULT_TO_STATUS = {
    SUMMARY_RESULT_PASS: test_runner_base.PASSED_STATUS,
    SUMMARY_RESULT_FAIL: test_runner_base.FAILED_STATUS,
    SUMMARY_RESULT_SKIP: test_runner_base.IGNORED_STATUS,
    SUMMARY_RESULT_ERROR: test_runner_base.FAILED_STATUS
}


@dataclasses.dataclass
class MoblyTestFiles:
    """Data class representing required files for a Mobly test."""
    mobly_pkg: str
    requirements_txt: str | None
    test_apks: list[str]


class MoblyTestRunnerError(Exception):
    """Errors encountered by the MoblyTestRunner."""


class MoblyTestRunner(test_runner_base.TestRunnerBase):
    """Mobly test runner class."""
    NAME: str = 'MoblyTestRunner'
    # Unused placeholder value. Mobly tests will be run from Python virtualenv
    EXECUTABLE: str = '.'

    # Temporary files and directories used by the runner.
    _temppaths: list[str] = []

    def run_tests(
            self, test_infos: list[test_info.TestInfo],
            extra_args: dict[str, Any],
            reporter: result_reporter.ResultReporter) -> int:
        """Run the list of test_infos.

        Should contain code for kicking off the test runs using
        test_runner_base.run(). Results should be processed and printed
        via the reporter passed in.

        Args:
            test_infos: List of TestInfo.
            extra_args: Dict of extra args to add to test run.
            reporter: An instance of result_report.ResultReporter.

        Returns:
            0 if tests succeed, non-zero otherwise.
        """
        ret_code = atest_enum.ExitCode.SUCCESS
        for tinfo in test_infos:
            logging.debug('Running Mobly test %s.', tinfo.test_name)
            try:
                # Pre-test setup
                test_files = self._get_test_files(tinfo)
                venv_executable = self._setup_python_virtualenv(
                    test_files.requirements_txt)
                serials = atest_configs.GLOBAL_ARGS.serial
                if constants.DISABLE_INSTALL not in extra_args:
                    self._install_apks(test_files.test_apks, serials)
                mobly_config = self._generate_mobly_config(serials)

                # Generate command and run
                mobly_command = self._get_mobly_command(
                    venv_executable, test_files.mobly_pkg, mobly_config)
                ret_code |= self._run_mobly_command(mobly_command)

                # Process results from generated summary file
                summary_file = os.path.join(self.results_dir, MOBLY_LOGS_DIR,
                                            LOCAL_TESTBED, LATEST_DIR,
                                            TEST_SUMMARY_YAML)
                test_results = self._get_test_results_from_summary(
                    summary_file, tinfo)
                for test_result in test_results:
                    reporter.process_test_result(test_result)
            finally:
                self._cleanup()
        return ret_code

    def host_env_check(self) -> None:
        """Checks that host env has met requirements."""

    def get_test_runner_build_reqs(
            self, test_infos: list[test_info.TestInfo]) -> set[str]:
        """Returns a set of build targets required by the test runner."""
        build_targets = set()
        build_targets.update(test_runner_base.gather_build_targets(test_infos))
        return build_targets

    # pylint: disable=unused-argument
    def generate_run_commands(
            self, test_infos: list[test_info.TestInfo],
            extra_args: dict[str, Any], _port: int | None = None) -> list[str]:
        """Generate a list of run commands from TestInfos.

        Args:
            test_infos: A set of TestInfo instances.
            extra_args: A Dict of extra args to append.
            _port: Unused.

        Returns:
            A list of run commands to run the tests.
        """
        # TODO: to be implemented
        return []

    def _get_test_files(self, tinfo: test_info.TestInfo) -> MoblyTestFiles:
        """Get test resource files from a given TestInfo."""
        mobly_pkg = None
        requirements_txt = None
        test_apks = []
        logging.debug('Getting test resource files for %s', tinfo.test_name)
        for path in tinfo.data.get(constants.MODULE_INSTALLED):
            path_str = str(path.expanduser().absolute())
            if not path.is_file():
                raise MoblyTestRunnerError(
                    _ERROR_TEST_FILE_NOT_FOUND % path_str)
            if path.name == tinfo.test_name:
                mobly_pkg = path_str
            elif path.name == FILE_REQUIREMENTS_TXT:
                requirements_txt = path_str
            elif path.suffix == FILE_SUFFIX_APK:
                test_apks.append(path_str)
            else:
                continue
            logging.debug('Found test resource file %s.', path_str)
        if mobly_pkg is None:
            raise MoblyTestRunnerError(_ERROR_NO_MOBLY_TEST_PKG)
        return MoblyTestFiles(mobly_pkg, requirements_txt, test_apks)

    def _generate_mobly_config(self, serials: list[str] | None) -> str:
        """Create a Mobly YAML config given the test parameters.

        If --serial is specified, the test will use those specific devices,
        otherwise it will use all ADB-connected devices.

        Also set the Mobly results dir to <atest_results>/mobly_logs.

        Args:
            serials: List of device serials, or None.

        Returns:
            Path to the generated config.
        """
        config = {
            CONFIG_KEY_TESTBEDS: [{
                CONFIG_KEY_NAME: LOCAL_TESTBED,
                CONFIG_KEY_CONTROLLERS: {
                    CONFIG_KEY_ANDROID_DEVICE: serials if serials else '*',
                },
            }],
            CONFIG_KEY_MOBLY_PARAMS: {
                CONFIG_KEY_LOG_PATH: os.path.join(
                    self.results_dir, MOBLY_LOGS_DIR),
            },
        }
        config_path = os.path.join(self.results_dir, CONFIG_FILE)
        logging.debug('Generating Mobly config at %s', config_path)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f)
        return config_path

    def _setup_python_virtualenv(self, requirements_txt: str | None) -> str:
        """Create a Python virtual environment and set up dependencies.

        Args:
            requirements_txt: Path to the requirements.txt file, where the PyPI
                dependencies are declared. None if no such file exists.

        Returns:
            Path to the virtualenv's Python executable.
        """
        venv_dir = tempfile.mkdtemp(prefix='venv_')
        logging.debug('Creating virtualenv at %s.', venv_dir)
        subprocess.check_call([PYTHON_EXECUTABLE, '-m', 'venv', venv_dir])
        self._temppaths.append(venv_dir)
        venv_executable = os.path.join(venv_dir, 'bin', 'python')

        # Install requirements
        if requirements_txt:
            logging.debug('Installing dependencies from %s.', requirements_txt)
            cmd = [venv_executable, '-m', 'pip', 'install', '-r',
                   requirements_txt]
            subprocess.check_call(cmd)

        return venv_executable

    def _install_apks(self, apks: list[str], serials: list[str] | None) -> None:
        """Install test APKs to devices.

        This can be toggled off by omitting the --install option.

        If --serial is specified, the APK will be installed to those specific
        devices, otherwise it will install to all ADB-connected devices.

        Args:
            apks: List of APK paths.
            serials: List of device serials, or None.
        """
        serials = serials or atest_utils.get_adb_devices()
        for apk in apks:
            for serial in serials:
                logging.debug('Installing APK %s to device %s.', apk, serial)
                subprocess.check_call(
                    ['adb', '-s', serial, 'install', '-r', '-g', apk])

    def _get_mobly_command(self, py_executable: str, mobly_pkg: str,
                           config_path: str) -> list[str]:
        """Generate a single Mobly test command.

        Args:
            py_executable: Path to the Python executable.
            mobly_pkg: Path to the Mobly test package.
            config_path: Path to the Mobly config.

        Returns:
            The full Mobly test command.
        """
        return [py_executable, mobly_pkg, '-c', config_path]

    def _run_mobly_command(self, mobly_cmd: list[str]) -> int:
        """Run the Mobly test command.

        Args:
            mobly_cmd: Mobly command to run.

        Returns:
            Return code of the Mobly command.
        """
        proc = self.run(
            shlex.join(mobly_cmd),
            output_to_stdout=bool(atest_configs.GLOBAL_ARGS.verbose))
        return self.wait_for_subprocess(proc)

    def _get_test_results_from_summary(
            self,
            summary_file: str,
            tinfo: test_info.TestInfo) -> list[test_runner_base.TestResult]:
        """Parse the Mobly summary file into ATest TestResults."""
        if not os.path.isfile(summary_file):
            raise MoblyTestRunnerError(_ERROR_NO_TEST_SUMMARY)

        # Find and parse 'Summary' section
        logging.debug('Processing results from summary file %s.', summary_file)
        with open(summary_file, 'r', encoding='utf-8') as f:
            summary = list(yaml.safe_load_all(f))

        # Populate TestResults
        test_results = []
        records = [entry for entry in summary
                   if entry[SUMMARY_KEY_TYPE] == SUMMARY_TYPE_RECORD]
        test_count = 0
        for record in records:
            test_count += 1
            time_elapsed_ms = 0
            if (record.get(SUMMARY_KEY_END_TIME) is not None
                    and record.get(SUMMARY_KEY_BEGIN_TIME) is not None):
                time_elapsed_ms = (record[SUMMARY_KEY_END_TIME] -
                                   record[SUMMARY_KEY_BEGIN_TIME])
            result = {
                'runner_name': self.NAME,
                'group_name': tinfo.test_name,
                'test_run_name': record[SUMMARY_KEY_TEST_CLASS],
                'test_name': '%s.%s' % (record[SUMMARY_KEY_TEST_CLASS],
                                        record[SUMMARY_KEY_TEST_NAME]),
                'status': MOBLY_RESULT_TO_STATUS.get(
                    record[SUMMARY_KEY_RESULT], test_runner_base.ERROR_STATUS),
                'details': record[SUMMARY_KEY_STACKTRACE],
                'test_count': test_count,
                'group_total': len(records),
                'test_time': str(
                    datetime.timedelta(milliseconds=time_elapsed_ms)),
                # Below values are unused
                'runner_total': None,
                'additional_info': {},
            }
            test_results.append(test_runner_base.TestResult(**result))
        return test_results

    def _cleanup(self) -> None:
        """Clean up temporary host files/directories."""
        logging.debug('Cleaning up temporary dirs/files.')
        for temppath in self._temppaths:
            if os.path.isdir(temppath):
                shutil.rmtree(temppath)
            else:
                os.remove(temppath)
        self._temppaths.clear()