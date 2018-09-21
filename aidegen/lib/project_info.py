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
    - TODO(b/112523202): Generate a dictionary named dep_modules with module
                         dependency information of a project.
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

_KEY_DEP = 'dependencies'


class ProjectInfo(object):
    """Project information.

    Attributes:
        android_root_path: The path to android source root.
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

    def __init__(self, args, module_info):
        """ProjectInfo initialize.

        Args:
            args: Includes args.module_name or args.project_path from user
                  input, args.module_name is at high priority to decide the
                  project path.
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
                os.path.join(self.android_root_path, args.project_path) if
                args.project_path else os.getcwd())
            self.project_relative_path = os.path.relpath(
                self.project_absolute_path, self.android_root_path)
        self.project_module_names = module_info.get_module_names(
            self.project_relative_path)
        assert self.project_module_names, (
            'No modules defined at %s.' % self.project_relative_path)
        self.modules_info = {}
        self.dep_modules = {}
        # Append default hard-code modules, source paths and jar files.
        # TODO(b/112058649): Do more research to clarify how to remove these
        #                    hard-code sources.
        # Framework module is always needed for dependencies but it might not be
        # located by module dependency.
        self.project_module_names.append('framework')
        self.source_path = {
            'source_folder_path': [
                # The srcjars folder can't be located through module dependency.
                # Without it, a lot of java files will have errors "cannot
                # resolve symbol" in IntelliJ since they import packages
                # android.Manifest and com.android.internal.R.
                ('out/soong/.intermediates/external/apache-http/org.apache.'
                 'http.legacy.docs.system/android_common/docs/srcjars')
            ],
            'jar_path':[
                # Same issue as source_folder_path since a lot of java file
                # import packages org.xmlpull, libcore.io, org.json, and so on.
                ('out/soong/.intermediates/libcore/core-libart/android_common/'
                 'combined/core-libart.jar')
            ]
        }

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

        Find depentdent modules by dependencies parameter of each module.
        For example:
            The module_names is ['ma'].
            The modules_info is
            {
                'm1': {'dependencies': ['m2'], 'path': ['path_to_m1']},
                'm2': {'dependencies': ['m4']},
                'm3': {'path': ['path_to_m1']},
                'm4': {'dependencies': ['m6']},
                'm5': {'path': []},
                'm6': {'path': []},
            }
            The result dependent modules are:
            {
                'm1': {'dependencies': ['m2'], 'path': ['path_to_m1']},
                'm2': {'dependencies': ['m4']},
                'm3': {'path': ['path_to_m1']},
                'm4': {'dependencies': ['m6']},
                'm6': {'path': []},
            }

        Args:
            module_names: A list of module's name.

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
