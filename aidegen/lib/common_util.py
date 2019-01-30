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

"""common_util

This module has a collection of functions that provide helper functions to
other modules.
"""

import logging
import os
import time

from functools import partial
from functools import wraps

from aidegen import constant
from aidegen.lib.errors import FakeModuleError
from aidegen.lib.errors import NoModuleDefinedInModuleInfoError
from aidegen.lib.errors import ProjectOutsideAndroidRootError
from aidegen.lib.errors import ProjectPathNotExistError
from atest import constants
from atest.atest_utils import colorize

COLORED_INFO = partial(colorize, color=constants.MAGENTA, highlight=False)
COLORED_PASS = partial(colorize, color=constants.GREEN, highlight=False)
COLORED_FAIL = partial(colorize, color=constants.RED, highlight=False)
FAKE_MODULE_ERROR = '{} is a fake module.'
OUTSIDE_ROOT_ERROR = '{} is outside android root.'
PATH_NOT_EXISTS_ERROR = 'The path {} doesn\'t exist.'
NO_MODULE_DEFINED_ERROR = 'No modules defined at {}.'


def time_logged(func=None, *, message='', maximum=1):
    """Decorate a function to find out how much time it spends.

    Args:
        func: a function is to be calculated its spending time.
        message: the message the decorated function wants to show.
        maximum: a interger, minutes. If time exceeds the maximum time show
                 message, otherwise doesn't.

    Returns:
        The wrapper function.
    """
    if func is None:
        return partial(time_logged, message=message, maximum=maximum)

    @wraps(func)
    def wrapper(*args, **kwargs):
        """A wrapper function."""

        start = time.time()
        try:
            return func(*args, **kwargs)
        finally:
            timestamp = time.time() - start
            logging.debug('{}.{} time consumes: {:.2f}s'.format(
                func.__module__, func.__name__,
                timestamp))
            if message and timestamp > maximum * 60:
                print(message)

    return wrapper


def get_related_paths(module_info, target=None):
    """Get the relative and absolute paths of target from module-info.

    Args:
        module_info: A ModuleInfo instance contains data of module-info.json.
        target: A string user input from command line. It could be several cases
                such as:
                1. Module name, e.g. Settings
                2. Module path, e.g. packages/apps/Settings
                3. Relative path, e.g. ../../packages/apps/Settings
                4. Current directory, e.g. . or no argument

    Return:
        rel_path: The relative path of a module, return None if no matching
                  module found.
        abs_path: The absolute path of a module, return None if no matching
                  module found.
    """
    rel_path = None
    abs_path = None
    if target:
        # User inputs a module name.
        if module_info.is_module(target):
            paths = module_info.get_paths(target)
            if paths:
                rel_path = paths[0]
                abs_path = os.path.join(constant.ANDROID_ROOT_PATH, rel_path)
        # User inputs a module path or a relative path of android root folder.
        elif (module_info.get_module_names(target) or
              os.path.isdir(os.path.join(constant.ANDROID_ROOT_PATH, target))):
            rel_path = target.strip(os.sep)
            abs_path = os.path.join(constant.ANDROID_ROOT_PATH, rel_path)
        # User inputs a relative path of current directory.
        else:
            abs_path = os.path.abspath(os.path.join(os.getcwd(), target))
            rel_path = os.path.relpath(abs_path, constant.ANDROID_ROOT_PATH)
    else:
        # User doesn't input.
        abs_path = os.getcwd()
        rel_path = os.path.relpath(abs_path, constant.ANDROID_ROOT_PATH)
    return rel_path, abs_path


def is_target_android_root(atest_module_info, targets):
    """Check if any target is the android root path.

    Args:
        atest_module_info: A ModuleInfo instance contains data of
                           module-info.json.
        targets: A list of target modules or project paths from user input.

    Returns:
        True if target is android root, otherwise false.
    """
    for target in targets:
        _, abs_path = get_related_paths(atest_module_info, target)
        if abs_path == constant.ANDROID_ROOT_PATH:
            return True
    return False


def has_build_target(atest_module_info, rel_path):
    """Determine if a relative path contains buildable module.

    Args:
        atest_module_info: A ModuleInfo instance contains data of
                           module-info.json.
        rel_path: The module path relative to android root.

    Returns:
        True if the relative path contains a build target, otherwise false.
    """
    return any(
        mod_path.startswith(rel_path)
        for mod_path in atest_module_info.path_to_module_info)


def check_modules(atest_module_info, targets):
    """Check if all targets are valid build targets."""
    for target in targets:
        check_module(atest_module_info, target)


def check_module(atest_module_info, target):
    """Check if a target is a valid build target or a project path containing
       build target.

    The rules:
        1. If module's absolute path is None, raise FakeModuleError.
        2. If the module doesn't exist in android root,
           raise ProjectOutsideAndroidRootError.
        3. If module's absolute path is not a directory,
           raise ProjectPathNotExistError.
        4. If it contains any build target continue checking, else:
           1) If it's android root, continue checking.
           2) If none of above, raise NoModuleDefinedInModuleInfoError.

    Args:
        atest_module_info: A ModuleInfo instance contains data of
                           module-info.json.
        target: A target module or project path from user input, when locating
                the target, project with matched module name of the target has a
                higher priority than project path. It could be several cases
                such as:
                1. Module name, e.g. Settings
                2. Module path, e.g. packages/apps/Settings
                3. Relative path, e.g. ../../packages/apps/Settings
                4. Current directory, e.g. . or no argument
    """
    rel_path, abs_path = get_related_paths(atest_module_info, target)
    if not abs_path:
        err = FAKE_MODULE_ERROR.format(target)
        logging.error(err)
        raise FakeModuleError(err)
    if not abs_path.startswith(constant.ANDROID_ROOT_PATH):
        err = OUTSIDE_ROOT_ERROR.format(abs_path)
        logging.error(err)
        raise ProjectOutsideAndroidRootError(err)
    if not os.path.isdir(abs_path):
        err = PATH_NOT_EXISTS_ERROR.format(rel_path)
        logging.error(err)
        raise ProjectPathNotExistError(err)
    if (not has_build_target(atest_module_info, rel_path)
            and abs_path != constant.ANDROID_ROOT_PATH):
        err = NO_MODULE_DEFINED_ERROR.format(rel_path)
        logging.error(err)
        raise NoModuleDefinedInModuleInfoError(err)


def get_abs_path(rel_path):
    """Get absolute path from a relative path.

    Args:
        rel_path: A string, a relative path to constant.ANDROID_ROOT_PATH.

    Returns:
        abs_path: A string, an absolute path starts with
                  constant.ANDROID_ROOT_PATH.
    """
    if not rel_path:
        return constant.ANDROID_ROOT_PATH
    if rel_path.startswith(constant.ANDROID_ROOT_PATH):
        return rel_path
    return os.path.join(constant.ANDROID_ROOT_PATH, rel_path)
