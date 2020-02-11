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
from io import StringIO
from io import TextIOWrapper

from aidegen import constant
from aidegen.lib import common_util

# Flags for writing to CMakeLists.txt section.
_GLOBAL_COMMON_FLAGS = '\n# GLOBAL ALL FLAGS:\n'
_LOCAL_COMMON_FLAGS = '\n# LOCAL ALL FLAGS:\n'
_GLOBAL_CFLAGS = '\n# GLOBAL CFLAGS:\n'
_LOCAL_CFLAGS = '\n# LOCAL CFLAGS:\n'
_GLOBAL_C_ONLY_FLAGS = '\n# GLOBAL C ONLY FLAGS:\n'
_LOCAL_C_ONLY_FLAGS = '\n# LOCAL C ONLY FLAGS:\n'
_GLOBAL_CPP_FLAGS = '\n# GLOBAL CPP FLAGS:\n'
_LOCAL_CPP_FLAGS = '\n# LOCAL CPP FLAGS:\n'
_SYSTEM_INCLUDE_FLAGS = '\n# GLOBAL SYSTEM INCLUDE FLAGS:\n'

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

# Dictionary maps keys to sections.
_FLAGS_DICT = {
    _KEY_GLOBAL_COMMON_FLAGS: _GLOBAL_COMMON_FLAGS,
    _KEY_LOCAL_COMMON_FLAGS: _LOCAL_COMMON_FLAGS,
    _KEY_GLOBAL_CFLAGS: _GLOBAL_CFLAGS,
    _KEY_LOCAL_CFLAGS: _LOCAL_CFLAGS,
    _KEY_GLOBAL_C_ONLY_FLAGS: _GLOBAL_C_ONLY_FLAGS,
    _KEY_LOCAL_C_ONLY_FLAGS: _LOCAL_C_ONLY_FLAGS,
    _KEY_GLOBAL_CPP_FLAGS: _GLOBAL_CPP_FLAGS,
    _KEY_LOCAL_CPP_FLAGS: _LOCAL_CPP_FLAGS,
    _KEY_SYSTEM_INCLUDE_FLAGS: _SYSTEM_INCLUDE_FLAGS
}

# Keys for parameter types.
_KEY_HEADER = 'header_search_path'
_KEY_SYSTEM = 'system_search_path'
_KEY_FLAG = 'flag'
_KEY_SYSTEM_ROOT = 'system_root'
_KEY_RELATIVE = 'relative_file_path'

# Constants for CMakeLists.txt.
_CMAKELISTS_HEADER = ('# THIS FILE WAS AUTOMATICALY GENERATED!\n'
                      '# ANY MODIFICATION WILL BE OVERWRITTEN!\n\n'
                      '# To improve project view in Clion    :\n'
                      '# Tools > CMake > Change Project Root  \n\n')
_MINI_VERSION_SUPPORT = 'cmake_minimum_required(VERSION {})\n'
_MINI_VERSION = '3.5'
_PROJECT_NAME = 'project({})\n'
_SET_ANDROID_ROOT = 'set(ANDROID_ROOT {})\n\n'
_LIST_APPEND_HEADER = 'list(APPEND\n'
_SOURCE_FILES_HEADER = 'SOURCE_FILES'
_END_WITH_ONE_BLANK_LINE = ')\n'
_END_WITH_TWO_BLANK_LINES = ')\n\n'
_SET_RELATIVE_PATH = 'set({} "{} {}={}")\n'
_SET_ALL_FLAGS = 'set({} "{} {}")\n'
_ANDROID_ROOT_SYMBOL = '${ANDROID_ROOT}'
_SYSTEM = 'SYSTEM'
_INCLUDE_DIR = 'include_directories({} \n'
_SET_INCLUDE_FORMAT = '    "{}"\n'
_CMAKE_C_FLAGS = 'CMAKE_C_FLAGS'
_CMAKE_CXX_FLAGS = 'CMAKE_CXX_FLAGS'
_USR = 'usr'
_INCLUDE = 'include'
_INCLUDE_SYSTEM = 'include_directories(SYSTEM "{}")\n'
_GLOB_RECURSE_TMP_HEADERS = 'file (GLOB_RECURSE TMP_HEADERS\n'
_ALL_HEADER_FILES = '    "{}/**/*.h"\n'
_APPEND_SOURCE_FILES = "list (APPEND SOURCE_FILES ${TMP_HEADERS})\n\n"


# The temporary pylint disable statements are only used for the skeleton upload.
# pylint: disable=unused-argument
@common_util.check_args(
    hfile=(TextIOWrapper, StringIO), module_name=str, root_dir=str)
@common_util.io_error_handle
def _write_header(hfile, module_name, root_dir):
    """Writes CLion project file's header messages.

    Args:
        hfile: A file handler instance.
        module_name: A string of module's name.
        root_dir: A string of Android root path.
    """
    hfile.write(_CMAKELISTS_HEADER)
    hfile.write(_MINI_VERSION_SUPPORT.format(_MINI_VERSION))
    hfile.write(_PROJECT_NAME.format(module_name))
    hfile.write(_SET_ANDROID_ROOT.format(root_dir))


@common_util.check_args(hfile=(TextIOWrapper, StringIO))
@common_util.io_error_handle
def _write_c_compiler_paths(hfile):
    """Writes CMake compiler paths for C and Cpp to CLion project file.

    Args:
        hfile: A file handler instance.
    """


@common_util.check_args(hfile=(TextIOWrapper, StringIO), mod_info=dict)
@common_util.io_error_handle
def _write_source_files(hfile, mod_info):
    """Writes source files' paths to CLion project file.

    Args:
        hfile: A file handler instance.
        mod_info: A module's info dictionary.
    """
    if constant.KEY_SRCS not in mod_info:
        return
    source_files = mod_info[constant.KEY_SRCS]
    hfile.write(_LIST_APPEND_HEADER)
    hfile.write(''.join(['     ', _SOURCE_FILES_HEADER, '\n']))
    for src in source_files:
        hfile.write(''.join([_build_cmake_path(src, '    '), '\n']))
    hfile.write(_END_WITH_ONE_BLANK_LINE)


@common_util.check_args(
    hfile=(TextIOWrapper, StringIO), mod_info=dict, key=str, cflags=bool,
    cppflags=bool)
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
    if key not in _FLAGS_DICT:
        return
    hfile.write(_FLAGS_DICT[key])
    params_dict = _parse_compiler_parameters(key, mod_info)
    if params_dict:
        _translate_to_cmake(hfile, params_dict, cflags, cppflags)


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


@common_util.check_args(flag=str, mod_info=dict)
def _parse_compiler_parameters(flag, mod_info):
    """Parses the specific flag data from a module_info dictionary.

    Args:
        flag: The string of key flag, e.g.: _KEY_GLOBAL_COMMON_FLAGS.
        mod_info: A module's info dictionary.

    Returns:
        A dictionary with compiled parameters.
    """
    params = mod_info.get(flag, {})
    if not params:
        return None
    params_dict = {
        _KEY_HEADER: [],
        _KEY_SYSTEM: [],
        _KEY_FLAG: [],
        _KEY_SYSTEM_ROOT: '',
        _KEY_RELATIVE: {}
    }
    for key, value in params.items():
        params_dict[key] = value
    return params_dict


@common_util.check_args(
    hfile=(TextIOWrapper, StringIO), params_dict=dict, cflags=bool,
    cppflags=bool)
def _translate_to_cmake(hfile, params_dict, cflags, cppflags):
    """Translates parameter dict's contents into CLion project file's format.

    Args:
        hfile: A file handler instance.
        params_dict: A dict contains data to be translated into CLion project
                     file's format.
        cflags: A boolean is to set 'CMAKE_C_FLAGS' flag.
        cppflags: A boolean is to set 'CMAKE_CXX_FLAGS' flag.
    """
    _write_all_include_directories(hfile, params_dict[_KEY_SYSTEM], True)
    _write_all_include_directories(hfile, params_dict[_KEY_HEADER], False)

    if cflags:
        _write_all_relative_file_path_flags(hfile, params_dict[_KEY_RELATIVE],
                                            _CMAKE_C_FLAGS)
        _write_all_flags(hfile, params_dict[_KEY_FLAG], _CMAKE_C_FLAGS)

    if cppflags:
        _write_all_relative_file_path_flags(hfile, params_dict[_KEY_RELATIVE],
                                            _CMAKE_CXX_FLAGS)
        _write_all_flags(hfile, params_dict[_KEY_FLAG], _CMAKE_CXX_FLAGS)

    if params_dict[_KEY_SYSTEM_ROOT]:
        path = os.path.join(params_dict[_KEY_SYSTEM_ROOT], _USR, _INCLUDE)
        hfile.write(_INCLUDE_SYSTEM.format(_build_cmake_path(path)))


@common_util.check_args(
    hfile=(TextIOWrapper, StringIO), rel_paths_dict=dict, tag=str)
@common_util.io_error_handle
def _write_all_relative_file_path_flags(hfile, rel_paths_dict, tag):
    """Writes all relative file path flags' parameters.

    Args:
        hfile: A file handler instance.
        rel_paths_dict: A dict contains data of flag as a key and the relative
                        path string as its value.
        tag: A string of tag, such as 'CMAKE_C_FLAGS'.
    """
    for flag, path in rel_paths_dict.items():
        hfile.write(
            _SET_RELATIVE_PATH.format(tag, _add_dollar_sign(tag), flag,
                                      _build_cmake_path(path)))


def _add_dollar_sign(tag):
    """Adds dollar sign to a string, e.g.: 'ANDROID_ROOT' -> '${ANDROID_ROOT}'.

    Args:
        tag: A string to be added a dollar sign.

    Returns:
        A dollar sign added string.
    """
    return ''.join(['${', tag, '}'])


@common_util.check_args(hfile=(TextIOWrapper, StringIO), flags=list, tag=str)
@common_util.io_error_handle
def _write_all_flags(hfile, flags, tag):
    """Wrties all flags to the project file.

    Args:
        hfile: A file handler instance.
        flags: A list of flag strings to be added.
        tag: A string to be added a dollar sign.
    """
    for flag in flags:
        hfile.write(_SET_ALL_FLAGS.format(tag, _add_dollar_sign(tag), flag))


def _build_cmake_path(path, tag=''):
    """Joins tag, '${ANDROID_ROOT}' and path into a new string.

    Args:
        path: A string of a path.
        tag: A string to be added in front of a dollar sign

    Returns:
        The composed string.
    """
    return ''.join([tag, _ANDROID_ROOT_SYMBOL, os.path.sep, path])


@common_util.check_args(hfile=(TextIOWrapper, StringIO), is_system=bool)
@common_util.io_error_handle
def _write_all_includes(hfile, includes, is_system):
    """Writes all included directories' paths to the CLion project file.

    Args:
        hfile: A file handler instance.
        includes: A list of included file paths.
        is_system: A boolean of whether it's a system flag.
    """
    if not includes:
        return
    system = ''
    if is_system:
        system = _SYSTEM
    hfile.write(_INCLUDE_DIR.format(system))
    for include in includes:
        hfile.write(_SET_INCLUDE_FORMAT.format(_build_cmake_path(include)))
    hfile.write(_END_WITH_TWO_BLANK_LINES)


@common_util.check_args(hfile=(TextIOWrapper, StringIO))
@common_util.io_error_handle
def _write_all_headers(hfile, includes):
    """Writes all header directories' paths to the CLion project file.

    Args:
        hfile: A file handler instance.
        includes: A list of included file paths.
    """
    if not includes:
        return
    hfile.write(_GLOB_RECURSE_TMP_HEADERS)
    for include in includes:
        hfile.write(_ALL_HEADER_FILES.format(_build_cmake_path(include)))
    hfile.write(_END_WITH_ONE_BLANK_LINE)
    hfile.write(_APPEND_SOURCE_FILES)


@common_util.check_args(hfile=(TextIOWrapper, StringIO), is_system=bool)
@common_util.io_error_handle
def _write_all_include_directories(hfile, includes, is_system):
    """Writes all included directories' paths to the CLion project file.

    Args:
        hfile: A file handler instance.
        includes: A list of included file paths.
        is_system: A boolean of whether it's a system flag.
    """
    if not includes:
        return
    _write_all_includes(hfile, includes, is_system)
    _write_all_headers(hfile, includes)


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


@common_util.check_args(mod_info=dict)
@common_util.io_error_handle
def generate_cmakelists_file(mod_info):
    """Generates CLion project file from the target module's info.

    Args:
        mod_info: A module's info dictionary.
    """


@common_util.io_error_handle
def generate_base_cmakelists_file(cc_module_info, project_path, mod_names):
    """Generates base CLion project file for multiple CLion projects.

    Args:
        cc_module_info: An instance of native_module_info.NativeModuleInfo.
        project_path: A string of the base project relative path.
        mod_names: A list of module names whose project were created under
                   project_path.
    """
