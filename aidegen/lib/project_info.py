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

from aidegen import constant
from aidegen.lib.common_util import get_related_paths
from aidegen.lib.module_info_util import generate_module_info_json

_KEY_DEP = 'dependencies'


class ProjectInfo():
    """Project information.

    Class attributes:
        android_root_path: The path to android source root.
        modules_info: A dict of all modules info by combining module-info.json
                      with module_bp_java_deps.json.

    Attributes:
        project_absolute_path: The absolute path to the project.
        project_relative_path: The relative path to the project by
                               android_root_path.
        project_module_names: A list of module names under project_absolute_path
                              directory or it's subdirectories.
        dep_modules: A dict has recursively dependent modules of
                     project_module_names.
    """

    android_root_path = constant.ANDROID_ROOT_PATH
    modules_info = {}

    def __init__(self, module_info, target=None):
        """ProjectInfo initialize.

        Args:
            module_info: A ModuleInfo class contains data of module-info.json.
            target: Includes target module or project path from user input, when
                    locating the target, project with matching module name of
                    the given target has a higher priority than project path.
        """
        # TODO: Find the closest parent module if no modules defined at project
        #       path.
        rel_path, abs_path = get_related_paths(module_info, target)
        self.project_module_names = module_info.get_module_names(rel_path)
        self.project_relative_path = rel_path
        self.project_absolute_path = abs_path
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
            'jar_path': set()
        }
        self.dep_modules = self.get_dep_modules()

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

    @classmethod
    def generate_projects(cls, module_info, targets, verbose):
        """Generate a list of projects in one time by a list of module names.

        Args:
            module_info: An Atest module-info instance.
            targets: A list of target modules or project paths from user input,
                     when locating the target, project with matched module name
                     of the target has a higher priority than project path.
            verbose: A boolean. If true, display DEBUG level logs.

        Returns:
            List: A list of ProjectInfo instances.
        """
        cls.modules_info = generate_module_info_json(module_info, targets,
                                                     verbose)
        return [ProjectInfo(module_info, target) for target in targets]
