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
project.dependency_info = generate_module_info_json(module_path)
"""

import json
import logging
import os
import subprocess

from aidegen.lib import constants
from aidegen.lib import errors

_ANDROID_PRODUCT_OUT = "ANDROID_PRODUCT_OUT"
_BLUEPRINT_JSONFILE_NAME = "module_bp_java_deps.json"
_MAKEFILE_JSONFILE_NAME = "module-info.json"
_BLUEPRINT_JSONFILE_OUTDIR = "out/soong/"
_MERGE_NEEDED_ITEMS = ["class", "path", "installed", "dependencies", "srcs"]
_COMMAND = ("source build/envsetup.sh;make %s;export SOONG_COLLECT_JAVA_DEPS=1;"
            "mmma %s")

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
        raise errors.JsonFileNotExistError("%s does not exist, error: %s."
                                           % (json_path, err))


def _merge_module_keys(m_dict, b_dict):
    """Merge a module's json dictionary into another module's json dictionary.

    Args:
        m_dict: The module dictionary is going to merge b_dict into.
        b_dict: Soong build system module dictionary.
    """
    for key in b_dict.keys():
        if key in m_dict.keys():
            m_dict[key].extend(b_dict[key])
        else:
            m_dict[key] = b_dict[key]


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
    for module in bp_dict.keys():
        if not module in merged_dict.keys():
            merged_dict[module] = dict()
        _merge_module_keys(merged_dict[module], bp_dict[module])
    return merged_dict


def generate_module_info_json(module_path):
    """Generate a merged json dictionary.

    generate_module_info_json entry

    Linked functions:
        _open_json(json_path)
        _merge_json(mk_dict, bp_dict)

    Args:
        module_path: A module path related to the android aosp root.

    Returns:
        A merged json dictionary.
    """
    merged_dict = dict()
    root_dir = os.environ.get(constants.ANDROID_BUILD_TOP, '/')
    os.chdir(root_dir)
    product_out_dir = os.environ.get(_ANDROID_PRODUCT_OUT)
    mk_json_path = os.path.join(product_out_dir, _MAKEFILE_JSONFILE_NAME)
    mk_json_relative_path = os.path.relpath(mk_json_path, root_dir)
    cmd = (_COMMAND) % (mk_json_relative_path, module_path)
    try:
        returncode = os.system(cmd)
        logging.info('Build successful: %s', cmd)
    except subprocess.CalledProcessError as err:
        logging.error('Error building: %s', cmd)
        if err.output:
            logging.error(err.output)
        raise subprocess.CalledProcessError(returncode, cmd, None)

    mk_dict = _open_json(mk_json_path)
    soong_out_dir = os.path.join(root_dir, _BLUEPRINT_JSONFILE_OUTDIR)
    bp_json_path = os.path.join(soong_out_dir, _BLUEPRINT_JSONFILE_NAME)
    bp_dict = _open_json(bp_json_path)
    merged_dict = _merge_json(mk_dict, bp_dict)
    return merged_dict
