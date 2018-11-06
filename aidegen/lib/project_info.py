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

"""Project information."""

from __future__ import absolute_import

import os

from atest import constants

_KEY_DEP = 'dependencies'


class ProjectInfo():
    """Project information.

    Class attributes:
        android_root_path: The path to android source root.

    Attributes:
        project_absolute_path: The absolute path to the project.
        project_relative_path: The relative path to the project by
                               android_root_path.
        project_module_names: A list of module names under project_absolute_path
                              directory or it's subdirectories.
        modules_info: A dict of all modules info by combining module-info.json
                      with module_bp_java_deps.json.
        dep_modules: A dict has recursively dependent modules of
                     project_module_names.
    """

    android_root_path = os.environ.get(constants.ANDROID_BUILD_TOP)

    def __init__(self, args, module_info):
        """ProjectInfo initialize.

        Args:
            args: Includes args.module_name or args.project_path from user
                  input, args.module_name is at high priority to decide the
                  project path.
            module_info: A ModuleInfo class contains data of module-info.json.
        """
        # TODO: Find the closest parent module if no modules defined at project
        #       path.
        rel_path, abs_path = self.get_related_path(args.target, module_info)
        self.project_module_names = module_info.get_module_names(rel_path)
        self.project_relative_path = rel_path
        self.project_absolute_path = abs_path
        self.modules_info = {}
        self.dep_modules = {}
        self.iml_path = ''
        # Append default hard-code modules, source paths and jar files.
        # TODO(b/112058649): Do more research to clarify how to remove these
        #                    hard-code sources.
        self.project_module_names.extend([
            # Framework module is always needed for dependencies but it might
            # not be located by module dependency.
            'framework',
            # The module can't be located through module dependency. Without it,
            # a lot of java files will have errors "cannot resolve symbol" in
            # IntelliJ since they import packages android.Manifest and
            # com.android.internal.R.
            'org.apache.http.legacy.stubs.system'
        ])
        self.source_path = {
            'source_folder_path': set(),
            'test_folder_path': set(),
            'jar_path': set()
        }

    @classmethod
    def get_related_path(cls, target, module_info):
        """Get the relative and absolute paths of target from module-info.

        Args:
            target: A string user input from command line. It could be
                    several cases such as:
                    1. Module name. e.g. Settings
                    2. Module path. e.g. packages/apps/Settings
                    3. Relative path. e.g. ../../packages/apps/Settings
                    4. Current directory. e.g. . or no argument
            module_info: A ModuleInfo class contains data of module-info.json.

        Retuen:
            rel_path: The relative path of a module.
            abs_path: The absolute path of a module.
        """
        if target:
            # User inputs a module name.
            if module_info.is_module(target):
                rel_path = module_info.get_paths(target)[0]
                abs_path = os.path.join(cls.android_root_path, rel_path)
            # User inputs a module path.
            elif module_info.get_module_names(target):
                rel_path = target
                abs_path = os.path.join(cls.android_root_path, rel_path)
            # User inputs a relative path of current directory.
            else:
                abs_path = os.path.abspath(os.path.join(os.getcwd(), target))
                rel_path = os.path.relpath(abs_path, cls.android_root_path)
        else:
            # User doesn't input.
            abs_path = os.getcwd()
            rel_path = os.path.relpath(abs_path, cls.android_root_path)
        return rel_path, abs_path

    def set_modules_under_project_path(self):
        """Find modules under the project path whose class is JAVA_LIBRARIES."""
        for name, data in self.modules_info.items():
            if ('class' in data and 'JAVA_LIBRARIES' in data['class']
                    and 'path' in data and data['path'][0].startswith(
                        self.project_relative_path)):
                if name not in self.project_module_names:
                    self.project_module_names.append(name)

    def get_dep_modules(self, module_names=None):
        """Recursively find dependent modules of the project.

        Find dependent modules by dependencies parameter of each module.
        For example:
            The module_names is ['m1'].
            The modules_info is
            {
                'm1': {'dependencies': ['m2'], 'path': ['path_to_m1']},
                'm2': {'path': ['path_to_m4']},
                'm3': {'path': ['path_to_m1']}
                'm4': {'path': []}
            }
            The result dependent modules are:
            {
                'm1': {'dependencies': ['m2'], 'path': ['path_to_m1']},
                'm2': {'path': ['path_to_m4']},
                'm3': {'path': ['path_to_m1']}
            }
            Note that:
                1. m4 is not in the result as it's not among dependent modules.
                2. m3 is in the result as it has the same path to m1.

        Args:
            module_names: A list of module names.

        Returns:
            deps: A dict contains all dependent modules data of given modules.
        """
        dep = {}
        if not module_names:
            self.set_modules_under_project_path()
            module_names = self.project_module_names
        for name in module_names:
            if name in self.modules_info:
                if name not in dep:
                    dep[name] = self.modules_info[name]
                if _KEY_DEP in dep[name] and dep[name][_KEY_DEP]:
                    dep.update(self.get_dep_modules(dep[name][_KEY_DEP]))
        return dep
