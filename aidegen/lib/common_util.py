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
from atest import constants
from atest.atest_utils import colorize

COLORED_INFO = partial(colorize, color=constants.MAGENTA, highlight=False)


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
        # User inputs a module path.
        elif module_info.get_module_names(target):
            rel_path = target
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
