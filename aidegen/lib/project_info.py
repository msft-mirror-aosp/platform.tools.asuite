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
from aidegen.lib import common_util

_ANDROID_MK = 'Android.mk'
_ANDROID_BP = 'Android.bp'
_CONVERT_MK_URL = ('https://android.googlesource.com/platform/build/soong/'
                   '#convert-android_mk-files')
_ANDROID_MK_WARN = (
    '{} contains Android.mk file(s) in its dependencies:\n{}\nPlease help '
    'convert these files into blueprint format in the future, otherwise '
    'AIDEGen may not be able to include all module dependencies.\nPlease visit '
    '%s for reference on how to convert makefile.' % _CONVERT_MK_URL)
_ROBOLECTRIC_MODULE = 'Robolectric_all'
_NOT_TARGET = ('Module %s\'s class setting is %s, none of which is included in '
               '%s, skipping this module in the project.')
# The module fake-framework have the same package name with framework but empty
# content. It will impact the dependency for framework when referencing the
# package from fake-framework in IntelliJ.
_EXCLUDE_MODULES = ['fake-framework']


class ProjectInfo:
    """Project information.

    Class attributes:
        modules_info: A AidegenModuleInfo instance whose name_to_module_info is
                      combining module-info.json with module_bp_java_deps.json.
        config: A ProjectConfig instance which contains user preference of
                project.

    Attributes:
        project_absolute_path: The absolute path of the project.
        project_relative_path: The relative path of the project to
                               common_util.get_android_root_dir().
        project_module_names: A list of module names under project_absolute_path
                              directory or it's subdirectories.
        dep_modules: A dict has recursively dependent modules of
                     project_module_names.
        git_path: The project's git path.
        iml_path: The project's iml file path.
        source_path: A dictionary to keep following data:
                     source_folder_path: A set contains the source folder
                                         relative paths.
                     test_folder_path: A set contains the test folder relative
                                       paths.
                     jar_path: A set contains the jar file paths.
                     jar_module_path: A dictionary contains the jar file and
                                      the module's path mapping, only used in
                                      Eclipse.
                     r_java_path: A set contains the relative path to the
                                  R.java files, only used in Eclipse.
                     srcjar_path: A source content descriptor only used in
                                  IntelliJ.
                                  e.g. out/.../aapt2.srcjar!/
                                  The "!/" is a content descriptor for
                                  compressed files in IntelliJ.
        is_main_project: A boolean to verify the project is main project.
    """

    modules_info = None
    config = None

    def __init__(self, target=None, is_main_project=False):
        """ProjectInfo initialize.

        Args:
            target: Includes target module or project path from user input, when
                    locating the target, project with matching module name of
                    the given target has a higher priority than project path.
            is_main_project: A boolean, default is False. True if the target is
                             the main project, otherwise False.
        """
        rel_path, abs_path = common_util.get_related_paths(self.modules_info,
                                                           target)
        self.module_name = self._get_target_name(target, abs_path)
        self.is_main_project = is_main_project
        self.project_module_names = set(
            self.modules_info.get_module_names(rel_path))
        self.project_relative_path = rel_path
        self.project_absolute_path = abs_path
        self.iml_path = ''
        self._set_default_modues()
        self._init_source_path()
        self.dep_modules = self.get_dep_modules()
        self._filter_out_modules()
        self._display_convert_make_files_message()

    def _set_default_modues(self):
        """Append default hard-code modules, source paths and jar files.

        1. framework: Framework module is always needed for dependencies but it
            might not always be located by module dependency.
        2. org.apache.http.legacy.stubs.system: The module can't be located
            through module dependency. Without it, a lot of java files will have
            error of "cannot resolve symbol" in IntelliJ since they import
            packages android.Manifest and com.android.internal.R.
        """
        # TODO(b/112058649): Do more research to clarify how to remove these
        #                    hard-code sources.
        self.project_module_names.update(
            ['framework', 'org.apache.http.legacy.stubs.system'])

    def _init_source_path(self):
        """Initialize source_path dictionary."""
        self.source_path = {
            'source_folder_path': set(),
            'test_folder_path': set(),
            'jar_path': set(),
            'jar_module_path': dict(),
            'r_java_path': set(),
            'srcjar_path': set()
        }

    def _display_convert_make_files_message(self):
        """Show message info users convert their Android.mk to Android.bp."""
        mk_set = set(self._search_android_make_files())
        if mk_set:
            print('\n{} {}\n'.format(
                common_util.COLORED_INFO('Warning:'),
                _ANDROID_MK_WARN.format(self.module_name, '\n'.join(mk_set))))

    def _search_android_make_files(self):
        """Search project and dependency modules contain Android.mk files.

        If there is only Android.mk but no Android.bp, we'll show the warning
        message, otherwise we won't.

        Yields:
            A string: the relative path of Android.mk.
        """
        android_mk = os.path.join(self.project_absolute_path, _ANDROID_MK)
        android_bp = os.path.join(self.project_absolute_path, _ANDROID_BP)
        if os.path.isfile(android_mk) and not os.path.isfile(android_bp):
            yield '\t' + os.path.join(self.project_relative_path, _ANDROID_MK)
        for mod_name in self.dep_modules:
            rel_path, abs_path = common_util.get_related_paths(
                self.modules_info, mod_name)
            if rel_path and abs_path:
                mod_mk = os.path.join(abs_path, _ANDROID_MK)
                mod_bp = os.path.join(abs_path, _ANDROID_BP)
                if os.path.isfile(mod_mk) and not os.path.isfile(mod_bp):
                    yield '\t' + os.path.join(rel_path, _ANDROID_MK)

    def set_modules_under_project_path(self):
        """Find modules whose class is qualified to be included under the
           project path.
        """
        logging.info('Find modules whose class is in %s under %s.',
                     common_util.TARGET_CLASSES, self.project_relative_path)
        for name, data in self.modules_info.name_to_module_info.items():
            if common_util.is_project_path_relative_module(
                    data, self.project_relative_path):
                if self._is_a_target_module(data):
                    self.project_module_names.add(name)
                    if self.modules_info.is_robolectric_test(name):
                        self.project_module_names.add(_ROBOLECTRIC_MODULE)
                else:
                    logging.debug(_NOT_TARGET, name, data['class'],
                                  common_util.TARGET_CLASSES)

    def _filter_out_modules(self):
        """Filter out unnecessary modules."""
        for module in _EXCLUDE_MODULES:
            self.dep_modules.pop(module, None)

    @staticmethod
    def _is_a_target_module(data):
        """Determine if the module is a target module.

        A module's class is in {'APPS', 'JAVA_LIBRARIES', 'ROBOLECTRIC'}

        Args:
            data: the module-info dictionary of the checked module.

        Returns:
            A boolean, true if is a target module, otherwise false.
        """
        if not 'class' in data:
            return False
        return any(x in data['class'] for x in common_util.TARGET_CLASSES)

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
        children = set()
        if not module_names:
            self.set_modules_under_project_path()
            module_names = self.project_module_names
            self.project_module_names = set()
        for name in module_names:
            if (name in self.modules_info.name_to_module_info
                    and name not in self.project_module_names):
                dep[name] = self.modules_info.name_to_module_info[name]
                dep[name][constant.KEY_DEPTH] = depth
                self.project_module_names.add(name)
                if (constant.KEY_DEPENDENCIES in dep[name]
                        and dep[name][constant.KEY_DEPENDENCIES]):
                    children.update(dep[name][constant.KEY_DEPENDENCIES])
        if children:
            dep.update(self.get_dep_modules(children, depth + 1))
        return dep

    @staticmethod
    def generate_projects(targets):
        """Generate a list of projects in one time by a list of module names.

        Args:
            targets: A list of target modules or project paths from user input,
                     when locating the target, project with matched module name
                     of the target has a higher priority than project path.

        Returns:
            List: A list of ProjectInfo instances.
        """
        return [ProjectInfo(target, i == 0) for i, target in enumerate(targets)]

    @staticmethod
    def _get_target_name(target, abs_path):
        """Get target name from target's absolute path.

        If the project is for entire Android source tree, change the target to
        source tree's root folder name. In this way, we give IDE project file
        a more specific name. e.g, master.iml.

        Args:
            target: Includes target module or project path from user input, when
                    locating the target, project with matching module name of
                    the given target has a higher priority than project path.
            abs_path: A string, target's absolute path.

        Returns:
            A string, the target name.
        """
        if abs_path == common_util.get_android_root_dir():
            return os.path.basename(abs_path)
        return target
