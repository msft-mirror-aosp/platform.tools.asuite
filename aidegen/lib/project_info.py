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

The information include some data or methods such as:
    - project_absolute_path: A string which has the absolute path of project.
    - TODO(b/112523202): Generate a dictionary named module_dependency with
                         module dependency information of a project.
    - TODO(b/112523194): Generate a dictionary named source_path with source and
                         jar paths of dependent modules.
    - TODO(b/112522635): A boolean value named is_generate_ide_project_file to
                         verify whether IDE project files are generated or not.
    - TODO(b/112578616): A boolean value named launch_ide_successfully to
                         verify whether IDE is launched or not.
    - _is_correct_module_path: A method to clarify Android.mk or Android.bp
                               exists in real_path.

For example:
    Users have to change directory to android source project root first then run
    aidegen tool.
    $ cd /user/home/aosp
    $ aidegen packages/apps/Settings
    or change directory to the path of project then run aidegen tool.
    $ cd /user/home/aosp/packages/apps/Settings
    $ aidegen
    Description:
    - The absolute path of project is /user/home/aosp/pcakages/apps/Settings.
"""

from __future__ import absolute_import

import os

from atest import constants


class ProjectInfo(object):
    """Project information.

    Attributes:
        project_absolute_path: The absolute path to the project.
        android_root_path: The path to android source root.
        project_relative_path: The relative path to the project by
                               android_root_path.
    """

    def __init__(self, project_path, module_info):
        """ProjectInfo initialize.

        Args:
            project_path: Probably none or a path from argument which users
                          types.
            module_info: A ModuleInfo class contains data of module-info.json.
        """
        self.project_absolute_path = (os.path.join(os.getcwd(), project_path)
                                      if project_path else os.getcwd())
        self.android_root_path = os.environ.get(constants.ANDROID_BUILD_TOP)
        self.project_relative_path = os.path.relpath(self.project_absolute_path,
                                                     self.android_root_path)
        modules = module_info.get_module_names(self.project_relative_path)
        # TODO: Find the closest parent module if no modules defined at project
        #       path.
        assert modules, ('No modules defined at %s.' %
                         self.project_relative_path)
