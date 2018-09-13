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

"""module_info_util

This module receives a module path which is relative to its root directory and
makes a command to generate two json files, one for mk files and one for bp
files. Then it will load these two json files into two json dictionaries,
merge them into one dictionary and return the merged dictionary to its caller.

Example usage:
module_info_obj = ModuleInfoUtil()
project.dependency_info = module_info_obj.generate_module_info_json(module_path)
"""

import json
import logging
import os
import subprocess

from aidegen.lib import errors
from atest import constants
from atest import module_info

_BLUEPRINT_JSONFILE_NAME = "module_bp_java_deps.json"
_BLUEPRINT_JSONFILE_OUTDIR = "out/soong/"
_KEY_CLS = 'class'
_KEY_PATH = 'path'
_KEY_INS = 'installed'
_KEY_DEP = 'dependencies'
_KEY_SRCS = 'srcs'
_MERGE_NEEDED_ITEMS = [_KEY_CLS, _KEY_PATH, _KEY_INS, _KEY_DEP, _KEY_SRCS]
_BUILD_JSON_COMMAND = ("source build/envsetup.sh;"
                       "export SOONG_COLLECT_JAVA_DEPS=1;mmma %s")
_RELATIVE_PATH = "../"

class ModuleInfoUtil(object):
    """Class offers a merged dictionary of both mk and bp json files and
    fast/easy lookup for Module related details."""

    def __init__(self):
        self._atest_module_info = module_info.ModuleInfo()

    @property
    def atest_module_info(self):
        """Return Atest module info instance."""
        return self._atest_module_info

    def generate_module_info_json(self, module_path):
        """Generate a merged json dictionary.

        Linked functions:
            _open_json(json_path)
            _merge_json(mk_dict, bp_dict)

        Args:
            module_path: A module path related to the android aosp root.

        Returns:
            A merged json dictionary.
        """
        root_dir = os.environ.get(constants.ANDROID_BUILD_TOP, '/')
        os.chdir(root_dir)
        cmd = (_BUILD_JSON_COMMAND) % module_path
        try:
            os.system(cmd)
            logging.info('Build successful: %s', cmd)
        except subprocess.CalledProcessError as err:
            logging.error('Failed build command: %s, error output: %s', cmd,
                          err.output)
            raise

        mk_dict = self._atest_module_info.name_to_module_info
        soong_out_dir = os.path.join(root_dir, _BLUEPRINT_JSONFILE_OUTDIR)
        bp_json_path = os.path.join(soong_out_dir, _BLUEPRINT_JSONFILE_NAME)
        bp_dict = _open_json(bp_json_path)
        return _merge_json(mk_dict, bp_dict)


def _open_json(json_path):
    """Load a json file and convert it into a json dictionary.

    Args:
        json_path: A json file path.

    Returns:
        A json dictionary.
    """
    try:
        with open(json_path) as jfile:
            json_dict = json.load(jfile)
            return json_dict
    except IOError as err:
        raise errors.JsonFileNotExistError(
            "%s does not exist, error: %s." % (json_path, err))


def _merge_module_keys(m_dict, b_dict):
    """Merge a module's json dictionary into another module's json dictionary.

    Args:
        m_dict: The module dictionary is going to merge b_dict into.
        b_dict: Soong build system module dictionary.
    """
    for key, b_modules in b_dict.items():
        m_dict[key] = sorted(list(set(m_dict.get(key, []) + b_modules)))


def _copy_needed_items_from(mk_dict):
    """Shallow copy needed items from Make build system part json dictionary.

    Args:
        mk_dict: Make build system json dictionary is going to be copyed.

    Returns:
        A merged json dictionary.
    """
    merged_dict = dict()
    for module in mk_dict.keys():
        merged_dict[module] = dict()
        for key in mk_dict[module].keys():
            if key in _MERGE_NEEDED_ITEMS and mk_dict[module][key] != []:
                merged_dict[module][key] = mk_dict[module][key]
    return merged_dict


def _join_mk_local_path_to_source_paths(merged_dict):
    """Join mk json dictionary's path to srcs.

    This function should be called directly after calling
    _copy_needed_items_from function.

    Args:
        merged_dict: Merged json dictionary.

    Returns:
        A merged json dictionary.

    For example:
                {
                    'path': ['path/to/the/module'],
                    'srcs': [
                        'src/com/android/test.java',
                        'src/com/google/test.java']
                }
    After calling this function, it will become:
                {
                    'path': ['path/to/the/module'],
                    'srcs': [
                        'path/to/the/module/src/com/android/test.java',
                        'path/to/the/module/src/com/google/test.java']
                }
    """
    for module in merged_dict.keys():
        keys = merged_dict[module].keys()
        if _KEY_PATH in keys and _KEY_SRCS in keys:
            path = merged_dict[module][_KEY_PATH][0]
            srcs = list()
            for src in merged_dict[module][_KEY_SRCS]:
                src = os.path.join(path, src)
                if _RELATIVE_PATH in src:
                    src = os.path.relpath(src)
                srcs.append(src)
            merged_dict[module][_KEY_SRCS] = srcs
    return merged_dict


def _merge_json(mk_dict, bp_dict):
    """Merge two json dictionaries.

    Linked function:
        _merge_module_keys(m_dict, b_dict)

    Args:
        mk_dict: Make build system part json dictionary.
        bp_dict: Soong build system part json dictionary.

    Returns:
        A merged json dictionary.
    """
    merged_dict = _copy_needed_items_from(mk_dict)
    merged_dict = _join_mk_local_path_to_source_paths(merged_dict)
    for module in bp_dict.keys():
        if not module in merged_dict.keys():
            merged_dict[module] = dict()
        _merge_module_keys(merged_dict[module], bp_dict[module])
    return merged_dict
