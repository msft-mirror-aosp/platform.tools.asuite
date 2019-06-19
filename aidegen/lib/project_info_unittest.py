#!/usr/bin/env python3
#
# Copyright 2018, The Android Open Source Project
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

"""Unittests for source_locator."""

import os
import unittest
from unittest import mock

from aidegen import unittest_constants
from aidegen.lib import common_util
from aidegen.lib import project_info

_MODULE_INFO = {
    'm1': {'class': ['JAVA_LIBRARIES'], 'dependencies': ['m2', 'm6'],
           'path': ['m1']},
    'm2': {'class': ['JAVA_LIBRARIES'], 'dependencies': ['m3', 'm4']},
    'm3': {'class': ['JAVA_LIBRARIES'], 'dependencies': []},
    'm4': {'class': ['JAVA_LIBRARIES'], 'dependencies': ['m6']},
    'm5': {'class': ['JAVA_LIBRARIES'], 'dependencies': []},
    'm6': {'class': ['JAVA_LIBRARIES'], 'dependencies': ['m2']},
}
_EXPECT_DEPENDENT_MODULES = {
    'm1': {'class': ['JAVA_LIBRARIES'], 'dependencies': ['m2', 'm6'],
           'path': ['m1'], 'depth': 0},
    'm2': {'class': ['JAVA_LIBRARIES'], 'dependencies': ['m3', 'm4'],
           'depth': 1},
    'm3': {'class': ['JAVA_LIBRARIES'], 'dependencies': [], 'depth': 2},
    'm4': {'class': ['JAVA_LIBRARIES'], 'dependencies': ['m6'], 'depth': 2},
    'm6': {'class': ['JAVA_LIBRARIES'], 'dependencies': ['m2'], 'depth': 1},
}


# pylint: disable=protected-access
# pylint: disable=invalid-name
class ProjectInfoUnittests(unittest.TestCase):
    """Unit tests for project_info.py"""

    def setUp(self):
        """Initialize arguments for ProjectInfo."""
        self.args = mock.MagicMock()
        self.args.module_name = 'm1'
        self.args.project_path = ''

    @mock.patch('atest.module_info.ModuleInfo')
    def test_get_dep_modules(self, mock_module_info):
        """Test get_dep_modules recursively find dependent modules."""
        mock_module_info.name_to_module_info = _MODULE_INFO
        mock_module_info.is_module.return_value = True
        mock_module_info.get_paths.return_value = ['m1']
        mock_module_info.get_module_names.return_value = ['m1']
        project_info.ProjectInfo.modules_info = mock_module_info
        proj_info = project_info.ProjectInfo(self.args.module_name)
        self.assertEqual(proj_info.dep_modules, _EXPECT_DEPENDENT_MODULES)

    @mock.patch.object(common_util, 'get_android_root_dir')
    def test_get_target_name(self, mock_get_root):
        """Test _get_target_name with different conditions."""
        mock_get_root.return_value = unittest_constants.TEST_DATA_PATH
        self.assertEqual(
            project_info.ProjectInfo._get_target_name(
                unittest_constants.TEST_MODULE,
                unittest_constants.TEST_DATA_PATH),
            os.path.basename(unittest_constants.TEST_DATA_PATH))
        self.assertEqual(
            project_info.ProjectInfo._get_target_name(
                unittest_constants.TEST_MODULE,
                unittest_constants.TEST_PATH),
            unittest_constants.TEST_MODULE)


if __name__ == '__main__':
    unittest.main()
