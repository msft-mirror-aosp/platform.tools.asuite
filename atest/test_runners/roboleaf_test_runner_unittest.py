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

# pylint: disable=line-too-long

"""Unittests for roboleaf_test_runner."""

import json
import os
import unittest
import subprocess
import logging
from textwrap import dedent

from pathlib import Path
from unittest import mock
from pyfakefs import fake_filesystem_unittest

from atest import atest_utils
from atest import constants
from atest import unittest_constants
from atest.test_finders.test_info import TestInfo
from atest.test_runners import roboleaf_test_runner
from atest.test_runners.roboleaf_test_runner import AbortRunException
from atest.test_runners.roboleaf_test_runner import RoboleafTestRunner
from atest.test_runners.roboleaf_test_runner import RoboleafModuleMap

# TODO(b/274706697): Refactor to remove disable=protected-access
# pylint: disable=protected-access
class RoboleafTestRunnerUnittests(fake_filesystem_unittest.TestCase):
    """Unit tests for roboleaf_test_runner.py"""
    def setUp(self):
        self.test_runner = RoboleafTestRunner(results_dir='')
        self.setUpPyfakefs()
        out_dir = atest_utils.get_build_out_dir()
        self.fs.create_file(
            out_dir.joinpath(roboleaf_test_runner._ROBOLEAF_MODULE_MAP_PATH),
            contents="{}")
        self.fs.create_file(roboleaf_test_runner._ALLOWLIST_LAUNCHED, contents="")

    def tearDown(self):
        RoboleafModuleMap()._module_map = {}
        mock.patch.stopall()

    def test_read_allowlist_simple(self):
        """Test _read_allowlist method with a simple configuration."""
        allowlist_path = Path("allowlist")
        allowlist_content = """
        # a comment
        //a:test1
        # another comment
        //a/b:test2
        """
        self.fs.create_file(allowlist_path, contents=dedent(allowlist_content))

        module_map = {'test1': "//a", "test2": "//a/b"}
        self.assertEqual(
            roboleaf_test_runner._read_allowlist(allowlist_path, module_map),
            ['test1','test2'])

    def test_read_allowlist_subset(self):
        """Test _read_allowlist method with a proper subset of converted modules."""
        allowlist_path = Path("allowlist")
        allowlist_content = """
        //a:test1
        """
        self.fs.create_file(allowlist_path, contents=dedent(allowlist_content))

        module_map = {'test1': "//a", "test2": "//a/b", "test3": "//a/b/c"}
        self.assertEqual(
            roboleaf_test_runner._read_allowlist(allowlist_path, module_map),
            ['test1'])

    def test_read_allowlist_superset(self):
        """Test _read_allowlist method with launch allowlist containing non-converted modules."""
        allowlist_path = Path("allowlist")
        allowlist_content = """
        //a:test1
        //a/b:test2
        //a/b/c:test3
        """
        self.fs.create_file(allowlist_path, contents=dedent(allowlist_content))

        module_map = {'test1': "//a", "test2": "//a/b"}
        with self.assertLogs('', level='WARNING') as context:
            self.assertEqual(
                roboleaf_test_runner._read_allowlist(allowlist_path, module_map),
                ['test1', 'test2'])

            self.assertListEqual([
                'WARNING:root:requested module //a/b/c:test3 '
                'is not in the bp2build roboleaf module map'
            ], context.output)

    def test_read_allowlist_malformed_label_with_colons(self):
        """Test _read_allowlist method with malformed bazel label."""
        allowlist_path = Path("allowlist")
        allowlist_content = """
        //a:test1:bad
        """
        self.fs.create_file(allowlist_path, contents=dedent(allowlist_content))

        module_map = {}
        with self.assertRaises(AbortRunException):
            roboleaf_test_runner._read_allowlist(allowlist_path, module_map)

    def test_read_allowlist_need_full_bazel_labels(self):
        """Test _read_allowlist method with non-full bazel label."""
        allowlist_path = Path("allowlist")
        allowlist_content = """
        foo
        """
        self.fs.create_file(allowlist_path, contents=dedent(allowlist_content))

        module_map = {}
        with self.assertRaises(AbortRunException):
            roboleaf_test_runner._read_allowlist(allowlist_path, module_map)

    def test_are_all_tests_supported_filtering(self):
        """Test are_all_tests_supported method when _module_map has entries"""
        RoboleafModuleMap._instances = {}

        out_dir = atest_utils.get_build_out_dir()
        os.remove(out_dir.joinpath(roboleaf_test_runner._ROBOLEAF_MODULE_MAP_PATH))
        self.fs.create_file(
            out_dir.joinpath(roboleaf_test_runner._ROBOLEAF_MODULE_MAP_PATH),
            contents=json.dumps({
            'test1': "//a",
            'test2': "//a/b",
            'test3': "//a/b/c",
            'test4': "//a/b/c/d",
        }))
        allowlist_content = """
        //a:test1
        //a/b:test2
        """
        os.remove(roboleaf_test_runner._ALLOWLIST_LAUNCHED)
        self.fs.create_file(
            roboleaf_test_runner._ALLOWLIST_LAUNCHED,
            contents=dedent(allowlist_content))

        # (mode, module names of requested tests, expected number of eligible tests)
        test_cases = [
            (roboleaf_test_runner.BazelBuildMode.OFF, ['test1', 'test2', 'test3'], 0),
            (roboleaf_test_runner.BazelBuildMode.OFF, [], 0),
            # --roboleaf-mode=dev tests. Ignores launch allowlist.
            (roboleaf_test_runner.BazelBuildMode.DEV, ['test1', 'test2', 'test3'], 3),
            (roboleaf_test_runner.BazelBuildMode.DEV, ['test1', 'test2'], 2),
            (roboleaf_test_runner.BazelBuildMode.DEV, ['test1'], 1),
            (roboleaf_test_runner.BazelBuildMode.DEV, [], 0),
            # --roboleaf-mode=on tests. Takes launch allowlist into account.
            (roboleaf_test_runner.BazelBuildMode.ON, ['test1', 'test2', 'test3'], 0),
            (roboleaf_test_runner.BazelBuildMode.ON, ['test1', 'test2'], 2),
            (roboleaf_test_runner.BazelBuildMode.ON, ['test1'], 1),
            (roboleaf_test_runner.BazelBuildMode.ON, [], 0),
        ]

        for test_case in test_cases:
            (mode, module_names, expected_len) = test_case
            eligible_tests = roboleaf_test_runner.are_all_tests_supported(mode, module_names, [])
            self.assertEqual(len(eligible_tests), expected_len)
            if expected_len:
                for module_name in module_names:
                    self.assertEqual(eligible_tests[module_name].test_name, module_name)
                    self.assertEqual(eligible_tests[module_name].test_runner,
                                    RoboleafTestRunner.NAME)

    def test_are_all_tests_supported_with_test_filter(self):
        """Test are_all_tests_supported method when specifying test filters"""
        RoboleafModuleMap._instances = {}

        out_dir = atest_utils.get_build_out_dir()
        os.remove(out_dir.joinpath(roboleaf_test_runner._ROBOLEAF_MODULE_MAP_PATH))
        self.fs.create_file(
            out_dir.joinpath(roboleaf_test_runner._ROBOLEAF_MODULE_MAP_PATH),
            contents=json.dumps({
                'test1': "//a",
                'test2': "//a/b",
                'test3': "//a/b/c",
            }))

        eligible_tests = roboleaf_test_runner.are_all_tests_supported(
            roboleaf_test_runner.BazelBuildMode.DEV,
            [
                'test1',
                'test2:class2#method2a',
                'test2:class2#method2b',
                'test3:class3#method3a,method3b',
            ],
            [])

        self.assertEqual(len(eligible_tests), 3)
        self.assertEqual(
            len(eligible_tests['test1'].data.get(constants.ROBOLEAF_TEST_FILTER, [])), 0)
        self.assertSetEqual(
            set(eligible_tests['test2'].data.get(constants.ROBOLEAF_TEST_FILTER, [])),
            {'test2:class2#method2a', 'test2:class2#method2b'})
        self.assertEqual(eligible_tests['test2'].test_runner, RoboleafTestRunner.NAME)
        self.assertSetEqual(
            set(eligible_tests['test3'].data.get(constants.ROBOLEAF_TEST_FILTER, [])),
            {'test3:class3#method3a,method3b'})
        self.assertEqual(eligible_tests['test3'].test_runner, RoboleafTestRunner.NAME)

    def test_are_all_tests_supported_empty_map(self):
        """Test are_all_tests_supported method when _module_map is empty"""
        module_names = [
            'test1',
            'test2',
        ]
        RoboleafModuleMap()._module_map = {}

        eligible_tests = roboleaf_test_runner.are_all_tests_supported(
            roboleaf_test_runner.BazelBuildMode.DEV,
            module_names,
            [])
        self.assertEqual(eligible_tests, {})

    def test_are_all_tests_supported_unsupported_flag(self):
        """Test are_all_tests_supported method when unsupported_flag is specified"""
        RoboleafModuleMap._instances = {}

        out_dir = atest_utils.get_build_out_dir()
        os.remove(out_dir.joinpath(roboleaf_test_runner._ROBOLEAF_MODULE_MAP_PATH))
        self.fs.create_file(
            out_dir.joinpath(roboleaf_test_runner._ROBOLEAF_MODULE_MAP_PATH),
            contents=json.dumps({
                'test1': "//a",
            }))
        allowlist_content = """
        //a:test1
        """
        os.remove(roboleaf_test_runner._ALLOWLIST_LAUNCHED)
        self.fs.create_file(
            roboleaf_test_runner._ALLOWLIST_LAUNCHED,
            contents=dedent(allowlist_content))
        module_names = [
            'test1',
        ]

        eligible_tests = roboleaf_test_runner.are_all_tests_supported(
            roboleaf_test_runner.BazelBuildMode.DEV,
            module_names,
            ['unsupported_flag'])

        self.assertEqual(eligible_tests, {})

    def test_get_map(self):
        """Test get_map method."""
        data = {
            "test1": "//platform/a",
            "test2": "//platform/b"
        }
        RoboleafModuleMap()._module_map = data

        self.assertEqual(RoboleafModuleMap().get_map(), data)

    @mock.patch.object(subprocess, "check_call")
    def test_generate_map(self, mock_subprocess):
        """Test test_generate_map method fomr file."""
        module_map_location = Path(unittest_constants.TEST_DATA_DIR).joinpath(
            "roboleaf_testing/converted_modules_path_map.json"
        )
        self.fs.create_file(
            module_map_location,
            contents=json.dumps({
            "test1": "//platform/a",
            "test2": "//platform/b"
        }))

        data = roboleaf_test_runner._generate_map(module_map_location)

        # Expected to not call a subprocess with the roboleaf bp2build
        # command since file already exists.
        self.assertEqual(mock_subprocess.called, False)
        self.assertEqual(data, {
            "test1": "//platform/a",
            "test2": "//platform/b"
        })

    @mock.patch('builtins.open', mock.mock_open(read_data=json.dumps(
        {"test3": "//a/b"})))
    @mock.patch.object(subprocess, "check_call")
    def test_generate_map_with_command(self, mock_subprocess):
        """Test that _generate_map runs the bp2build command"""
        module_map_location = Path(unittest_constants.TEST_DATA_DIR).joinpath(
            "roboleaf_testing/does_not_exist.json"
        )

        # Disable expected warning log message "converted modules file was not
        # found." to reduce noise during tests.
        logging.disable(logging.WARNING)
        data = roboleaf_test_runner._generate_map(module_map_location)
        logging.disable(logging.NOTSET)

        self.assertEqual(mock_subprocess.called, True)
        self.assertEqual(data, {"test3": "//a/b"})

    def test_info_target_label(self):
        """Test info_target_label method."""
        RoboleafModuleMap()._module_map = {
            "test1": "//a",
        }

        target_label = self.test_runner.test_info_target_label(
            TestInfo(
                "test1",
                RoboleafTestRunner.NAME,
                set()),
        )

        self.assertEqual(target_label, "//a:test1")

    def test_generate_run_commands(self):
        """Test generate_run_commands method."""
        RoboleafModuleMap()._module_map = {
            "test1": "//a",
            "test2": "//b",
        }
        test_infos = (
            TestInfo(
                "test1",
                RoboleafTestRunner.NAME,
                set()),
            TestInfo(
                "test2",
                RoboleafTestRunner.NAME,
                set()),
        )

        cmds = self.test_runner.generate_run_commands(test_infos, extra_args={})

        self.assertEqual(len(cmds), 1)
        self.assertTrue('b test //a:test1 //b:test2' in cmds[0])

    def test_atest_host_flag(self):
        """Test that generate_run_commands converts --host correctly."""
        RoboleafModuleMap()._module_map = {"test1": "//a"}
        test_infos = (
            TestInfo("test1", RoboleafTestRunner.NAME, set()),
        )

        cmds = self.test_runner.generate_run_commands(
            test_infos,
            extra_args={ constants.HOST : True },
        )

        self.assertEqual(len(cmds), 1)
        self.assertTrue('--config=deviceless' in cmds[0])

    def test_atest_enable_device_preparer_flag(self):
        """Test that generate_run_commands converts --enable-device-preparer correctly."""
        RoboleafModuleMap()._module_map = {"test1": "//a"}
        test_infos = (
            TestInfo("test1", RoboleafTestRunner.NAME, set()),
        )

        cmds = self.test_runner.generate_run_commands(
            test_infos,
            extra_args={ constants.ENABLE_DEVICE_PREPARER: True },
        )

        self.assertEqual(len(cmds), 1)
        self.assertTrue('--test_arg=--enable-device-preparer' in cmds[0])

    @mock.patch.object(RoboleafTestRunner, 'run')
    def test_run_tests(self, mock_run):
        """Test run_tests_raw method."""
        RoboleafModuleMap()._module_map = {
            "test1": "//a",
            "test2": "//b",
        }
        test_infos = (
            TestInfo(
                "test1",
                RoboleafTestRunner.NAME,
                set()),
            TestInfo(
                "test2",
                RoboleafTestRunner.NAME,
                set()),
        )
        extra_args = {}
        mock_subproc = mock.Mock()
        mock_run.return_value = mock_subproc
        mock_subproc.returncode = 0
        mock_reporter = mock.Mock()

        result = self.test_runner.run_tests(
            test_infos, extra_args, mock_reporter)

        self.assertEqual(result, 0)


if __name__ == '__main__':
    unittest.main()
