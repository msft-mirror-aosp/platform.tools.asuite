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
from aidegen.lib.common_util import read_file_content
from aidegen.lib.eclipse_project_file_gen import EclipseConf


# pylint: disable=protected-access
class EclipseConfUnittests(unittest.TestCase):
    """Unit tests for generate_project_file.py"""
    _ROOT_PATH = '/android/root'
    _PROJECT_RELPATH = 'module/path'
    _PROJECT_ABSPATH = os.path.join(_ROOT_PATH, _PROJECT_RELPATH)
    _PROJECT_NAME = 'test'
    _LINK_TEMPLATE = ('                <link><name>%s</name><type>2</type>'
                      '<location>%s</location></link>\n')
    _TEST_DATA_PATH = unittest_constants.TEST_DATA_PATH
    _PROJECT_SAMPLE = os.path.join(_TEST_DATA_PATH, 'eclipse.project')

    def test_gen_link(self):
        """Test get_link return a correct link resource config."""
        constant.ANDROID_ROOT_PATH = self._ROOT_PATH
        name = os.path.join(constant.KEY_DEPENDENCIES, self._PROJECT_RELPATH)
        expected_link = self._LINK_TEMPLATE % (name, self._PROJECT_ABSPATH)
        generated_link = EclipseConf._gen_link(self._PROJECT_RELPATH)
        self.assertEqual(generated_link, expected_link)

    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_create_project_content(self, mock_project_info):
        """Test _create_project_content."""
        constant.ANDROID_ROOT_PATH = self._ROOT_PATH
        mock_project_info.project_absolute_path = self._PROJECT_ABSPATH
        mock_project_info.module_name = self._PROJECT_NAME
        mock_project_info.source_path = {
            'jar_module_path': {
                '': self._PROJECT_RELPATH
            },
            'r_java_path': {constant.CENTRAL_R_PATH}
        }
        expected_content = read_file_content(self._PROJECT_SAMPLE)
        eclipse_config = EclipseConf(mock_project_info)
        eclipse_config._create_project_content()
        generated_content = eclipse_config.project_content
        self.assertEqual(generated_content, expected_content)


if __name__ == '__main__':
    unittest.main()
