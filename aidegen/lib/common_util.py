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

import functools
import logging
import time


def time_logged(func):
    """Decorate a function to find out how much time it spends.

    Args:
        func: a function is to be calculated its spending time.

    Returns:
        The wrapper function.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        """A wrapper function."""

        start = time.time()
        try:
            return func(*args, **kwargs)
        finally:
            logging.debug('{}.{} time consumes: {:.2f}s'.format(
                func.__module__, func.__name__,
                time.time() - start))

    return wrapper
