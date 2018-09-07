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

import os
import re

from aidegen.lib import errors

# Parse package name from the package declaration line of a java.
# Group matches "foo.bar" of line "package foo.bar;" or "package foo.bar"
_PACKAGE_RE = re.compile(r'\s*package\s+(?P<package>[^(;|\s)]+)\s*', re.I)

_ANDROID_BUILD_TOP = "ANDROID_BUILD_TOP"
_ANDROID_SUPPORT_MODULE_KEYWORD = "android-support-"
_JARJAR_RULES_FILE = "jarjar-rules.txt"
_KEY_AIDL = "aidl_include_dirs"
_KEY_JARJAR_RULES = "jarjar_rules"
_KEY_JARS = "jars"
_KEY_PATH = "path"
_KEY_SRCS = "srcs"
_REGEXP_MULTI_DIR = "/**/"


def locate_source(project):
    """Locate the paths of dependent source folders and jar files.

    Try to reference source folder path as dependent module unless the
    dependent module should be referenced to a jar file, such as modules have
    jars and jarjar_rules parameter.
    For example:
        Module: asm-6.0
            java_import {
                name: "asm-6.0",
                host_supported: true,
                jars: ["asm-6.0.jar"],
            }
        Module: bouncycastle
            java_library {
                name: "bouncycastle",
                ...
                target: {
                    android: {
                        jarjar_rules: "jarjar-rules.txt",
                    },
                },
            }

    Args:
        project: ProjectInfo class.Information of a project such as project
                 relative path, project real path, project dependencies.

    Example usage:
        project.source_path = locate_source(project)
        E.g.
            project.source_path = {
                "source_folder_path": ["path/to/source/folder1",
                                       "path/to/source/folder2", ...],
                "jar_path": ["path/to/jar/file1", "path/to/jar/file2", ...]
            }
    """
    if not hasattr(project, "depend_modules") or not project.depend_modules:
        raise errors.EmptyModuleDependencyError(
            "Dependent modules dictionary is empty.")
    project.source_path = {
        "source_folder_path": [],
        "jar_path": []
    }
    for module_name in project.depend_modules:
        module = ModuleData(module_name, project.depend_modules[module_name])
        src_paths, jar_files = module.locate_sources_path()
        project.source_path["source_folder_path"].extend(src_paths)
        project.source_path["jar_path"].extend(jar_files)


class ModuleData(object):
    """ModuleData class."""

    def __init__(self, module_name, module_data):
        """Initialize ModuleData.

        Args:
            module_name: Name of the module.
            module_data: A dictionary holding a module information.
            For example:
                {
                    "class": ["APPS"],
                    "path": ["path/to/the/module"],
                    "dependencies": ["bouncycastle", "ims-common"],
                    "srcs": [
                        "core/java/**/*.java",
                        "src/com/android/test.java",
                        "src/com/google/test.java",
                        "src/com/android/aidl/test.aidl",
                        "src/com/android/logtags/test.logtags",
                        ":file_group_name"],
                    "installed": ["out/target/product/generic_x86_64/
                                   system/framework/framework.jar"],
                    "jars": ["settings.jar"],
                    "jarjar_rules": ["jarjar-rules.txt"],
                    "aidl_include_dirs": []
                }
        """
        assert module_name, "Module name can't be null."
        assert module_data, "Module data of %s can't be null." % module_name
        self.module_name = module_name
        self.module_data = module_data
        self.src_dirs = []
        self.jar_files = []
        self.is_android_support_module = self.module_name.startswith(
            _ANDROID_SUPPORT_MODULE_KEYWORD)
        self.aidl_existed = _KEY_AIDL in self.module_data
        self.jarjar_rules_existed = (
            _KEY_JARJAR_RULES in self.module_data and
            self.module_data[_KEY_JARJAR_RULES][0] == _JARJAR_RULES_FILE
        )
        self.jars_existed = (_KEY_JARS in self.module_data and
                             self.module_data[_KEY_JARS])
        self.filegroup_existed = False
        self.logtags_existed = False

        self._collect_srcs_paths()

    def _collect_srcs_paths(self):
        """Collect source folder paths in src_dirs from module_data["srcs"].

        The value of srcs is from Android.bp or Android.mk.
        1.In Android.bp, there might be src/main/java/**/*.java in srcs. It
          means src/main/java is a source path of this module.
        2.In Android.mk, srcs have relative path to java files, however it's
          not a source path. Call _get_source_folder method to get source path.

        Other items, such as file name ends with .aidl or .logtags or file name
        starts with colon, needed to be record first and then add the certain
        directory under out/ as a source folder.
        """
        if (_KEY_SRCS in self.module_data and self.module_data[_KEY_SRCS]):
            scanned_dirs = []
            for src_item in self.module_data[_KEY_SRCS]:
                if src_item.endswith(".java"):
                    src_dir = None
                    if _REGEXP_MULTI_DIR in src_item:
                        src_dir = src_item.split(_REGEXP_MULTI_DIR)[0]
                    else:
                        java_dir, _ = os.path.split(src_item)
                        if java_dir not in scanned_dirs:
                            src_dir = self._get_source_folder(src_item)
                            scanned_dirs.append(java_dir)
                    if src_dir and src_dir not in self.src_dirs:
                        self.src_dirs.append(src_dir)
                elif src_item.endswith(".aidl"):
                    self.aidl_existed = True
                elif src_item.endswith(".logtags"):
                    self.logtags_existed = True
                elif src_item.startswith(":"):
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
        abs_java_path = os.path.join(os.environ.get(_ANDROID_BUILD_TOP),
                                     self.module_data[_KEY_PATH][0], java_file)
        if os.path.exists(abs_java_path):
            with open(abs_java_path) as data:
                for line in data.read().splitlines():
                    match = _PACKAGE_RE.match(line)
                    if match:
                        package_name = match.group('package')
                        package_path = package_name.replace(os.extsep, os.sep)
                        source_folder, _, _ = java_file.rpartition(package_path)
                        return source_folder.strip(os.sep)

    def locate_sources_path(self):
        """Locate source folders' path or jar files.

        Returns:
            A tuple of contains src_paths and jar_files. Only one of them has
            data. Since if the referencing module by jar file then it doesn't
            need to reference source folder and vice versa.
        """
        # TODO(b/112523194):Summarizing self.src_dirs and self.jar_files.
        return self.src_dirs, self.jar_files
