#!/usr/bin/env python3
#
# Copyright 2019 - The Android Open Source Project
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

"""native_util

This module has a collection of functions that provide helper functions for
launching native projects in IDE.
"""

import fnmatch
import os

from aidegen import constant
from aidegen.lib import common_util

def _get_cmakelists_path():
    """Assemble the path of the file which contains all CLion projects' paths.

    Returns:
        Clion project list file path.
    """
    return os.path.join(
        common_util.get_soong_out_path(), constant.CMAKELISTS_FILE_NAME)


def _generate_clion_projects_file():
    """Generate file of CLion's project file paths' list."""
    android_root = common_util.get_android_root_dir()
    files = []
    for root, _, filenames in os.walk(android_root):
        if fnmatch.filter(filenames, constant.CLION_PROJECT_FILE_NAME):
            files.append(os.path.relpath(root, android_root))
    with open(_get_cmakelists_path(), 'w') as outfile:
        for cfile in files:
            outfile.write("%s\n" % cfile)


def _separate_native_and_java_projects(
        atest_module_info, targets, native_file_list):
    """Separate native and java projects.

    Args:
        atest_module_info: A ModuleInfo instance contains the data of
                module-info.json.
        targets: A list of targets to be imported.
        native_file_list: A list of native files' path to be checked.

    Returns:
        A tuple of a list of CMakeLists.txt relative paths and a list of build
        targets.
    """
    ctargets = []
    cmakelists = []
    for target in targets:
        rel_path, abs_path = common_util.get_related_paths(
            atest_module_info, target)
        if rel_path in native_file_list:
            ctargets.append(target)
            cmakelists.append(os.path.relpath(abs_path, os.getcwd()))
    for target in ctargets:
        targets.remove(target)
    return cmakelists, targets


def check_native_projects(atest_module_info, targets):
    """Check if targets exist native projects.

    For native projects:
    1. Since IntelliJ doesn't support native projects any more, when targets
       exist native projects, we should separate them and launch them with
       CLion.
    2. Android Studio support native project and open CMakeLists.txt as its
       native project file as well. Its behavior is like IntelliJ: Java projects
       and native projects can't be launched in the same IDE and each IDE can
       only launch a single native project.

    Args:
        atest_module_info: A ModuleInfo instance contains the data of
                module-info.json.
        targets: A list of targets to be imported.

    Returns:
        A tuple of a list of CMakeLists.txt relative paths and a list of build
        targets.
    """
    cmake_file = _get_cmakelists_path()
    if not os.path.isfile(cmake_file):
        _generate_clion_projects_file()
    # TODO(b/140140401): Support Eclipse's native projects.
    # Launch CLion for Eclipse's native projects as a temporary solution.
    if not os.path.isfile(cmake_file):
        return [], targets

    native_file_list = common_util.read_file_line_to_list(cmake_file)

    return _separate_native_and_java_projects(
        atest_module_info, targets, native_file_list)
