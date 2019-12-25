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

"""clion_project_file_gen

This module has a collection of helper functions for generating CLion's
CMakeLists.txt project file.

Example usage:
    json_path = common_util.get_blueprint_cc_json_path()
    json_dict = common_util.get_soong_build_json_dict(json_path)
    modules_dict = json_dict.get('modules', {})
    if not modules_dict:
        return
    mod_info = modules_dict.get('libui', {})
    if not mod_info:
        return
    clion_project_file_gen.generate_cmakelists_file(mod_info)
"""

import os

from functools import partial

from aidegen.lib import common_util

# Keys for writing in module_bp_cc_deps.json
_KEY_GLOBAL_COMMON_FLAGS = 'global_common_flags'
_KEY_LOCAL_COMMON_FLAGS = 'local_common_flags'
_KEY_GLOBAL_CFLAGS = 'global_c_flags'
_KEY_LOCAL_CFLAGS = 'local_c_flags'
_KEY_GLOBAL_C_ONLY_FLAGS = 'global_c_only_flags'
_KEY_LOCAL_C_ONLY_FLAGS = 'local_c_only_flags'
_KEY_GLOBAL_CPP_FLAGS = 'global_cpp_flags'
_KEY_LOCAL_CPP_FLAGS = 'local_cpp_flags'
_KEY_SYSTEM_INCLUDE_FLAGS = 'system_include_flags'

# Constants for CMakeLists.txt.
_ANDROID_ROOT_SYMBOL = '${ANDROID_ROOT}'


# The temporary pylint disable statements are only used for the skeleton upload.
# pylint: disable=unused-argument
# pylint: disable=unnecessary-pass
@common_util.io_error_handle
def _write_header(hfile, module_name, root_dir):
    """Writes CLion project file's header messages.

    Args:
        hfile: A file handler instance.
        module_name: A string of module's name.
        root_dir: A string of Android root path.
    """
    pass


@common_util.io_error_handle
def _write_c_compiler_paths(hfile):
    """Writes CMake compiler paths for C and Cpp to CLion project file.

    Args:
        hfile: A file handler instance.
    """
    pass


@common_util.io_error_handle
def _write_source_files(hfile, mod_info):
    """Writes source files' paths to CLion project file.

    Args:
        hfile: A file handler instance.
        mod_info: A module's info dictionary.
    """
    pass


@common_util.io_error_handle
def _write_flags(hfile, mod_info, key, cflags, cppflags):
    """Writes CMake compiler paths for C and Cpp for different kinds of flags.

    Args:
        hfile: A file handler instance.
        mod_info: A module's info dictionary.
        key: A string of flag type, e.g., _KEY_GLOBAL_COMMON_FLAGS.
        cflags: A boolean for setting 'CMAKE_C_FLAGS' flag.
        cppflags: A boolean for setting 'CMAKE_CXX_FLAGS' flag.
    """
    pass


# Functions to simplify the calling to function _write_flags with some fixed
# parameters.
_WRITE_GLOBAL_COMMON_FLAGS = partial(
    _write_flags, key=_KEY_GLOBAL_COMMON_FLAGS, cflags=True, cppflags=True)
_WRITE_LOCAL_COMMON_FLAGS = partial(
    _write_flags, key=_KEY_LOCAL_COMMON_FLAGS, cflags=True, cppflags=True)
_WRITE_GLOBAL_C_FLAGS = partial(
    _write_flags, key=_KEY_GLOBAL_CFLAGS, cflags=True, cppflags=True)
_WRITE_LOCAL_C_FLAGS = partial(
    _write_flags, key=_KEY_LOCAL_CFLAGS, cflags=True, cppflags=True)
_WRITE_GLOBAL_C_ONLY_FLAGS = partial(
    _write_flags, key=_KEY_GLOBAL_C_ONLY_FLAGS, cflags=True, cppflags=False)
_WRITE_LOCAL_C_ONLY_FLAGS = partial(
    _write_flags, key=_KEY_LOCAL_C_ONLY_FLAGS, cflags=True, cppflags=False)
_WRITE_GLOBAL_CPP_FLAGS = partial(
    _write_flags, key=_KEY_GLOBAL_CPP_FLAGS, cflags=False, cppflags=True)
_WRITE_LOCAL_CPP_FLAGS = partial(
    _write_flags, key=_KEY_LOCAL_CPP_FLAGS, cflags=False, cppflags=True)
_WRITE_SYSTEM_INCLUDE_FLAGS = partial(
    _write_flags, key=_KEY_SYSTEM_INCLUDE_FLAGS, cflags=True, cppflags=True)


def _parse_compiler_parameters(hfile, flag, mod_info):
    """Parses the specific flag data from a module_info dictionary.

    Args:
        hfile: A file handler instance.
        flag: The string of key flag, e.g.: _KEY_GLOBAL_COMMON_FLAGS.
        mod_info: A module's info dictionary.

    Returns:
        A dictionary with compiled parameters.
    """
    pass


def _translate_to_cmake(hfile, params_dict, cflags, cppflags):
    """Translates parameter dict's contents into CLion project file's format.

    Args:
        hfile: A file handler instance.
        params_dict: A dict contains data to be translated into CLion project
                     file's format.
        cflags: A boolean is to set 'CMAKE_C_FLAGS' flag.
        cppflags: A boolean is to set 'CMAKE_CXX_FLAGS' flag.
    """
    pass


@common_util.io_error_handle
def _write_all_relative_file_path_flags(hfile, rel_paths_dict, tag):
    """Writes all relative file path flags' parameters."""
    pass


def _add_dollar_sign(tag):
    """Adds dollar sign to a string, e.g.: 'ANDROID_ROOT' -> '${ANDROID_ROOT}'.

    Args:
        tag: A string to be added a dollar sign.

    Returns:
        A dollar sign added string.
    """
    return ''.join(['${', tag, '}'])


@common_util.io_error_handle
def _write_all_flags(hfile, flags, tag):
    """Wrties all flags to the project file.

    Args:
        hfile: A file handler instance.
        flags: A list of flag strings to be added.
        tag: A string to be added a dollar sign.
    """
    pass


def _build_cmake_path(path, tag=''):
    """Joins tag, '${ANDROID_ROOT}' and path into a new string."""
    return ''.join([tag, _ANDROID_ROOT_SYMBOL, os.path.sep, path])


@common_util.io_error_handle
def _write_all_include_directories(hfile, includes, is_system):
    """Writes all included directories' paths to the CLion project file.

    Args:
        hfile: A file handler instance.
        includes: A list of included file paths.
        is_system: A boolean of whether it's a system flag.
    """
    pass


def _get_cmakelists_file_dir(cc_path):
    """Gets module's CMakeLists.txt file path to be created.

    Return a string of $OUT/development/ide/clion/${cc_path}/[module name].
    For example, if module name is 'libui'. The return path string would be:
        out/development/ide/clion/frameworks/native/libs/ui/libui

    Args:
        cc_path: A string of relative path of module's Android.bp file.

    Returns:
        A string of relative path of module's CMakeLists.txt file to be created.
    """
    pass


@common_util.io_error_handle
def generate_cmakelists_file(mod_info):
    """Generates CLion project file from the target module's info.

    Args:
        mod_info: A module's info dictionary.
    """
    pass


@common_util.io_error_handle
def generate_base_cmakelists_file(cc_module_info, project_path, mod_names):
    """Generates base CLion project file for multiple CLion projects.

    Args:
        cc_module_info: An instance of native_module_info.NativeModuleInfo.
        project_path: A string of the base project relative path.
        mod_names: A list of module names whose project were created under
                   project_path.
    """
    pass
