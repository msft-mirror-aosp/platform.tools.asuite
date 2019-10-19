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

"""Unittests for generate project file of Eclipse."""

import os
import unittest
from unittest import mock

from aidegen import constant
from aidegen import unittest_constants
from aidegen.lib import common_util
from aidegen.lib import eclipse_project_file_gen


# pylint: disable=protected-access
class EclipseConfUnittests(unittest.TestCase):
    """Unit tests for generate_project_file.py"""
    _ROOT_PATH = '/android/root'
    _PROJECT_RELPATH = 'module/path'
    _PROJECT_ABSPATH = os.path.join(_ROOT_PATH, _PROJECT_RELPATH)
    _PROJECT_NAME = 'test'
    _LINK_TEMPLATE = ('                <link><name>%s</name><type>2</type>'
                      '<location>%s</location></link>\n')
    _PROJECT_SAMPLE = os.path.join(unittest_constants.TEST_DATA_PATH,
                                   'eclipse.project')

    @mock.patch.object(common_util, 'get_android_root_dir')
    def test_gen_link(self, mock_get_root):
        """Test get_link return a correct link resource config."""
        mock_get_root.return_value = self._ROOT_PATH
        name = os.path.join(constant.KEY_DEPENDENCIES, self._PROJECT_RELPATH)
        expected_link = self._LINK_TEMPLATE % (name, self._PROJECT_ABSPATH)
        generated_link = eclipse_project_file_gen.EclipseConf._gen_link(
            self._PROJECT_RELPATH)
        self.assertEqual(generated_link, expected_link)

    @mock.patch('os.path.exists')
    @mock.patch.object(common_util, 'get_android_out_dir')
    @mock.patch.object(common_util, 'get_android_root_dir')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_create_project_content(self, mock_project_info, mock_get_root,
                                    mock_out_dir, mock_dir_exists):
        """Test _create_project_content."""
        mock_get_root.return_value = self._ROOT_PATH
        mock_out_dir.return_value = os.path.join(self._ROOT_PATH, 'out')
        mock_dir_exists.return_value = True
        mock_project_info.project_absolute_path = self._PROJECT_ABSPATH
        mock_project_info.module_name = self._PROJECT_NAME
        mock_project_info.source_path = {
            'source_folder_path': '',
            'test_folder_path': '',
            'jar_module_path': {
                '': self._PROJECT_RELPATH
            },
            'r_java_path': set()
        }
        expected_content = common_util.read_file_content(self._PROJECT_SAMPLE)
        eclipse_config = eclipse_project_file_gen.EclipseConf(mock_project_info)
        eclipse_config._create_project_content()
        generated_content = eclipse_config.project_content
        self.assertEqual(generated_content, expected_content)

    @mock.patch.object(common_util, 'get_android_root_dir')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_gen_src_path_entries(self, mock_project_info, mock_get_root):
        """Test generate source folders' class path entries."""
        mock_get_root.return_value = self._ROOT_PATH
        mock_project_info.project_absolute_path = self._PROJECT_ABSPATH
        mock_project_info.project_relative_path = self._PROJECT_RELPATH
        mock_project_info.module_name = self._PROJECT_NAME
        mock_project_info.source_path = {
            'source_folder_path': set([
                'module/path/src',
                'module/path/test',
            ]),
            'test_folder_path': set(),
            'jar_module_path': {},
            'r_java_path': {}
        }
        expected_result = [
            '    <classpathentry kind="src" path="src"/>\n',
            '    <classpathentry kind="src" path="test"/>\n',
        ]
        eclipse_config = eclipse_project_file_gen.EclipseConf(mock_project_info)
        generated_result = sorted(eclipse_config._gen_src_path_entries())
        self.assertEqual(generated_result, expected_result)

    @mock.patch.object(common_util, 'get_android_root_dir')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_gen_jar_path_entries(self, mock_project_info, mock_get_root):
        """Test generate jar files' class path entries."""
        mock_get_root.return_value = self._ROOT_PATH
        mock_project_info.project_absolute_path = self._PROJECT_ABSPATH
        mock_project_info.project_relative_path = self._PROJECT_RELPATH
        mock_project_info.module_name = self._PROJECT_NAME
        mock_project_info.source_path = {
            'source_folder_path': set(),
            'test_folder_path': set(),
            'jar_module_path': {
                '/abspath/to/the/file.jar': 'relpath/to/the/module',
            },
            'r_java_path': {}
        }
        expected_result = [
            ('    <classpathentry exported="true" kind="lib" '
             'path="/abspath/to/the/file.jar" '
             'sourcepath="dependencies/relpath/to/the/module"/>\n')
        ]
        eclipse_config = eclipse_project_file_gen.EclipseConf(mock_project_info)
        generated_result = eclipse_config._gen_jar_path_entries()
        self.assertEqual(generated_result, expected_result)


if __name__ == '__main__':
    unittest.main()
