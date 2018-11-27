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

import logging
import os

from aidegen import constant
from aidegen.lib.common_util import get_related_paths
from aidegen.lib.module_info_util import generate_module_info_json
from atest import atest_utils
from atest import constants

_KEY_DEP = 'dependencies'
_ANDROID_MK = 'Android.mk'
_ANDROID_BP = 'Android.bp'
_ANDROID_MK_WARN = (
    '%s contains Android.mk file(s) in its dependencies:\n%s\nPlease help '
    'convert these files into blueprint format in the future, otherwise '
    'AIDEGen may not be able to include all module dependencies.')
_FILTER_CLASSES = {'APPS', 'JAVA_LIBRARIES'}


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
            module_info: A ModuleInfo instance contains data of
                         module-info.json.
            target: Includes target module or project path from user input, when
                    locating the target, project with matching module name of
                    the given target has a higher priority than project path.
        """
        # TODO: Find the closest parent module if no modules defined at project
        #       path.
        rel_path, abs_path = get_related_paths(module_info, target)
        # If the project is for entire Android source tree, change the target to
        # source tree's root folder name. In this way, we give IDE project file
        # a more specific name. e.g, master.iml.
        if abs_path == constant.ANDROID_ROOT_PATH:
            target = os.path.basename(abs_path)
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
            'test_folder_path': set(),
            'jar_path': set()
        }
        self.dep_modules = self.get_dep_modules()
        mk_set = set(self._search_android_make_files(module_info))
        if mk_set:
            print('\n%s\n%s\n' % (atest_utils.colorize(
                "Warning...", constants.MAGENTA), _ANDROID_MK_WARN %
                                  (target, '\n'.join(mk_set))))

    def _search_android_make_files(self, module_info):
        """Search project and dependency modules contain Android.mk files.

        Args:
            module_info: A ModuleInfo instance contains data of
                         module-info.json.

        Yields:
            A string: relative path of Android.mk.
        """
        android_mk = os.path.join(self.project_absolute_path, _ANDROID_MK)
        android_bp = os.path.join(self.project_absolute_path, _ANDROID_BP)
        # If there is only Android.mk but no Android.bp, we'll show the warning
        # message, otherwise we wont.
        if os.path.isfile(android_mk) and not os.path.isfile(android_bp):
            yield '\t' + os.path.join(self.project_relative_path, _ANDROID_MK)
        for module_name in self.dep_modules:
            rel_path, abs_path = get_related_paths(module_info, module_name)
            mod_mk = os.path.join(abs_path, _ANDROID_MK)
            mod_bp = os.path.join(abs_path, _ANDROID_BP)
            if os.path.isfile(mod_mk) and not os.path.isfile(mod_bp):
                yield '\t' + os.path.join(rel_path, _ANDROID_MK)

    def set_modules_under_project_path(self):
        """Find modules whose class is qualified to be included under the
           project path.
        """
        logging.info('Find modules whose class is in %s under %s.',
                     _FILTER_CLASSES, self.project_relative_path)
        for name, data in self.modules_info.items():
            if ('class' in data and 'path' in data
                    and data['path'][0].startswith(self.project_relative_path)):
                if not set(data['class']).intersection(_FILTER_CLASSES):
                    logging.info(('Module %s\'s class setting is %s, none of '
                                  'which is included in %s, skipping this '
                                  'module in the project.'),
                                 name, data['class'], _FILTER_CLASSES)
                elif name not in self.project_module_names:
                    self.project_module_names.append(name)

    def get_dep_modules(self, module_names=None, depth=0):
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
                'm1': {'dependencies': ['m2'], 'path': ['path_to_m1']
                       'depth': 0},
                'm2': {'path': ['path_to_m4'], 'depth': 1},
                'm3': {'path': ['path_to_m1'], 'depth': 0}
            }
            Note that:
                1. m4 is not in the result as it's not among dependent modules.
                2. m3 is in the result as it has the same path to m1.

        Args:
            module_names: A list of module names.
            depth: An integer shows the depth of module dependency referenced by
                   source. Zero means the max module depth.

        Returns:
            deps: A dict contains all dependent modules data of given modules.
        """
        dep = {}
        if not module_names:
            self.set_modules_under_project_path()
            module_names = self.project_module_names
        for name in module_names:
            if name in self.modules_info:
                dep[name] = self.modules_info[name]
                if _KEY_DEP in dep[name] and dep[name][_KEY_DEP]:
                    dep.update(
                        self.get_dep_modules(dep[name][_KEY_DEP], depth + 1))
                dep[name][constant.KEY_DEPTH] = depth
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
