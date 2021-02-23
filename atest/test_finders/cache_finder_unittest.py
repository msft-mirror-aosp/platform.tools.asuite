#!/usr/bin/env python3
#
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

"""Unittests for cache_finder."""

# pylint: disable=line-too-long

import unittest
import os

from unittest import mock

import atest_utils
import constants
import module_info
import unittest_constants as uc

from test_finders import cache_finder


#pylint: disable=protected-access
class CacheFinderUnittests(unittest.TestCase):
    """Unit tests for cache_finder.py"""
    def setUp(self):
        """Set up stuff for testing."""
        self.cache_finder = cache_finder.CacheFinder()
        self.cache_finder.module_info = mock.Mock(spec=module_info.ModuleInfo)

    @mock.patch.object(cache_finder.CacheFinder, '_is_test_filter_valid',
                       return_value=True)
    @mock.patch.object(cache_finder.CacheFinder, '_is_test_build_target_valid',
                       return_value=True)
    @mock.patch.object(atest_utils, 'get_test_info_cache_path')
    def test_find_test_by_cache(self, mock_get_cache_path,
            _mock_build_target_valid, _mock_filter_valid):
        """Test find_test_by_cache method."""
        uncached_test = 'mytest1'
        cached_test = 'hello_world_test'
        uncached_test2 = 'mytest2'
        test_cache_root = os.path.join(uc.TEST_DATA_DIR, 'cache_root')
        # Hit matched cache file but no original_finder in it,
        # should return None.
        mock_get_cache_path.return_value = os.path.join(
            test_cache_root,
            'cd66f9f5ad63b42d0d77a9334de6bb73.cache')
        self.assertIsNone(self.cache_finder.find_test_by_cache(uncached_test))
        # Hit matched cache file and original_finder is in it,
        # should return cached test infos.
        self.cache_finder.module_info.get_paths.return_value = [
            'platform_testing/tests/example/native']
        mock_get_cache_path.return_value = os.path.join(
            test_cache_root,
            '78ea54ef315f5613f7c11dd1a87f10c7.cache')
        self.assertIsNotNone(self.cache_finder.find_test_by_cache(cached_test))
        # Does not hit matched cache file, should return cached test infos.
        mock_get_cache_path.return_value = os.path.join(
            test_cache_root,
            '39488b7ac83c56d5a7d285519fe3e3fd.cache')
        self.assertIsNone(self.cache_finder.find_test_by_cache(uncached_test2))

    @mock.patch.object(cache_finder.CacheFinder, '_is_test_build_target_valid',
                       return_value=True)
    @mock.patch.object(atest_utils, 'get_test_info_cache_path')
    def test_find_test_by_cache_wo_valid_path(self, mock_get_cache_path,
            _mock_build_target_valid):
        """Test find_test_by_cache method."""
        cached_test = 'hello_world_test'
        test_cache_root = os.path.join(uc.TEST_DATA_DIR, 'cache_root')
        # Return None when the actual test_path is not identical to that in the
        # existing cache.
        self.cache_finder.module_info.get_paths.return_value = [
            'not/matched/test/path']
        mock_get_cache_path.return_value = os.path.join(
            test_cache_root,
            '78ea54ef315f5613f7c11dd1a87f10c7.cache')
        self.assertIsNone(self.cache_finder.find_test_by_cache(cached_test))

    @mock.patch.object(cache_finder.CacheFinder, '_is_test_build_target_valid',
                       return_value=False)
    @mock.patch.object(cache_finder.CacheFinder, '_is_test_path_valid',
                       return_value=True)
    @mock.patch.object(atest_utils, 'get_test_info_cache_path')
    def test_find_test_by_cache_wo_valid_build_target(self, mock_get_cache_path,
            _mock_path_valid, _mock_build_target_valid):
        """Test find_test_by_cache method."""
        cached_test = 'hello_world_test'
        test_cache_root = os.path.join(uc.TEST_DATA_DIR, 'cache_root')
        # Return None when the build target is not exist in module-info.
        mock_get_cache_path.return_value = os.path.join(
            test_cache_root,
            '78ea54ef315f5613f7c11dd1a87f10c7.cache')
        self.assertIsNone(self.cache_finder.find_test_by_cache(cached_test))

    @mock.patch.object(cache_finder.CacheFinder, '_is_test_filter_valid',
                       return_value=False)
    @mock.patch.object(cache_finder.CacheFinder, '_is_test_build_target_valid',
                       return_value=True)
    @mock.patch.object(cache_finder.CacheFinder, '_is_test_path_valid',
                       return_value=True)
    @mock.patch.object(atest_utils, 'get_test_info_cache_path')
    def test_find_test_by_cache_wo_valid_java_filter(self, mock_get_cache_path,
        _mock_path_valid, _mock_build_target_valid, _mock_filter_valid):
        """Test _is_test_filter_valid method."""
        cached_test = 'hello_world_test'
        test_cache_root = os.path.join(uc.TEST_DATA_DIR, 'cache_root')
        # Return None if the cached test filter is not valid.
        mock_get_cache_path.return_value = os.path.join(
            test_cache_root,
            '78ea54ef315f5613f7c11dd1a87f10c7.cache')
        self.assertIsNone(self.cache_finder.find_test_by_cache(cached_test))

    def test_is_java_filter_in_module_for_java_class(self):
        """Test _is_java_filter_in_module method if input is java class."""
        mock_mod = {constants.MODULE_SRCS:
                             ['src/a/b/c/MyTestClass1.java']}
        self.cache_finder.module_info.get_module_info.return_value = mock_mod
        # Should not match if class name does not exist.
        self.assertFalse(
            self.cache_finder._is_java_filter_in_module(
                'MyModule', 'a.b.c.MyTestClass'))
        # Should match if class name exist.
        self.assertTrue(
            self.cache_finder._is_java_filter_in_module(
                'MyModule', 'a.b.c.MyTestClass1'))

    def test_is_java_filter_in_module_for_java_package(self):
        """Test _is_java_filter_in_module method if input is java package."""
        mock_mod = {constants.MODULE_SRCS:
                        ['src/a/b/c/MyTestClass1.java']}
        self.cache_finder.module_info.get_module_info.return_value = mock_mod
        # Should not match if package name does not match the src.
        self.assertFalse(
            self.cache_finder._is_java_filter_in_module(
                'MyModule', 'a.b.c.d'))
        # Should match if package name matches the src.
        self.assertTrue(
            self.cache_finder._is_java_filter_in_module(
                'MyModule', 'a.b.c'))

if __name__ == '__main__':
    unittest.main()
