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

import os
import unittest
from unittest import mock

import aidegen.unittest_constants as uc
from aidegen import aidegen_main
from aidegen.lib import aidegen_metrics
from aidegen import constant
from aidegen.lib import common_util
from aidegen.lib.errors import IDENotExistError
from aidegen.lib.errors import ProjectPathNotExistError
from aidegen.lib.ide_util import IdeUtil
from aidegen.lib.eclipse_project_file_gen import EclipseConf
from aidegen.lib.project_info import ProjectInfo
from aidegen.lib.project_file_gen import ProjectFileGenerator
from atest import module_info


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

    @mock.patch('aidegen.lib.project_config.ProjectConfig')
    @mock.patch.object(ProjectFileGenerator, 'generate_ide_project_files')
    @mock.patch.object(EclipseConf, 'generate_ide_project_files')
    def test_generate_project_files(self, mock_eclipse, mock_ide, mock_config):
        """Test _generate_project_files with different conditions."""
        projects = ['module_a', 'module_v']
        ProjectInfo.config = mock_config
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
    @mock.patch.object(aidegen_metrics, 'log_usage')
    def test_show_collect_data_notice(self, mock_log, mock_get):
        """Test main process always run through the target test function."""
        target = 'nothing'
        args = aidegen_main._parse_args([target, '-s', '-n'])
        with self.assertRaises(ProjectPathNotExistError):
            err = common_util.PATH_NOT_EXISTS_ERROR.format(target)
            mock_get.side_effect = ProjectPathNotExistError(err)
            aidegen_main.main_without_message(args)
            self.assertTrue(mock_log.called)

    @mock.patch.object(common_util, 'get_related_paths')
    def test_compile_targets_for_whole_android_tree(self, mock_get):
        """Test _add_whole_android_tree_project with different conditions."""
        mod_info = module_info.ModuleInfo()
        targets = ['']
        cwd = common_util.get_android_root_dir()
        self.assertEqual(
            targets,
            aidegen_main._compile_targets_for_whole_android_tree(
                mod_info, targets, cwd))
        base_dir = 'frameworks/base'
        expected_targets = ['', base_dir]
        cwd = os.path.join(common_util.get_android_root_dir(), base_dir)
        mock_get.return_value = None, cwd
        self.assertEqual(
            expected_targets,
            aidegen_main._compile_targets_for_whole_android_tree(
                mod_info, targets, cwd))
        targets = [base_dir]
        cwd = common_util.get_android_root_dir()
        self.assertEqual(
            expected_targets,
            aidegen_main._compile_targets_for_whole_android_tree(
                mod_info, targets, cwd))

    @mock.patch.object(os, 'getcwd')
    def test_is_whole_android_tree(self, mock_getcwd):
        """Test _is_whole_android_tree with different conditions."""
        self.assertTrue(aidegen_main._is_whole_android_tree(['a'], True))
        self.assertFalse(aidegen_main._is_whole_android_tree(['a'], False))
        mock_getcwd.return_value = common_util.get_android_root_dir()
        self.assertTrue(aidegen_main._is_whole_android_tree([''], False))
        mock_getcwd.return_value = 'frameworks/base'
        self.assertFalse(aidegen_main._is_whole_android_tree([''], False))


if __name__ == '__main__':
    unittest.main()
