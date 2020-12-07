# Copyright 2019, The Android Open Source Project
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

"""
Cache Finder class.
"""

import atest_utils
import constants

from test_finders import test_finder_base
from test_finders import test_info

class CacheFinder(test_finder_base.TestFinderBase):
    """Cache Finder class."""
    NAME = 'CACHE'

    def __init__(self, module_info=None):
        super().__init__()
        self.module_info = module_info

    def _is_latest_testinfos(self, test_infos):
        """Check whether test_infos are up-to-date.

        Args:
            test_infos: A list of TestInfo.

        Returns:
            True if all keys in test_infos and TestInfo object are equal.
            Otherwise, False.
        """
        sorted_base_ti = sorted(
            vars(test_info.TestInfo(None, None, None)).keys())
        for cached_test_info in test_infos:
            sorted_cache_ti = sorted(vars(cached_test_info).keys())
            if not sorted_cache_ti == sorted_base_ti:
                return False
        return True

    def find_test_by_cache(self, test_reference):
        """Find the matched test_infos in saved caches.

        Args:
            test_reference: A string of the path to the test's file or dir.

        Returns:
            A list of TestInfo namedtuple if cache found and is in latest
            TestInfo format, else None.
        """
        test_infos = atest_utils.load_test_info_cache(test_reference)
        if test_infos and self._is_test_infos_valid(test_infos):
            return test_infos
        return None

    def _is_test_infos_valid(self, test_infos):
        """Check if the given test_infos are valid.

        Args:
            test_infos: A list of TestInfo.

        Returns:
            True if test_infos are all valid. Otherwise, False.
        """
        if not self._is_latest_testinfos(test_infos):
            return False
        for t_info in test_infos:
            if not self._is_test_path_valid(t_info):
                return False
            # TODO: (b/172260100) Check if all the build target is valid.
            if not self._is_test_build_target_valid(t_info):
                return False
            # TODO: (b/172260100) Check if the cached test filter is valid.
            if not self._is_test_filter_valid(t_info):
                return False
        return True

    def _is_test_path_valid(self, t_info):
        """Check if test path is valid.

        Args:
            t_info: TestInfo that has been filled out by a find method.

        Returns:
            True if test path is valid. Otherwise, False.
        """
        cached_test_paths = t_info.get_test_paths()
        current_test_paths = self.module_info.get_paths(t_info.test_name)
        if not current_test_paths:
            return False
        if sorted(cached_test_paths) != sorted(current_test_paths):
            return False
        return True

    def _is_test_build_target_valid(self, t_info):
        """Check if test build targets are valid.

        Args:
            t_info: TestInfo that has been filled out by a find method.

        Returns:
            True if test's build target is valid. Otherwise, False.
        """
        # If the cached build target can be found in current module-info, then
        # it is a valid build targets of the test.
        for build_target in t_info.build_targets:
            if self.module_info.is_module(build_target):
                return False
        return True

    def _is_test_filter_valid(self, t_info):
        """Check if test filter is valid.

        Args:
            t_info: TestInfo that has been filled out by a find method.

        Returns:
            True if test filter is valid. Otherwise, False.
        """
        # TODO: (b/172260100) Implement the check for test filter.
        t_info.data.get(constants.TI_FILTER, frozenset())
        return True
