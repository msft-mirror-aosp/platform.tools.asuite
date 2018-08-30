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

import logging


def _open_json(json_path):
    """Load a json file and convert it into a json dictionary.

    Args:
        json_path: A json file path.

    Returns:
        A json dictionary.
    """
    logging.info("json file name:%s", json_path)


def _merge_module_keys(m_dict, b_dict):
    """Merge a module's json dictionary into another module's json dictionary.

    Args:
        m_dict: The module dictionary is going to merge b_dict into.
        b_dict: Soong build system module dictionary.
    """
    logging.info("merged dict:%s", m_dict)
    logging.info("bp dict:%s", b_dict)


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
    logging.info("mk dict:%s", mk_dict)
    logging.info("bp dict:%s", bp_dict)


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
    logging.info("module path:%s", module_path)
