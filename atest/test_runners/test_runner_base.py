# Copyright 2017, The Android Open Source Project
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

"""
Base test runner class.

Class that other test runners will instantiate for test runners.
"""

from __future__ import print_function

import errno
import logging
import signal
import subprocess
import tempfile
import os

from collections import namedtuple
from typing import Any, Dict, List, Set

from atest import atest_error
from atest import atest_utils
from atest import device_update
from atest.test_finders import test_info
from atest.test_runner_invocation import TestRunnerInvocation

OLD_OUTPUT_ENV_VAR = 'ATEST_OLD_OUTPUT'

# TestResult contains information of individual tests during a test run.
TestResult = namedtuple('TestResult', ['runner_name', 'group_name',
                                       'test_name', 'status', 'details',
                                       'test_count', 'test_time',
                                       'runner_total', 'group_total',
                                       'additional_info', 'test_run_name'])
ASSUMPTION_FAILED = 'ASSUMPTION_FAILED'
FAILED_STATUS = 'FAILED'
PASSED_STATUS = 'PASSED'
IGNORED_STATUS = 'IGNORED'
ERROR_STATUS = 'ERROR'

# Code for RunnerFinishEvent.
RESULT_CODE = {PASSED_STATUS: 0,
               FAILED_STATUS: 1,
               IGNORED_STATUS: 2,
               ASSUMPTION_FAILED: 3,
               ERROR_STATUS: 4}


class TestRunnerBase:
    """Base Test Runner class."""
    NAME = ''
    EXECUTABLE = ''

    def __init__(self, results_dir, **kwargs):
        """Init stuff for base class."""
        self.results_dir = results_dir
        self.test_log_file = None
        if not self.NAME:
            raise atest_error.NoTestRunnerName('Class var NAME is not defined.')
        if not self.EXECUTABLE:
            raise atest_error.NoTestRunnerExecutable('Class var EXECUTABLE is '
                                                     'not defined.')
        if kwargs:
            for key, value in kwargs.items():
                if not 'test_infos' in key:
                    logging.debug('Found auxiliary args: %s=%s',
                                  key, value)

    def create_invocations(
        self,
        extra_args: Dict[str, Any],
        test_infos: List[test_info.TestInfo],
        update_device: bool,
    ) -> List[TestRunnerInvocation]:
        """Creates test runner invocations.

        Args:
            extra_args: A dict of arguments.
            test_infos: A list of instances of TestInfo.
            update_device: Specifies whether a device update is required.

        Returns:
            A list of TestRunnerInvocation instances.
        """
        update_method = (device_update.AdeviceUpdateMethod() if update_device
                         else device_update.NoopUpdateMethod())

        return [TestRunnerInvocation(
            test_runner=self,
            extra_args=extra_args,
            test_infos=test_infos,
            update_method=update_method)]

    def run(self, cmd, output_to_stdout=False, env_vars=None):
        """Shell out and execute command.

        Args:
            cmd: A string of the command to execute.
            output_to_stdout: A boolean. If False, the raw output of the run
                              command will not be seen in the terminal. This
                              is the default behavior, since the test_runner's
                              run_tests() method should use atest's
                              result reporter to print the test results.

                              Set to True to see the output of the cmd. This
                              would be appropriate for verbose runs.
            env_vars: Environment variables passed to the subprocess.
        """
        if not output_to_stdout:
            self.test_log_file = tempfile.NamedTemporaryFile(
                mode='w', dir=self.results_dir, delete=True)
        logging.debug('Executing command: %s', cmd)
        return subprocess.Popen(cmd, start_new_session=True, shell=True,
                                stderr=subprocess.STDOUT,
                                stdout=self.test_log_file, env=env_vars)

    # pylint: disable=broad-except
    def handle_subprocess(self, subproc, func):
        """Execute the function. Interrupt the subproc when exception occurs.

        Args:
            subproc: A subprocess to be terminated.
            func: A function to be run.
        """
        try:
            signal.signal(signal.SIGINT, self._signal_passer(subproc))
            func()
        except Exception as error:
            # exc_info=1 tells logging to log the stacktrace
            logging.debug('Caught exception:', exc_info=1)
            # If atest crashes, try to kill subproc group as well.
            try:
                logging.debug('Killing subproc: %s', subproc.pid)
                os.killpg(os.getpgid(subproc.pid), signal.SIGINT)
            except OSError:
                # this wipes our previous stack context, which is why
                # we have to save it above.
                logging.debug('Subproc already terminated, skipping')
            finally:
                if self.test_log_file:
                    with open(self.test_log_file.name, 'r') as f:
                        intro_msg = "Unexpected Issue. Raw Output:"
                        print(atest_utils.mark_red(intro_msg))
                        print(f.read())
                # Ignore socket.recv() raising due to ctrl-c
                if not error.args or error.args[0] != errno.EINTR:
                    raise error

    def wait_for_subprocess(self, proc):
        """Check the process status. Interrupt the TF subporcess if user
        hits Ctrl-C.

        Args:
            proc: The tradefed subprocess.

        Returns:
            Return code of the subprocess for running tests.
        """
        try:
            logging.debug('Runner Name: %s, Process ID: %s',
                          self.NAME, proc.pid)
            signal.signal(signal.SIGINT, self._signal_passer(proc))
            proc.wait()
            return proc.returncode
        except:
            # If atest crashes, kill TF subproc group as well.
            os.killpg(os.getpgid(proc.pid), signal.SIGINT)
            raise

    def _signal_passer(self, proc):
        """Return the signal_handler func bound to proc.

        Args:
            proc: The tradefed subprocess.

        Returns:
            signal_handler function.
        """
        def signal_handler(_signal_number, _frame):
            """Pass SIGINT to proc.

            If user hits ctrl-c during atest run, the TradeFed subprocess
            won't stop unless we also send it a SIGINT. The TradeFed process
            is started in a process group, so this SIGINT is sufficient to
            kill all the child processes TradeFed spawns as well.
            """
            print('Process ID: %s', proc.pid)
            try:
                logging.info('Ctrl-C received. Killing process group ID: %s',
                             os.getpgid(proc.pid))
                os.killpg(os.getpgid(proc.pid), signal.SIGINT)
            except ProcessLookupError as e:
                logging.info(e)
        return signal_handler

    def run_tests(self, test_infos, extra_args, reporter):
        """Run the list of test_infos.

        Should contain code for kicking off the test runs using
        test_runner_base.run(). Results should be processed and printed
        via the reporter passed in.

        Args:
            test_infos: List of TestInfo.
            extra_args: Dict of extra args to add to test run.
            reporter: An instance of result_report.ResultReporter.
        """
        raise NotImplementedError

    def host_env_check(self):
        """Checks that host env has met requirements."""
        raise NotImplementedError

    def get_test_runner_build_reqs(self, test_infos: List[test_info.TestInfo]):
        """Returns a list of build targets required by the test runner."""
        raise NotImplementedError

    def generate_run_commands(self, test_infos, extra_args, port=None):
        """Generate a list of run commands from TestInfos.

        Args:
            test_infos: A set of TestInfo instances.
            extra_args: A Dict of extra args to append.
            port: Optional. An int of the port number to send events to.
                  Subprocess reporter in TF won't try to connect if it's None.

        Returns:
            A list of run commands to run the tests.
        """
        raise NotImplementedError


def gather_build_targets(
        test_infos: List[test_info.TestInfo]) -> Set[str]:
    """Gets all build targets for the given tests.

    Args:
        test_infos: List of TestInfo.

    Returns:
        Set of build targets.
    """
    build_targets = set()

    for t_info in test_infos:
        build_targets |= t_info.build_targets

    return build_targets
