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

"""Native project information."""

from __future__ import absolute_import

from aidegen.lib import common_util
from aidegen.lib import native_module_info
from aidegen.lib import project_config
from aidegen.lib import project_info


class NativeProjectInfo():
    """Native project information.

    Class attributes:
        modules_info: An AidegenModuleInfo instance whose name_to_module_info is
                      a dictionary of module_bp_cc_deps.json.

    Attributes:
        module_name: A string of the native project's module name.
        gen_includes: A set of the include paths have to be generated.
    """

    modules_info = None

    def __init__(self, target):
        """ProjectInfo initialize.

        Args:
            target: A native module or project path from users' input will be
                    checked if they contain include paths need to be generated,
                    e.g., in 'libui' module.
            'out/soong/../android.frameworks.bufferhub@1.0_genc++_headers/gen'
                    we should call 'm android.frameworks.bufferhub@1.0' to
                    generate the include header files in,
                    'android.frameworks.bufferhub@1.0_genc++_headers/gen'
                    direcotry.
        """
        self._init_modules_info()
        _, abs_path = common_util.get_related_paths(
            NativeProjectInfo.modules_info, target)
        self.module_name = project_info.ProjectInfo.get_target_name(
            target, abs_path)
        self.gen_includes = NativeProjectInfo.modules_info.get_gen_includes(
            self.module_name)
        config = project_config.ProjectConfig.get_instance()
        if not config.is_skip_build and self.gen_includes:
            project_info.batch_build_dependencies(
                config.verbose, self.gen_includes)

    @classmethod
    def _init_modules_info(cls):
        """Initializes the class attribute: modules_info."""
        if cls.modules_info:
            return
        cls.modules_info = native_module_info.NativeModuleInfo()

    @staticmethod
    def generate_projects(targets):
        """Generates a list of projects in one time by a list of module names.

        Args:
            targets: A list of native modules or project paths from users' input
            will be checked if they contain include paths need to be generated.

        Returns:
            List: A list of ProjectInfo instances.
        """
        return [NativeProjectInfo(target) for target in targets]
