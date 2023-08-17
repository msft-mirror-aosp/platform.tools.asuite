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

"""
Test runner for Roboleaf mode.

This runner is used to run the tests that have been fully converted to Bazel.
"""

import enum
import json
import logging
import os
import shlex
import subprocess

from pathlib import Path
from typing import Any, Dict, List, Set

from atest import atest_utils
from atest import bazel_mode
from atest import constants
from atest import result_reporter

from atest.atest_enum import ExitCode
from atest.test_finders.test_info import TestInfo
from atest.test_runners import test_runner_base
from atest.tools.singleton import Singleton

# Roboleaf maintains allowlists that identify which modules have been
# fully converted to bazel. Users of atest can use
# --roboleaf-mode=[ON/OFF/DEV] to filter by these allowlists.
# ON (default) is the only mode expected to be fully converted and passing.
# This list contains the test labels that should be fully handled by Bazel end to
# end.
_ALLOWLIST_LAUNCHED = (
    f'{os.environ.get(constants.ANDROID_BUILD_TOP)}/'
    'tools/asuite/atest/test_runners/roboleaf_launched.txt')
# This list contains all of the bp2build converted Android.bp modules.
_ROBOLEAF_MODULE_MAP_PATH = ('soong/soong_injection/metrics/'
                             'converted_modules_path_map.json')
_SOONG_UI_CMD = 'build/soong/soong_ui.bash'

@enum.unique
class BazelBuildMode(enum.Enum):
    "Represents different bp2build allowlists to use when running bazel (b)"
    OFF = 'off' # no bazel builds at all
    ON = 'on' # use bazel for the production ready set of converted tests.
    DEV = 'dev' # use bazel for all converted tests. (some may still be failing)

class RoboleafModuleMap(metaclass=Singleton):
    """Roboleaf Module Map Singleton class."""

    def __init__(self, module_map_location: str = ''):
        module_map = _generate_map(module_map_location)
        self._module_map = module_map
        self.launched_modules = _read_allowlist(
            Path(_ALLOWLIST_LAUNCHED), module_map = module_map)

    def get_map(self) -> Dict[str, str]:
        """Return converted module map.

        Returns:
            A dictionary of test names that bazel paths for eligible tests,
            for example { "test_a": "//platform/test_a" }.
        """
        return self._module_map

def are_all_tests_supported(roboleaf_mode, tests) -> Dict[str, TestInfo]:
    """Determine if the list of tests are all supported by bazel based on the mode.

    If all requested tests are eligible, then indexing, generating
    module-info.json, and generating atest bazel workspace can be skipped since
    dependencies can be transitively built with bazel's build graph.

    Args:
        roboleaf_mode: The value of --roboleaf-mode.
        tests: A list of test names requested by the user.

    Returns:
        The list of 'b test'-able module names. If --roboleaf-mode is 'off' or
        if at least 1 requested test is not b testable, return an empty list.

    """
    if roboleaf_mode == BazelBuildMode.OFF:
        # Gracefully fall back to standard atest if roboleaf mode is disabled.
        return {}

    eligible_tests = _roboleaf_eligible_tests(roboleaf_mode, tests)

    if set(eligible_tests.keys()) == set(tests):
        # only enable b test when every requested test is eligible for roboleaf
        # mode.
        return eligible_tests

    # Gracefully fall back to standard atest if not every test is b testable.
    return {}

def _roboleaf_eligible_tests(
    mode: BazelBuildMode,
    module_names: List[str]) -> Dict[str, TestInfo]:
    """Filter the given module_names to only ones that are currently
    fully converted with roboleaf (b test) and then filter further by the
    launch allowlist.

    Args:
        mode: A BazelBuildMode value to switch between dev and prod lists.
        module_names: A list of module names to check for roboleaf support.

    Returns:
        A dictionary keyed by test name and value of Roboleaf TestInfo.
    """
    if not module_names or mode == BazelBuildMode.OFF:
        return {}

    mod_map = RoboleafModuleMap()
    supported_modules = set(filter(
        lambda m: m in mod_map.get_map(), module_names))

    # By default, only keep modules that are in the managed list
    # of launched modules.
    if mode == BazelBuildMode.ON:
        supported_modules = set(filter(
            lambda m: m in supported_modules, mod_map.launched_modules))

    return {
        module: TestInfo(module, RoboleafTestRunner.NAME, set())
        for module in supported_modules
    }

def _generate_map(module_map_location: str = '') -> Dict[str, str]:
    """Generate converted module map.

    Args:
        module_map_location: Path of the module_map_location to check.

    Returns:
        A dictionary of test names that bazel paths for eligible tests,
        for example { "test_a": "//platform/test_a" }.
    """
    if module_map_location:
        module_map_location = Path(module_map_location)
    else:
        module_map_location = atest_utils.get_build_out_dir(_ROBOLEAF_MODULE_MAP_PATH)

    # TODO(b/274161649): It is possible it could be stale on first run.
    # Invoking m or b test will check/recreate this file.  Bug here is
    # to determine if we can check staleness without a large time penalty.
    if not module_map_location.is_file():
        logging.warning('The roboleaf converted modules file: %s was not '
                        'found.', module_map_location)
        # Attempt to generate converted modules file.
        try:
            cmd = _generate_bp2build_command()
            env_vars = os.environ.copy()
            logging.info(
                'Running `bp2build` to generate converted modules file.'
                '\n%s', ' '.join(cmd))
            subprocess.check_call(cmd,  env=env_vars)
        except subprocess.CalledProcessError as e:
            logging.error(e)
            return {}

    with open(module_map_location, 'r', encoding='utf8') as robo_map:
        return json.load(robo_map)

def _read_allowlist(
    allowlist_location: Path = None,
    module_map: Dict[str, str] = None) -> List[str]:
    """Generate a list of modules based on a plain text allowlist file.

    The expected file format is a text file that has a Bazel label on each line.

    The bazel label is in the format of "//path/to:module".

    Lines that start with '#' are considered comments and skipped.

    Args:
        location: Path of the allowlist file to parse.

    Returns:
        A list of module names.
    """

    if not allowlist_location:
        raise AbortRunException("No launch allowlist was specified.")
    if not allowlist_location.exists():
        raise AbortRunException('The allowlist %s was not found.' % allowlist_location)

    with open(allowlist_location,  encoding='utf-8') as f:
        allowed = []

        # .read().splitlines() handles newline stripping
        # automatically, compared to .readlines().
        for entry in f.read().splitlines():
            if not entry or entry.startswith('#'):
                # This is a comment or empty line.
                continue
            if not entry.startswith("//"):
                # Not a valid fully qualified bazel label.
                raise AbortRunException("all entries in roboleaf_launched.txt must be valid "
                                        "bazel labels that starts with '//', but got '%s'" % entry)

            parts = entry.split(":")
            package_name = None
            target_name = None

            if len(parts) > 2:
                raise AbortRunException("%s is not a valid bazel label with "
                                        "more than two colons ':' characters" % entry)

            if len(parts) == 2:
                # ["//foo/bar", "module"]
                package_name = parts[0]
                target_name = parts[1]
            elif len(parts) == 1:
                # bazel shorthand //foo/bar == //foo/bar:bar, so compute for 'bar'
                package_name = entry
                target_name = entry.split("/")[-1]

            # Check that the module is the main converted module map. If it's
            # not converted by bp2build, don't build it with bazel. This may
            # change in the future with checked-in BUILD targets.
            if target_name not in module_map and module_map.get(target_name) != package_name:
                logging.warning("requested module %s is not in the bp2build roboleaf module map", entry)
                continue

            allowed.append(target_name)
        return allowed

def _generate_bp2build_command() -> List[str]:
    """Build command to run bp2build.

    Returns:
        A list of commands to run bp2build.
    """
    soong_ui = (
        f'{os.environ.get(constants.ANDROID_BUILD_TOP, os.getcwd())}/'
        f'{_SOONG_UI_CMD}')
    return [soong_ui, '--make-mode', 'WRAPPER_TOOL=atest', 'bp2build']


class AbortRunException(Exception):
    """Roboleaf Abort Run Exception Class."""


class RoboleafTestRunner(test_runner_base.TestRunnerBase):
    """Roboleaf Test Runner class."""
    NAME = 'RoboleafTestRunner'
    EXECUTABLE = 'b'

    # pylint: disable=unused-argument
    def generate_run_commands(self,
                              test_infos: Set[Any],
                              extra_args: Dict[str, Any],
                              port: int = None) -> List[str]:
        """Generate a list of run commands from TestInfos.

        Args:
            test_infos: A set of TestInfo instances.
            extra_args: A Dict of extra args to append.
            port: Optional. An int of the port number to send events to.

        Returns:
            A list of run commands to run the tests.
        """
        target_patterns = ' '.join(
            self.test_info_target_label(i) for i in test_infos)
        bazel_args = bazel_mode.parse_args(test_infos, extra_args, None)
        # The tool tag attributes this bazel invocation to atest. This
        # is uploaded in BEP when bes publishing is enabled.
        bazel_args.append("--tool_tag=atest")

        # --config=deviceless_tests filters for tradefed_deviceless_test targets.
        if constants.HOST in extra_args:
            bazel_args.append("--config=deviceless_tests")

        bazel_args_str = ' '.join(shlex.quote(arg) for arg in bazel_args)
        command = f'{self.EXECUTABLE} test {target_patterns} {bazel_args_str}'
        results = [command]
        logging.info("Roboleaf test runner command:\n"
                     "\n".join(results))
        return results

    def test_info_target_label(self, test: TestInfo) -> str:
        """ Get bazel path of test

        Args:
            test: An object of TestInfo.

        Returns:
            The bazel path of the test.
        """
        module_map = RoboleafModuleMap().get_map()
        return f'{module_map[test.test_name]}:{test.test_name}'

    def run_tests(self,
                  test_infos: List[TestInfo],
                  extra_args: Dict[str, Any],
                  reporter: result_reporter.ResultReporter) -> int:
        """Run the list of test_infos.

        Args:
            test_infos: List of TestInfo.
            extra_args: Dict of extra args to add to test run.
            reporter: An instance of result_reporter.ResultReporter.
        """
        reporter.register_unsupported_runner(self.NAME)
        ret_code = ExitCode.SUCCESS
        try:
            run_cmds = self.generate_run_commands(test_infos, extra_args)
        except AbortRunException as e:
            atest_utils.colorful_print(f'Stop running test(s): {e}',
                                       constants.RED)
            return ExitCode.ERROR
        for run_cmd in run_cmds:
            subproc = self.run(run_cmd, output_to_stdout=True)
            ret_code |= self.wait_for_subprocess(subproc)
        return ret_code

    def get_test_runner_build_reqs(
        self,
        test_infos: List[TestInfo]) -> Set[str]:
        return set()

    def host_env_check(self) -> None:
        """Check that host env has everything we need.

        We actually can assume the host env is fine because we have the same
        requirements that atest has. Update this to check for android env vars
        if that changes.
        """
