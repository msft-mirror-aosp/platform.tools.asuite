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

"""It is an AIDEGen sub task: generate VSCode Java related config files."""

import os

from aidegen import constant
from aidegen.lib import common_util

_NAME = 'name'
_FOLDERS = 'folders'
_VSCODE_WORKSPACE_EXT = '.code-workspace'


class JavaProjectGen():
    """VSCode Java project file generator.

    Usage:
        vscode_project = vscode_java_project_file_gen.JavaProjectGen
        abs_jpath = vscode_project.generate_code_workspace_file(abs_paths)
        _launch_ide(ide_util_obj, abs_jpath)

    Attributes:
        _module_info: A dictionary contains the module's information.
                      Here's an example,
                      module_info = {
                          'path': 'relative/path/to/the/module',
                          'src': [...],
                          'dependencies': [...],
                          'classes': [...],
                          'jar': [...],
                          ...
                      }

        _is_main_module: A boolean, True if the module is a main module else
                         False.
    """
    # TODO(b/152452857): For now module_info default is None, implement it in
    # another CL.
    def __init__(self, module_info=None, is_main_module=False):
        """JavaProjectGen initialization.

        Args:
            module_info: A dictionary contains the module's information.
            is_main_module: A boolean, True if the module is a main module else
                            False.
        """
        self._module_info = module_info
        self._is_main_module = is_main_module

    @classmethod
    def generate_code_workspace_file(cls, abs_paths):
        """Generates .code-workspace file to launch multiple projects in VSCode.

        The rules:
            1. Get all folder names.
            2. Get file name and absolute file path for .code-workspace file.
            3. Generate .code-workspace file content.
            4. Create .code-workspace file.

        Args:
            abs_paths: A list of absolute paths of all modules in the projects.

        Returns:
            A string of the absolute path of ${project}.code-workspace file.
        """
        workspace_dict = {_FOLDERS: []}
        root_dir = common_util.get_android_root_dir()
        for path in abs_paths:
            workspace_dict[_FOLDERS].append(
                {_NAME: os.path.relpath(path, root_dir).replace(os.sep, '.'),
                 constant.KEY_PATH: path})
        return _create_code_workspace_file_content(workspace_dict)


def _create_code_workspace_file_content(workspace_dict):
    """Create '${project}.code-workspace' file content with workspace_dict.

    Args:
        workspace_dict: A dictionary contains the 'folders', 'name', 'path'
                        formats.

    Returns:
        A string of the absolute path of ${project}.code-workspace file.
    """
    folder_name = workspace_dict[_FOLDERS][0][_NAME]
    abs_path = workspace_dict[_FOLDERS][0][constant.KEY_PATH]
    file_name = ''.join([folder_name, _VSCODE_WORKSPACE_EXT])
    file_path = os.path.join(abs_path, file_name)
    common_util.dump_json_dict(file_path, workspace_dict)
    return file_path
