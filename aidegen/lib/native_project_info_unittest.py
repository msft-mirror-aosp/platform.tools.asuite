#!/usr/bin/env python3
#
# Copyright 2020, The Android Open Source Project
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

"""Unittests for native_util."""

import unittest
from unittest import mock

from aidegen.lib import common_util
from aidegen.lib import native_module_info
from aidegen.lib import native_project_info
from aidegen.lib import project_config
from aidegen.lib import project_info


# pylint: disable=protected-access
class NativeProjectInfoUnittests(unittest.TestCase):
    """Unit tests for native_project_info.py"""

    @mock.patch.object(native_module_info, 'NativeModuleInfo')
    def test_init_modules_info(self, mock_mod_info):
        """Test initializing the class attribute: modules_info."""
        native_project_info.NativeProjectInfo.modules_info = None
        native_project_info.NativeProjectInfo._init_modules_info()
        self.assertEqual(mock_mod_info.call_count, 1)
        native_project_info.NativeProjectInfo._init_modules_info()
        self.assertEqual(mock_mod_info.call_count, 1)

    @mock.patch.object(project_info, 'batch_build_dependencies')
    @mock.patch.object(
        project_config.ProjectConfig, 'get_instance')
    @mock.patch.object(project_info.ProjectInfo, 'get_target_name')
    @mock.patch.object(common_util, 'get_related_paths')
    @mock.patch.object(
        native_project_info.NativeProjectInfo, '_init_modules_info')
    def test_init(self, mock_mod_info, mock_get_rel, mock_get_name,
                  mock_get_instance, mock_build):
        """Test initializing NativeProjectInfo woth different conditions."""
        target = 'libui'
        mock_mod_info.return_value = None
        mock_get_rel.return_value = 'rel_path', 'path_to_something'
        mock_get_name.return_value = target
        mod_info = mock.Mock()
        native_project_info.NativeProjectInfo.modules_info = mod_info
        config = mock.Mock()
        mock_get_instance.return_value = config
        config.is_skip_build = True
        native_project_info.NativeProjectInfo(target)
        self.assertFalse(mock_build.called)
        mod_info.get_gen_includes.return_value = None
        config.is_skip_build = False
        native_project_info.NativeProjectInfo(target)
        self.assertFalse(mock_build.called)
        mod_info.get_gen_includes.return_value = ['path_to_include']
        config.is_skip_build = True
        native_project_info.NativeProjectInfo(target)
        self.assertFalse(mock_build.called)
        config.is_skip_build = False
        native_project_info.NativeProjectInfo(target)
        self.assertTrue(mock_build.called)


if __name__ == '__main__':
    unittest.main()
