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

import sys
import unittest
from unittest import mock

from aidegen import aidegen_main
from aidegen import constant
from aidegen import unittest_constants
from aidegen.lib import aidegen_metrics
from aidegen.lib import common_util
from aidegen.lib import eclipse_project_file_gen
from aidegen.lib import errors
from aidegen.lib import project_config
from aidegen.lib import project_file_gen


# pylint: disable=protected-access
# pylint: disable=invalid-name
class AidegenMainUnittests(unittest.TestCase):
    """Unit tests for aidegen_main.py"""

    def _init_project_config(self, args):
        """Initialize project configurations."""
        self.assertIsNotNone(args)
        config = project_config.ProjectConfig(args)
        config.init_environment()

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
        self.assertTrue(args.verbose)
        args = aidegen_main._parse_args(['-v'])
        self.assertTrue(args.verbose)
        args = aidegen_main._parse_args(['-i', 's'])
        self.assertEqual(args.ide[0], 's')
        args = aidegen_main._parse_args(['-i', 'e'])
        self.assertEqual(args.ide[0], 'e')
        args = aidegen_main._parse_args(['-p', unittest_constants.TEST_MODULE])
        self.assertEqual(args.ide_installed_path,
                         unittest_constants.TEST_MODULE)
        args = aidegen_main._parse_args(['-n'])
        self.assertTrue(args.no_launch)
        args = aidegen_main._parse_args(['-r'])
        self.assertTrue(args.config_reset)
        args = aidegen_main._parse_args(['-s'])
        self.assertTrue(args.skip_build)

    @mock.patch.object(project_config, 'ProjectConfig')
    @mock.patch.object(project_file_gen.ProjectFileGenerator,
                       'generate_ide_project_files')
    @mock.patch.object(eclipse_project_file_gen.EclipseConf,
                       'generate_ide_project_files')
    def test_generate_project_files(self, mock_eclipse, mock_ide, mock_config):
        """Test _generate_project_files with different conditions."""
        projects = ['module_a', 'module_v']
        args = aidegen_main._parse_args([projects, '-i', 'e'])
        self._init_project_config(args)
        mock_config.ide_name = constant.IDE_ECLIPSE
        aidegen_main._generate_project_files(projects)
        self.assertTrue(mock_eclipse.called_with(projects))
        mock_config.ide_name = constant.IDE_ANDROID_STUDIO
        aidegen_main._generate_project_files(projects)
        self.assertTrue(mock_ide.called_with(projects))
        mock_config.ide_name = constant.IDE_INTELLIJ
        aidegen_main._generate_project_files(projects)
        self.assertTrue(mock_ide.called_with(projects))

    @mock.patch.object(common_util, 'get_atest_module_info')
    @mock.patch.object(aidegen_metrics, 'starts_asuite_metrics')
    def test_show_collect_data_notice(self, mock_metrics, mock_get):
        """Test main process always run through the target test function."""
        target = 'nothing'
        args = aidegen_main._parse_args([target, '-s', '-n'])
        self._init_project_config(args)
        with self.assertRaises(errors.ProjectPathNotExistError):
            err = common_util.PATH_NOT_EXISTS_ERROR.format(target)
            mock_get.side_effect = errors.ProjectPathNotExistError(err)
            aidegen_main.main_without_message(args)
            self.assertTrue(mock_metrics.called)

    @mock.patch.object(aidegen_main, 'main_with_message')
    @mock.patch.object(aidegen_main, 'main_without_message')
    def test_main(self, mock_without, mock_with):
        """Test main with conditions."""
        aidegen_main.main(['-s'])
        self.assertEqual(mock_without.call_count, 1)
        aidegen_main.main([''])
        self.assertEqual(mock_with.call_count, 1)

    @mock.patch.object(aidegen_metrics, 'starts_asuite_metrics')
    @mock.patch.object(project_config, 'is_whole_android_tree')
    @mock.patch.object(aidegen_metrics, 'ends_asuite_metrics')
    @mock.patch.object(aidegen_main, 'main_with_message')
    def test_main_with_normal(self, mock_main, mock_ends_metrics,
                              mock_is_whole_tree, mock_starts_metrics):
        """Test main with normal conditions."""
        aidegen_main.main(['-h'])
        self.assertFalse(mock_main.called)
        mock_ends_metrics.assert_called_with(constant.EXIT_CODE_NORMAL)
        mock_is_whole_tree.return_value = True
        aidegen_main.main([''])
        mock_starts_metrics.assert_called_with([constant.ANDROID_TREE])

    @mock.patch.object(aidegen_metrics, 'ends_asuite_metrics')
    @mock.patch.object(aidegen_main, 'main_with_message')
    def test_main_with_build_fail_errors(self, mock_main, mock_ends_metrics):
        """Test main with raising build failure error conditions."""
        mock_main.side_effect = errors.BuildFailureError
        with self.assertRaises(errors.BuildFailureError):
            aidegen_main.main([''])
            _, exc_value, exc_traceback = sys.exc_info()
            msg = str(exc_value)
            mock_ends_metrics.assert_called_with(
                constant.EXIT_CODE_AIDEGEN_EXCEPTION, exc_traceback, msg)

    @mock.patch.object(aidegen_metrics, 'ends_asuite_metrics')
    @mock.patch.object(aidegen_main, 'main_with_message')
    def test_main_with_io_errors(self, mock_main, mock_ends_metrics):
        """Test main with raising IO error conditions."""
        mock_main.side_effect = IOError
        with self.assertRaises(IOError):
            aidegen_main.main([''])
            _, exc_value, exc_traceback = sys.exc_info()
            msg = str(exc_value)
            mock_ends_metrics.assert_called_with(
                constant.EXIT_CODE_EXCEPTION, exc_traceback, msg)


if __name__ == '__main__':
    unittest.main()
