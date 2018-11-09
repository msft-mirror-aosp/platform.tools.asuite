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
merged_dict = generate_module_info_json(atest_module_info, project, verbose)
"""

import glob
import json
import os
import sys

from aidegen.lib.common_util import time_logged
from aidegen.lib.common_util import get_related_paths
from aidegen.lib import errors
from atest import atest_utils
from atest import constants

_BLUEPRINT_JSONFILE_NAME = 'module_bp_java_deps.json'
_BLUEPRINT_JSONFILE_OUTDIR = 'out/soong/'
_KEY_CLS = 'class'
_KEY_PATH = 'path'
_KEY_INS = 'installed'
_KEY_DEP = 'dependencies'
_KEY_SRCS = 'srcs'
_MERGE_NEEDED_ITEMS = [_KEY_CLS, _KEY_PATH, _KEY_INS, _KEY_DEP, _KEY_SRCS]
_BUILD_ENV_VARS = {
    'SOONG_COLLECT_JAVA_DEPS': 'true',
    'DISABLE_ROBO_RUN_TESTS': 'true'
}
_MODULES_IN = 'MODULES-IN-%s'
_RELATIVE_PATH = '../'
_INTELLIJ_PROJECT_FILE_EXT = '*.iml'
_LAUNCH_PROJECT_QUERY = (
    'There exists an IntelliJ project file: %s. Do you want '
    'to launch it (yes/No)?')


@time_logged
def generate_module_info_json(module_info, projects, verbose):
    """Generate a merged json dictionary.

    Linked functions:
        _build_target(project, verbose)
        _get_soong_build_json_dict()
        _merge_json(mk_dict, bp_dict)

    Args:
        module_info: A ModuleInfo instance contains data of module-info.json.
        projects: A list of project names.
        verbose: A boolean, if true displays full build output.

    Returns:
        A tuple of Atest module info instance and a merged json dictionary.
    """
    _build_target(projects, module_info, verbose)
    mk_dict = module_info.name_to_module_info
    bp_dict = _get_soong_build_json_dict()
    return _merge_json(mk_dict, bp_dict)


def _build_target(projects, module_info, verbose):
    """Build input project list to generate _BLUEPRINT_JSONFILE_NAME.

    When we build a list of projects, we look up in module-info dictionary to
    get project's relative and absolute paths for generating build target list
    and then pass it to build function in Atest.

    Args:
        projects: A list of project names.
        module_info: A ModuleInfo instance contains data of module-info.json.
        verbose: A boolean, if true displays full build output.

    Build results:
        1. Build successfully return.
        2. Build failed:
           1) There's no project file, raise BuildFailureError.
           2) There exists a project file, ask users if they want to
              launch IDE with the old project file.
              a) If the answer is yes, return.
              b) If the answer is not yes, sys.exit(1)
    """
    build_targets = []
    main_project_path = None
    for target in projects:
        rel_path, abs_path = get_related_paths(module_info, target)
        build_target = _MODULES_IN % rel_path.replace('/', '-')
        build_targets.append(build_target)
        if not main_project_path:
            main_project_path = abs_path
    successful_build = atest_utils.build(
        build_targets, verbose=verbose, env_vars=_BUILD_ENV_VARS)
    if not successful_build:
        project_file = glob.glob(
            os.path.join(main_project_path, _INTELLIJ_PROJECT_FILE_EXT))
        if project_file:
            query = (_LAUNCH_PROJECT_QUERY) % project_file[0]
            input_data = input(query)
            if not input_data.lower() in ['yes', 'y']:
                sys.exit(1)
        else:
            raise errors.BuildFailureError(
                'Failed to build %s.' % ' '.join(build_targets))


def _get_soong_build_json_dict():
    """Load a json file from path and convert it into a json dictionary.

    Returns:
        A json dictionary.
    """
    root_dir = os.environ.get(constants.ANDROID_BUILD_TOP, os.sep)
    soong_out_dir = os.path.join(root_dir, _BLUEPRINT_JSONFILE_OUTDIR)
    json_path = os.path.join(soong_out_dir, _BLUEPRINT_JSONFILE_NAME)
    try:
        with open(json_path) as jfile:
            json_dict = json.load(jfile)
            return json_dict
    except IOError as err:
        raise errors.JsonFileNotExistError(
            '%s does not exist, error: %s.' % (json_path, err))


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
