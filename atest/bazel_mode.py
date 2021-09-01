# Copyright 2021, The Android Open Source Project
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
Implementation of Atest's Bazel mode.

Bazel mode runs tests using Bazel by generating a synthetic workspace
that contains test targets. Using Bazel allow Atest to leverage features
such as sandboxing, caching, and remote execution.
"""

import constants

from test_finders import test_finder_base
from test_runners import test_runner_base


# pylint: disable=unused-argument
def generate_bazel_workspace(mod_info):
    """Generate bazel test workspace.

    Args:
        mod_info: ModuleInfo Object.
    """

def _decorate_find_method(mod_info, finder_method_func):
    """A finder_method decorator to override TestInfo properties."""

    def use_bazel_runner(finder_obj, test_id):
        test_infos = finder_method_func(finder_obj, test_id)
        if not test_infos:
            return test_infos
        for tinfo in test_infos:
            m_info = mod_info.get_module_info(tinfo.test_name)
            if mod_info.is_unit_test(m_info):
                tinfo.test_runner = BazelTestRunner.NAME
        return test_infos
    return use_bazel_runner

def create_new_finder(mod_info, finder):
    """Create new test_finder_base.Finder with decorated find_method.

    Args:
      mod_info: ModuleInfo object.
      finder: Test Finder class.

    Returns:
        List of ordered find methods.
    """
    return test_finder_base.Finder(finder.test_finder_instance,
                                   _decorate_find_method(
                                       mod_info,
                                       finder.find_method),
                                   finder.finder_info)

class BazelTestRunner(test_runner_base.TestRunnerBase):
    """Bazel Test Runner class."""
    NAME = 'BazelTestRunner'
    EXECUTABLE = 'none'

    # pylint: disable=unused-argument
    def run_tests(self, test_infos, extra_args, reporter):
        """Run the list of test_infos.

        Args:
            test_infos: List of TestInfo.
            extra_args: Dict of extra args to add to test run.
            reporter: An instance of result_report.ResultReporter
        """
        reporter.register_unsupported_runner(self.NAME)
        ret_code = constants.EXIT_CODE_SUCCESS

        run_cmds = self.generate_run_commands(test_infos, extra_args)
        for run_cmd in run_cmds:
            subproc = self.run(run_cmd,
                               output_to_stdout=True)
            ret_code |= self.wait_for_subprocess(subproc)
        return ret_code

    def host_env_check(self):
        """Check that host env has everything we need.

        We actually can assume the host env is fine because we have the same
        requirements that atest has. Update this to check for android env vars
        if that changes.
        """

    def get_test_runner_build_reqs(self):
        """Return the build requirements.

        Returns:
            Set of build targets.
        """
        return set()

    # pylint: disable=unused-argument
    # pylint: disable=unused-variable
    def generate_run_commands(self, test_infos, extra_args, port=None):
        """Generate a list of run commands from TestInfos.

        Args:
            test_infos: A set of TestInfo instances.
            extra_args: A Dict of extra args to append.
            port: Optional. An int of the port number to send events to.

        Returns:
            A list of run commands to run the tests.
        """
        run_cmds = []
        for tinfo in test_infos:
            run_cmds.append('echo "bazel test";')
        return run_cmds
