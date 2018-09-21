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

"""Collect the source paths from dependency information."""

from __future__ import absolute_import

import logging
import os
import re

from aidegen.lib import errors

# Parse package name from the package declaration line of a java.
# Group matches "foo.bar" of line "package foo.bar;" or "package foo.bar"
_PACKAGE_RE = re.compile(r'\s*package\s+(?P<package>[^(;|\s)]+)\s*', re.I)

_ANDROID_SUPPORT_PATH_KEYWORD = 'prebuilts/sdk/current/'
_DIR_AIDL = 'aidl'
_DIR_GEN = 'gen'
_DIR_LOGTAGS = 'logtags'
_JARJAR_RULES_FILE = 'jarjar-rules.txt'
_KEY_AIDL = 'aidl_include_dirs'
_KEY_INSTALLED = 'installed'
_KEY_JARJAR_RULES = 'jarjar_rules'
_KEY_JARS = 'jars'
_KEY_PATH = 'path'
_KEY_SRCS = 'srcs'
_REGEXP_MULTI_DIR = '/**/'


def locate_source(project):
    """Locate the paths of dependent source folders and jar files.

    Try to reference source folder path as dependent module unless the
    dependent module should be referenced to a jar file, such as modules have
    jars and jarjar_rules parameter.
    For example:
        Module: asm-6.0
            java_import {
                name: 'asm-6.0',
                host_supported: true,
                jars: ['asm-6.0.jar'],
            }
        Module: bouncycastle
            java_library {
                name: 'bouncycastle',
                ...
                target: {
                    android: {
                        jarjar_rules: 'jarjar-rules.txt',
                    },
                },
            }

    Args:
        project: ProjectInfo class. Information of a project such as project
                 relative path, project real path, project dependencies.

    Example usage:
        project.source_path = locate_source(project)
        E.g.
            project.source_path = {
                'source_folder_path': ['path/to/source/folder1',
                                       'path/to/source/folder2', ...],
                'jar_path': ['path/to/jar/file1', 'path/to/jar/file2', ...]
            }
    """
    if not hasattr(project, 'depend_modules') or not project.depend_modules:
        raise errors.EmptyModuleDependencyError(
            'Dependent modules dictionary is empty.')
    project.source_path = {'source_folder_path': [], 'jar_path': []}
    for module_name in project.depend_modules:
        module = ModuleData(project.android_root_path, module_name,
                            project.depend_modules[module_name])
        module.locate_sources_path()
        project.source_path['source_folder_path'].extend(module.src_dirs)
        project.source_path['jar_path'].extend(module.jar_files)


class ModuleData(object):
    """ModuleData class."""

    def __init__(self, android_root_path, module_name, module_data):
        """Initialize ModuleData.

        Args:
            android_root_path: The path to android source root.
            module_name: Name of the module.
            module_data: A dictionary holding a module information.
            For example:
                {
                    'class': ['APPS'],
                    'path': ['path/to/the/module'],
                    'dependencies': ['bouncycastle', 'ims-common'],
                    'srcs': [
                        'core/java/**/*.java',
                        'src/com/android/test.java',
                        'src/com/google/test.java',
                        'src/com/android/aidl/test.aidl',
                        'src/com/android/logtags/test.logtags'],
                    'installed': ['out/target/product/generic_x86_64/
                                   system/framework/framework.jar'],
                    'jars': ['settings.jar'],
                    'jarjar_rules': ['jarjar-rules.txt'],
                    'aidl_include_dirs': []
                }
        """
        assert module_name, 'Module name can\'t be null.'
        assert module_data, 'Module data of %s can\'t be null.' % module_name
        self.android_root_path = android_root_path
        self.module_name = module_name
        self.module_data = module_data
        self.module_path = (self.module_data[_KEY_PATH][0]
                            if _KEY_PATH in self.module_data
                            and self.module_data[_KEY_PATH] else '')
        self.src_dirs = []
        self.jar_files = []
        self.is_android_support_module = self.module_path.startswith(
            _ANDROID_SUPPORT_PATH_KEYWORD)
        self.aidl_existed = (_KEY_AIDL in self.module_data
                             and self.module_data[_KEY_AIDL])
        self.jarjar_rules_existed = (
            _KEY_JARJAR_RULES in self.module_data
            and self.module_data[_KEY_JARJAR_RULES][0] == _JARJAR_RULES_FILE)
        self.jars_existed = (_KEY_JARS in self.module_data
                             and self.module_data[_KEY_JARS])
        self.filegroup_existed = False
        self.logtags_existed = False

        self._check_special_files()

    def _collect_srcs_paths(self):
        """Collect source folder paths in src_dirs from module_data['srcs'].

        The value of srcs is from Android.bp or Android.mk.
        1.In Android.bp, there might be src/main/java/**/*.java in srcs. It
          means src/main/java is a source path of this module.
        2.In Android.mk, srcs have relative path to java files, however it's
          not a source path. Call _get_source_folder method to get source path.
        """
        if _KEY_SRCS in self.module_data and self.module_data[_KEY_SRCS]:
            scanned_dirs = []
            for src_item in self.module_data[_KEY_SRCS]:
                if src_item.endswith('.java'):
                    src_dir = None
                    if _REGEXP_MULTI_DIR in src_item:
                        src_dir = src_item.split(_REGEXP_MULTI_DIR)[0]
                    else:
                        java_dir, _ = os.path.split(src_item)
                        if java_dir not in scanned_dirs:
                            src_dir = self._get_source_folder(src_item)
                            scanned_dirs.append(java_dir)
                    if src_dir:
                        src_dir = os.path.join(self.module_path, src_dir)
                        if src_dir not in self.src_dirs:
                            self.src_dirs.append(src_dir)

    def _check_special_files(self):
        """Check if *.aidl or *.logtags or filegroup exists."""
        if _KEY_SRCS in self.module_data and self.module_data[_KEY_SRCS]:
            for src_item in self.module_data[_KEY_SRCS]:
                if src_item.endswith('.aidl'):
                    self.aidl_existed = True
                elif src_item.endswith('.logtags'):
                    self.logtags_existed = True
                elif src_item.startswith(':'):
                    self.filegroup_existed = True

    # pylint: disable=inconsistent-return-statements
    def _get_source_folder(self, java_file):
        """Parsing a java to get the package name to filter out source path.

        There are 3 steps to get the source path from a java.
        1. Parsing a java to get package name.
           For example:
               The package name of src/main/java/com/android/first.java is
               com.android.
        2. Transfer package name to package path:
           For example:
               The package path of com.android is com/android.
        3. Remove the package path and file name from the java path.
           For example:
               The java is src/main/java/com/android/first.java.
               The path after removing package path and file name is
               src/main/java.
        As a result, src/main/java is the source path parsed from
        src/main/java/com/android/first.java.

        Returns:
            source_folder: A string of path to source folder(e.g. src/main/java)
                           or none when it failed to get package name.
        """
        abs_java_path = os.path.join(self.android_root_path, self.module_path,
                                     java_file)
        if os.path.exists(abs_java_path):
            with open(abs_java_path) as data:
                for line in data.read().splitlines():
                    match = _PACKAGE_RE.match(line)
                    if match:
                        package_name = match.group('package')
                        package_path = package_name.replace(os.extsep, os.sep)
                        source_folder, _, _ = java_file.rpartition(
                            package_path)
                        return source_folder.strip(os.sep)

    def _append_jar_file(self, jar_path):
        """Append a path to the jar file into self.jar_files if it's exists.

        Args:
            jar_path: A path supposed to be a jar file.

        Returns:
            Boolean: True if jar_path is an existing jar file.
        """
        jar_abspath = os.path.join(self.android_root_path, jar_path)
        if jar_path.endswith('.jar') and os.path.isfile(jar_abspath):
            self.jar_files.append(jar_path)
            return True
        elif not jar_path.endswith('.jar'):
            logging.warn('Not a jar file: %s.', jar_path)
        else:
            logging.warn('Jar file doesn\'t exist: %s.', jar_abspath)

    def _append_src_dir(self, src_path):
        """Append a path into self.src_dirs if it's exists.

        Args:
            src_path: A path to source folder.

        Returns:
            Boolean: True if the source folder exists and append to
                     self.src_dirs successfully.
        """
        src_abspath = os.path.join(self.android_root_path, src_path)
        if os.path.isdir(src_abspath):
            self.src_dirs.append(src_path)
            return True
        else:
            logging.warn('Source path doesn\'t exist: %s.', src_abspath)

    def _append_jar_from_installed(self, specific_dir=None):
        """Append a jar file's path to the list of jar_files with matching
        path_prefix.

        There might be more than one jar in "installed" parameter and only the
        first jar file is returned. If specific_dir is set, the jar file must be
        under the specific directory or its sub-directory.

        Args:
            specific_dir: A string of path.
        """
        if (_KEY_INSTALLED in self.module_data
                and self.module_data[_KEY_INSTALLED]):
            for jar in self.module_data[_KEY_INSTALLED]:
                if not specific_dir or jar.startswith(specific_dir):
                    self._append_jar_file(jar)
                    break

    def _set_jars_jarfile(self):
        """Append prebuilt jars of module into self.jar_files.

        Some modele is with prebuilt jar files instead of source java files.
        The jar files can be imported into IntelliJ as a dependency directly.
        There is only jar file name in self.module_data['jars'], it has to be
        combined with self.module_data['path'] to append into self.jar_files.
        For example:
        'asm-6.0': {
            'jars': [
                'asm-6.0.jar'
            ],
            'path': [
                'prebuilts/misc/common/asm'
            ],
        },
        Path to the jar file is prebuilts/misc/common/asm/asm-6.0.jar.
        """
        if _KEY_JARS in self.module_data and self.module_data[_KEY_JARS]:
            for jar_name in self.module_data[_KEY_JARS]:
                jar_path = os.path.join(self.module_path, jar_name)
                self._append_jar_file(jar_path)

    def locate_sources_path(self):
        """Locate source folders' paths or jar files."""
        out_soong = os.path.join('out/soong/.intermediates', self.module_path,
                                 self.module_name, 'android_common')
        out_target = os.path.join('out/target/common/obj/JAVA_LIBRARIES/',
                                  '%s_intermediates' % self.module_name)
        # Deal with jar file first, in current studies we can ignore src paths
        # if a jar is referenced. Because the src paths and the related files
        # are packed in the jar.
        if self.is_android_support_module:
            self._append_jar_from_installed()
        elif self.jarjar_rules_existed or self.filegroup_existed:
            self._append_jar_from_installed(out_soong)
        elif self.jars_existed:
            self._set_jars_jarfile()
        if self.jar_files:
            return
        # Find source folders if there is no jar file needed.
        self._collect_srcs_paths()
        if self.aidl_existed:
            self._append_src_dir(os.path.join(out_soong, _DIR_GEN, _DIR_AIDL))
            self._append_src_dir(os.path.join(out_target, _DIR_AIDL))
        if self.logtags_existed:
            self._append_src_dir(
                os.path.join(out_soong, _DIR_GEN, _DIR_LOGTAGS))
            self._append_src_dir(os.path.join(out_target, _DIR_LOGTAGS))
