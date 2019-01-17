#!/usr/bin/env python3
#
# Copyright 2019, The Android Open Source Project
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

"""Unittests for aidegen_main."""

from __future__ import print_function

import unittest
from unittest import mock

from aidegen import aidegen_main
from aidegen.lib.common_util import COLORED_INFO
from aidegen.lib.errors import IDENotExistError
from aidegen.lib.ide_util import IdeUtil

import aidegen.unittest_constants as uc

# pylint: disable=protected-access
# pylint: disable=invalid-name
class AidegenMainUnittests(unittest.TestCase):
    """Unit tests for aidegen_main.py"""

    def test_parse_args(self):
        """Test _parse_args with different conditions."""
        args = aidegen_main._parse_args([])
        self.assertEqual(args.targets, [''])
        self.assertEqual(args.ide[0], 'j')
        target = 'tradefed'
        args = aidegen_main._parse_args([target])
        self.assertEqual(args.targets, [target])
        depth = '2'
        args = aidegen_main._parse_args(['-d', depth])
        self.assertEqual(args.depth, int(depth))
        args = aidegen_main._parse_args(['-v'])
        self.assertEqual(args.verbose, True)
        args = aidegen_main._parse_args(['-v'])
        self.assertEqual(args.verbose, True)
        args = aidegen_main._parse_args(['-i', 's'])
        self.assertEqual(args.ide[0], 's')
        args = aidegen_main._parse_args(['-i', 'e'])
        self.assertEqual(args.ide[0], 'e')
        args = aidegen_main._parse_args(['-p', uc.TEST_MODULE])
        self.assertEqual(args.ide_installed_path, uc.TEST_MODULE)
        args = aidegen_main._parse_args(['-n'])
        self.assertEqual(args.no_launch, True)
        args = aidegen_main._parse_args(['-r'])
        self.assertEqual(args.config_reset, True)
        args = aidegen_main._parse_args(['-s'])
        self.assertEqual(args.skip_build, True)

    @mock.patch('aidegen_main.logging.basicConfig')
    def test_configure_logging(self, mock_log_config):
        """Test _configure_logging with different arguments."""
        aidegen_main._configure_logging(True)
        log_format = aidegen_main._LOG_FORMAT
        datefmt = aidegen_main._DATE_FORMAT
        level = aidegen_main.logging.DEBUG
        self.assertTrue(
            mock_log_config.called_with(
                level=level, format=log_format, datefmt=datefmt))
        aidegen_main._configure_logging(False)
        level = aidegen_main.logging.INFO
        self.assertTrue(
            mock_log_config.called_with(
                level=level, format=log_format, datefmt=datefmt))

    @mock.patch.object(IdeUtil, 'is_ide_installed')
    def test_get_ide_util_instance(self, mock_installed):
        """Test _get_ide_util_instance with different conditions."""
        target = 'tradefed'
        args = aidegen_main._parse_args([target, '-n'])
        self.assertEqual(aidegen_main._get_ide_util_instance(args), None)
        args = aidegen_main._parse_args([target])
        self.assertIsInstance(
            aidegen_main._get_ide_util_instance(args), IdeUtil)
        mock_installed.return_value = False
        with self.assertRaises(IDENotExistError):
            aidegen_main._get_ide_util_instance(args)

    @mock.patch('builtins.print')
    def test_check_skip_build(self, mock_print):
        """Test _check_skip_build with different conditions."""
        target = 'tradefed'
        args = aidegen_main._parse_args([target, '-s'])
        aidegen_main._check_skip_build(args)
        self.assertFalse(mock_print.called)
        args = aidegen_main._parse_args([target])
        aidegen_main._check_skip_build(args)
        msg = aidegen_main._SKIP_BUILD_INFO.format(
            COLORED_INFO(
                aidegen_main._SKIP_BUILD_CMD.format(' '.join(args.targets))))
        info = '\n{} {}\n'.format(aidegen_main._INFO, msg)
        self.assertTrue(mock_print.called_with(info))


if __name__ == '__main__':
    unittest.main()
