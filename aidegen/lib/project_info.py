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
    - real_path: A string which have the absolute path of project.
    - TODO(b/112523202): Generate a dictionary named module_dependency which
                         have dependent modules of project.
    - TODO(b/112523194): Generate a dictionary named source_path which have
                         source and jar paths of dependent modules.
    - TODO(b/112522635): A boolean value named is_generate_ide_project_file to
                         verify whether IDE project files are generated or not.
    - TODO(b/112578616): A boolean value named launch_ide_successfully to
                         verify whether IDE is launched or not.
    - _is_correct_module_path: A method to clarify Android.mk or Android.bp
                               exist in real_path.

For example:
    User have to change directory to AOSP root first then run aidegen tool.
    $ cd /user/home/aosp
    $ aidegen packages/apps/Settings
    or change directory to the path of project then run aidegen tool.
    $ cd /user/home/aosp/packages/apps/Settings
    $ aidegen
    Description:
    - The real path of project is /user/home/aosp/pcakages/apps/Settings.
    - The method _is_correct_module_path return True if Android.mk or
      Android.bp exist in the real path of project.
"""

from __future__ import absolute_import

import os

from aidegen.lib import errors

ANDROID_BLUEPRINT_NAME = "Android.bp"
ANDROID_MAKEFILE_NAME = "Android.mk"


class ProjectInfo(object):
    """Project information.

    Attributes:
        real_path: The absolute path of project.
    """

    def __init__(self, args):
        """ProjectInfo initialize.

        Args:
            args: An argparse.Namespace class instance holding parsed args.
        """
        self.real_path = (os.path.join(os.getcwd(), args.project_path)
                          if args.project_path else os.getcwd())
        if not self._is_correct_module_path():
            raise errors.ProjectPathError(
                "%s is not a correct module path." % self.real_path)

    def _is_correct_module_path(self):
        """Check if Android.mk or Android.bp exist in project_path.

        Returns:
            Boolean: True if Android.mk or Android.bp exist.
        """
        makefile = os.path.join(self.real_path, ANDROID_MAKEFILE_NAME)
        blueprint = os.path.join(self.real_path, ANDROID_BLUEPRINT_NAME)
        return os.path.exists(makefile) or os.path.exists(blueprint)
