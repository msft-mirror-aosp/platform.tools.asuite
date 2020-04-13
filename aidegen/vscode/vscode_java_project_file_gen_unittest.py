#!/usr/bin/env python3
#
# Copyright 2020 - The Android Open Source Project
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


"""Unittests for ide_util."""

import os
import unittest
from unittest import mock

from aidegen.lib import common_util
from aidegen.vscode import vscode_java_project_file_gen


# pylint: disable=protected-access
class JavaProjectFileGenUnittests(unittest.TestCase):
    """Unit tests for ide_util.py."""

    @mock.patch.object(
        vscode_java_project_file_gen, '_create_code_workspace_file_content')
    @mock.patch.object(common_util, 'get_android_root_dir')
    def test_vdcode_apply_optional_config(
            self, mock_get_root, mock_ws_content):
        """Test IdeVSCode's apply_optional_config method."""
        mock_get_root.return_value = 'a/b'
        vscode_project = vscode_java_project_file_gen.JavaProjectGen()
        vscode_project.generate_code_workspace_file(
            ['a/b/path_to_project1', 'a/b/path_to_project2'])
        self.assertTrue(mock_get_root.called)
        self.assertTrue(mock_ws_content.called)

    @mock.patch.object(common_util, 'dump_json_dict')
    def test_create_code_workspace_file_content(self, mock_dump):
        """Test _create_code_workspace_file_content function."""
        abs_path = 'a/b'
        folder_name = 'Settings'
        res = vscode_java_project_file_gen._create_code_workspace_file_content(
            {'folders': [{'name': folder_name, 'path': abs_path}]})
        self.assertTrue(mock_dump.called)
        file_name = ''.join(
            [folder_name, vscode_java_project_file_gen._VSCODE_WORKSPACE_EXT])
        file_path = os.path.join(abs_path, file_name)
        self.assertEqual(res, file_path)


if __name__ == '__main__':
    unittest.main()
