#!/usr/bin/env python3
#
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

"""Unittests for atest."""

# pylint: disable=line-too-long

import datetime
import os
import sys
import tempfile
import unittest

from importlib import reload
from io import StringIO
from unittest import mock
from pyfakefs import fake_filesystem_unittest

from atest import atest_main
from atest import atest_utils
from atest import constants
from atest import module_info

from atest.metrics import metrics_utils
from atest.test_finders import test_info

GREEN= '\x1b[1;32m'
CYAN = '\x1b[1;36m'
MAGENTA = '\x1b[1;35m'
END = '\x1b[0m'


#pylint: disable=protected-access
class AtestUnittests(unittest.TestCase):
    """Unit tests for atest_main.py"""

    @mock.patch('os.environ.get', return_value=None)
    def test_missing_environment_variables_uninitialized(self, _):
        """Test _has_environment_variables when no env vars."""
        self.assertTrue(atest_main._missing_environment_variables())

    @mock.patch('os.environ.get', return_value='out/testcases/')
    def test_missing_environment_variables_initialized(self, _):
        """Test _has_environment_variables when env vars."""
        self.assertFalse(atest_main._missing_environment_variables())

    def test_parse_args(self):
        """Test _parse_args parses command line args."""
        test_one = 'test_name_one'
        test_two = 'test_name_two'
        custom_arg = '--custom_arg'
        custom_arg_val = 'custom_arg_val'
        pos_custom_arg = 'pos_custom_arg'

        # Test out test and custom args are properly retrieved.
        args = [test_one, test_two, '--', custom_arg, custom_arg_val]
        parsed_args = atest_main._parse_args(args)
        self.assertEqual(parsed_args.tests, [test_one, test_two])
        self.assertEqual(parsed_args.custom_args, [custom_arg, custom_arg_val])

        # Test out custom positional args with no test args.
        args = ['--', pos_custom_arg, custom_arg_val]
        parsed_args = atest_main._parse_args(args)
        self.assertEqual(parsed_args.tests, [])
        self.assertEqual(parsed_args.custom_args, [pos_custom_arg,
                                                   custom_arg_val])

    def test_has_valid_test_mapping_args(self):
        """Test _has_valid_test_mapping_args method."""
        # Test test mapping related args are not mixed with incompatible args.
        options_no_tm_support = [
            ('--generate-baseline', '5'),
            ('--detect-regression', 'path'),
            ('--generate-new-metrics', '5')
        ]
        tm_options = [
            '--test-mapping',
            '--include-subdirs'
        ]

        for tm_option in tm_options:
            for no_tm_option, no_tm_option_value in options_no_tm_support:
                args = [tm_option, no_tm_option]
                if no_tm_option_value is not None:
                    args.append(no_tm_option_value)
                parsed_args = atest_main._parse_args(args)
                self.assertFalse(
                    atest_main._has_valid_test_mapping_args(parsed_args),
                    'Failed to validate: %s' % args)

    @mock.patch.object(atest_utils, 'get_adb_devices')
    @mock.patch.object(metrics_utils, 'send_exit_event')
    def test_validate_exec_mode(self, _send_exit, _devs):
        """Test _validate_exec_mode."""
        _devs.return_value = ['127.0.0.1:34556']
        args = []
        no_install_test_info = test_info.TestInfo(
            'mod', '', set(), data={}, module_class=["JAVA_LIBRARIES"],
            install_locations=set(['device']))
        host_test_info = test_info.TestInfo(
            'mod', '', set(), data={}, module_class=["NATIVE_TESTS"],
            install_locations=set(['host']))
        device_test_info = test_info.TestInfo(
            'mod', '', set(), data={}, module_class=["NATIVE_TESTS"],
            install_locations=set(['device']))
        both_test_info = test_info.TestInfo(
            'mod', '', set(), data={}, module_class=["NATIVE_TESTS"],
            install_locations=set(['host', 'device']))

        # $atest <Both-support>
        parsed_args = atest_main._parse_args(args)
        test_infos = [host_test_info]
        atest_main._validate_exec_mode(parsed_args, test_infos)
        self.assertFalse(parsed_args.host)

        # $atest <Both-support> with host_tests set to True
        parsed_args = atest_main._parse_args([])
        test_infos = [host_test_info]
        atest_main._validate_exec_mode(parsed_args, test_infos, host_tests=True)
        # Make sure the host option is not set.
        self.assertFalse(parsed_args.host)

        # $atest <Both-support> with host_tests set to False
        parsed_args = atest_main._parse_args([])
        test_infos = [host_test_info]
        atest_main._validate_exec_mode(parsed_args, test_infos, host_tests=False)
        self.assertFalse(parsed_args.host)

        # $atest <device-only> with host_tests set to False
        parsed_args = atest_main._parse_args([])
        test_infos = [device_test_info]
        atest_main._validate_exec_mode(parsed_args, test_infos, host_tests=False)
        # Make sure the host option is not set.
        self.assertFalse(parsed_args.host)

        # $atest <device-only> with host_tests set to True
        parsed_args = atest_main._parse_args([])
        test_infos = [device_test_info]
        self.assertRaises(SystemExit, atest_main._validate_exec_mode,
                          parsed_args, test_infos, host_tests=True)

        # $atest <Both-support>
        parsed_args = atest_main._parse_args([])
        test_infos = [both_test_info]
        atest_main._validate_exec_mode(parsed_args, test_infos)
        self.assertFalse(parsed_args.host)

        # $atest <no_install_test_info>
        parsed_args = atest_main._parse_args([])
        test_infos = [no_install_test_info]
        atest_main._validate_exec_mode(parsed_args, test_infos)
        self.assertFalse(parsed_args.host)

    def test_make_test_run_dir(self):
        """Test make_test_run_dir."""
        tmp_dir = tempfile.mkdtemp()
        constants.ATEST_RESULT_ROOT = tmp_dir
        date_time = None

        work_dir = atest_main.make_test_run_dir()
        folder_name = os.path.basename(work_dir)
        date_time = datetime.datetime.strptime('_'.join(folder_name.split('_')[0:2]),
                                               atest_main.TEST_RUN_DIR_PREFIX)
        reload(constants)
        self.assertTrue(date_time)


# pylint: disable=missing-function-docstring
class AtestUnittestFixture(fake_filesystem_unittest.TestCase):
    """Fixture for ModuleInfo tests."""

    def setUp(self):
        self.setUpPyfakefs()

    # pylint: disable=protected-access
    def create_empty_module_info(self):
        fake_temp_file_name = next(tempfile._get_candidate_names())
        self.fs.create_file(fake_temp_file_name, contents='{}')
        return module_info.ModuleInfo(module_file=fake_temp_file_name)

    def create_module_info(self, modules=None):
        mod_info = self.create_empty_module_info()
        modules = modules or []

        for m in modules:
            mod_info.name_to_module_info[m['module_name']] = m

        return mod_info

    def create_test_info(
            self,
            test_name='hello_world_test',
            test_runner='AtestTradefedRunner',
            build_targets=None):
        """Create a test_info.TestInfo object."""
        if not build_targets:
            build_targets = set()
        return test_info.TestInfo(test_name, test_runner, build_targets)


class PrintModuleInfoTest(AtestUnittestFixture):
    """Test conditions for _print_module_info."""

    def tearDown(self):
        sys.stdout = sys.__stdout__

    @mock.patch('atest.atest_utils._has_colors', return_value=True)
    def test_print_module_info_from_module_name(self, _):
        """Test _print_module_info_from_module_name method."""
        mod_info = self.create_module_info(
            [module(
                name='mod1',
                path=['src/path/mod1'],
                installed=['installed/path/mod1'],
                compatibility_suites=['device_test_mod1', 'native_test_mod1']
            )]
        )
        correct_output = (f'{GREEN}mod1{END}\n'
                          f'{CYAN}\tCompatibility suite{END}\n'
                          '\t\tdevice_test_mod1\n'
                          '\t\tnative_test_mod1\n'
                          f'{CYAN}\tSource code path{END}\n'
                          '\t\t[\'src/path/mod1\']\n'
                          f'{CYAN}\tInstalled path{END}\n'
                          '\t\tinstalled/path/mod1\n')
        capture_output = StringIO()
        sys.stdout = capture_output

        atest_main._print_module_info_from_module_name(mod_info, 'mod1')

        # Check the function correctly printed module_info in color to stdout
        self.assertEqual(correct_output, capture_output.getvalue())

    @mock.patch('atest.atest_utils._has_colors', return_value=True)
    def test_print_test_info(self, _):
        """Test _print_test_info method."""
        modules = []
        for index in {1, 2, 3}:
            modules.append(
                module(
                    name=f'mod{index}',
                    path=[f'path/mod{index}'],
                    installed=[f'installed/mod{index}'],
                    compatibility_suites=[f'suite_mod{index}']
                )
            )
        mod_info = self.create_module_info(modules)
        test_infos = {
            self.create_test_info(
                test_name='mod1',
                test_runner='mock_runner',
                build_targets={'mod1', 'mod2', 'mod3'},
            ),
        }
        correct_output = (f'{GREEN}mod1{END}\n'
                          f'{CYAN}\tCompatibility suite{END}\n'
                          '\t\tsuite_mod1\n'
                          f'{CYAN}\tSource code path{END}\n'
                          '\t\t[\'path/mod1\']\n'
                          f'{CYAN}\tInstalled path{END}\n'
                          '\t\tinstalled/mod1\n'
                          f'{MAGENTA}\tRelated build targets{END}\n'
                          '\t\tmod1, mod2, mod3\n'
                          f'{GREEN}mod2{END}\n'
                          f'{CYAN}\tCompatibility suite{END}\n'
                          '\t\tsuite_mod2\n'
                          f'{CYAN}\tSource code path{END}\n'
                          '\t\t[\'path/mod2\']\n'
                          f'{CYAN}\tInstalled path{END}\n'
                          '\t\tinstalled/mod2\n'
                          f'{GREEN}mod3{END}\n'
                          f'{CYAN}\tCompatibility suite{END}\n'
                          '\t\tsuite_mod3\n'
                          f'{CYAN}\tSource code path{END}\n'
                          '\t\t[\'path/mod3\']\n'
                          f'{CYAN}\tInstalled path{END}\n'
                          '\t\tinstalled/mod3\n'
                          f'\x1b[1;37m{END}\n')
        capture_output = StringIO()
        sys.stdout = capture_output

        # The _print_test_info() will print the module_info of the test_info's
        # test_name first. Then, print its related build targets. If the build
        # target be printed before(e.g. build_target == test_info's test_name),
        # it will skip it and print the next build_target.
        # Since the build_targets of test_info are mod_one, mod_two, and
        # mod_three, it will print mod_one first, then mod_two, and mod_three.
        #
        # _print_test_info() calls _print_module_info_from_module_name() to
        # print the module_info. And _print_module_info_from_module_name()
        # calls get_module_info() to get the module_info. So we can mock
        # get_module_info() to achieve that.
        atest_main._print_test_info(mod_info, test_infos)

        self.assertEqual(correct_output, capture_output.getvalue())


# pylint: disable=too-many-arguments
def module(
    name=None,
    path=None,
    installed=None,
    classes=None,
    auto_test_config=None,
    test_config=None,
    shared_libs=None,
    dependencies=None,
    runtime_dependencies=None,
    data=None,
    data_dependencies=None,
    compatibility_suites=None,
    host_dependencies=None,
    srcs=None,
):
    name = name or 'libhello'

    m = {}

    m['module_name'] = name
    m['class'] = classes
    m['path'] = [path or '']
    m['installed'] = installed or []
    m['is_unit_test'] = 'false'
    m['auto_test_config'] = auto_test_config or []
    m['test_config'] = test_config or []
    m['shared_libs'] = shared_libs or []
    m['runtime_dependencies'] = runtime_dependencies or []
    m['dependencies'] = dependencies or []
    m['data'] = data or []
    m['data_dependencies'] = data_dependencies or []
    m['compatibility_suites'] = compatibility_suites or []
    m['host_dependencies'] = host_dependencies or []
    m['srcs'] = srcs or []
    return m

if __name__ == '__main__':
    unittest.main()
