#!/usr/bin/env python3
#
# Copyright 2018 - The Android Open Source Project
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
"""Project information.

The information include methods such as:
    - TODO(b/112523202): Generate a dictionary named module_dependency with
                         module dependency information of a project.
    - TODO(b/112523194): Generate a dictionary named source_path with source and
                         jar paths of dependent modules.
    - TODO(b/112522635): A boolean value named is_generate_ide_project_file to
                         verify whether IDE project files are generated or not.
    - TODO(b/112578616): A boolean value named launch_ide_successfully to
                         verify whether IDE is launched or not.

For example:
    - The absolute path of project is /user/home/aosp/pcakages/apps/Settings.
    1. Users have to change directory to android source project root first then
       run aidegen tool.
       $ cd /user/home/aosp
       $ aidegen -p packages/apps/Settings
       or
       $ aidegen -m Settings
    2. Change directory to the path of project then run aidegen tool.
       $ cd /user/home/aosp/packages/apps/Settings
       $ aidegen
"""

from __future__ import absolute_import

import os

from atest import constants


class ProjectInfo(object):
    """Project information.

    Attributes:
        android_root_path: The path to android source root.
        project_absolute_path: The absolute path to the project.
        project_relative_path: The relative path to the project by
                               android_root_path.
        project_modules: A list of modules with the same path.
    """

    def __init__(self, args, module_info):
        """ProjectInfo initialize.

        Args:
            args: Includes args.module_name or args.project_path from user input
                  , args.module_name is at high priority to decide the project
                  path.
            module_info: A ModuleInfo class contains data of module-info.json.
        """
        self.android_root_path = os.environ.get(constants.ANDROID_BUILD_TOP)
        # TODO: Find the closest parent module if no modules defined at project
        #       path.
        if args.module_name:
            assert module_info.is_module(
                args.module_name), ('Module:%s not exists.' % args.module_name)
            self.project_relative_path = module_info.get_paths(
                args.module_name)[0]
            self.project_absolute_path = os.path.join(
                self.android_root_path, self.project_relative_path)
        else:
            self.project_absolute_path = (
                os.path.join(self.android_root_path, args.project_path)
                if args.project_path else os.getcwd())
            self.project_relative_path = os.path.relpath(
                self.project_absolute_path, self.android_root_path)
        self.project_modules = module_info.get_module_names(
            self.project_relative_path)
        assert self.project_modules, (
            'No modules defined at %s.' % self.project_relative_path)
