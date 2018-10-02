#!/usr/bin/env python3
#
# Copyright 2018, The Android Open Source Project
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

"""Unittests for module_info_utils."""

import copy
import unittest

from aidegen.lib import module_info_util

_TEST_CLASS_DICT = {'class': ['JAVA_LIBRARIES']}
_TEST_SRCS_BAR_DICT = {'srcs': ['Bar']}
_TEST_SRCS_BAZ_DICT = {'srcs': ['Baz']}
_TEST_DEP_FOO_DIST = {'dependencies': ['Foo']}
_TEST_DEP_SRC_DICT = {'dependencies': ['Foo'], 'srcs': ['Bar']}
_TEST_DEP_SRC_MORE_DICT = {'dependencies': ['Foo'], 'srcs': ['Baz', 'Bar']}
_TEST_MODULE_A_DICT = {
    'module_a': {
        'class': ['JAVA_LIBRARIES'],
        'path': ['path_a'],
        'installed': ['out/path_a/a.jar'],
        'dependencies': ['Foo'],
        'srcs': ['Bar']
    }
}
_TEST_MODULE_A_DICT_HAS_NONEED_ITEMS = {
    'module_a': {
        'class': ['JAVA_LIBRARIES'],
        'path': ['path_a'],
        'installed': ['out/path_a/a.jar'],
        'dependencies': ['Foo'],
        'srcs': ['Bar'],
        'compatibility_suites': ['null-suite'],
        'module_name': ['ltp_fstat03_64']
    }
}
_TEST_MODULE_A_JOIN_PATH_DICT = {
    'module_a': {
        'class': ['JAVA_LIBRARIES'],
        'path': ['path_a'],
        'installed': ['out/path_a/a.jar'],
        'dependencies': ['Foo'],
        'srcs': ['path_a/Bar']
    }
}
_TEST_MODULE_A_JOIN_WITHOUT_PATH_DICT = {
    'module_a': {
        'class': ['JAVA_LIBRARIES'],
        'installed': ['out/path_a/a.jar'],
        'dependencies': ['Foo'],
        'srcs': ['path_a/Bar']
    }
}
_TEST_MODULE_WITH_RELATIVE_PATH_DICT = {
    'module_a': {
        'path': ['cts/tests/tests/appwidget/packages/launchermanifest'],
        'srcs': ['../../common/src/android/Constants.java']
    }
}
_TEST_MODULE_WITH_RELATIVE_PATH_DICT_RESULT = {
    'module_a': {
        'path': ['cts/tests/tests/appwidget/packages/launchermanifest'],
        'srcs': ['cts/tests/tests/appwidget/common/src/android/Constants.java']
    }
}


# pylint: disable=protected-access
# pylint: disable=invalid-name
class AidegenModuleInfoUtilUnittests(unittest.TestCase):
    """Unit tests for moduole_info_utils.py"""

    def test_merge_module_keys_with_empty_dict(self):
        """Test _merge_module_keys with an empty dictionary."""
        test_b_dict = {}
        test_m_dict = copy.deepcopy(_TEST_DEP_SRC_DICT)
        module_info_util._merge_module_keys(test_m_dict, test_b_dict)
        self.assertEqual(_TEST_DEP_SRC_DICT, test_m_dict)

    def test_merge_module_keys_with_key_not_in_orginial_dict(self):
        """Test _merge_module_keys with the key does not exist in the dictionary
        to be merged into.
        """
        test_b_dict = _TEST_SRCS_BAR_DICT
        test_m_dict = copy.deepcopy(_TEST_DEP_FOO_DIST)
        module_info_util._merge_module_keys(test_m_dict, test_b_dict)
        self.assertEqual(_TEST_DEP_SRC_DICT, test_m_dict)

    def test_merge_module_keys_with_key_in_orginial_dict(self):
        """Test _merge_module_keys with with the key exists in the dictionary
        to be merged into.
        """
        test_b_dict = _TEST_SRCS_BAZ_DICT
        test_m_dict = copy.deepcopy(_TEST_DEP_SRC_DICT)
        module_info_util._merge_module_keys(test_m_dict, test_b_dict)
        self.assertEqual(
            set(_TEST_DEP_SRC_MORE_DICT['srcs']), set(test_m_dict['srcs']))
        self.assertEqual(
            set(_TEST_DEP_SRC_MORE_DICT['dependencies']),
            set(test_m_dict['dependencies']))

    def test_merge_module_keys_with_duplicated_item_dict(self):
        """Test _merge_module_keys with with the key exists in the dictionary
        to be merged into.
        """
        test_b_dict = _TEST_CLASS_DICT
        test_m_dict = copy.deepcopy(_TEST_CLASS_DICT)
        module_info_util._merge_module_keys(test_m_dict, test_b_dict)
        self.assertEqual(_TEST_CLASS_DICT, test_m_dict)

    def test_copy_needed_items_from_empty_dict(self):
        """Test _copy_needed_items_from an empty dictionary."""
        test_mk_dict = {}
        want_dict = {}
        self.assertEqual(want_dict,
                         module_info_util._copy_needed_items_from(test_mk_dict))

    def test_copy_needed_items_from_all_needed_items_dict(self):
        """Test _copy_needed_items_from a dictionary with all needed items."""
        self.assertEqual(
            _TEST_MODULE_A_DICT,
            module_info_util._copy_needed_items_from(_TEST_MODULE_A_DICT))

    def test_copy_needed_items_from_some_needed_items_dict(self):
        """Test _copy_needed_items_from a dictionary with some needed items."""
        self.assertEqual(
            _TEST_MODULE_A_DICT,
            module_info_util._copy_needed_items_from(
                _TEST_MODULE_A_DICT_HAS_NONEED_ITEMS))

    def test_join_mk_local_path_to_source_paths_without_path(self):
        """Test _join_mk_local_path_to_source_paths a dictionary without path
        item.
        """
        test_m_dict = copy.deepcopy(_TEST_MODULE_A_JOIN_WITHOUT_PATH_DICT)
        self.assertEqual(
            _TEST_MODULE_A_JOIN_WITHOUT_PATH_DICT,
            module_info_util._join_mk_local_path_to_source_paths(test_m_dict))

    def test_join_mk_local_path_to_source_paths(self):
        """Test _join_mk_local_path_to_source_paths a dictionary with path
        items.
        """
        test_m_dict = copy.deepcopy(_TEST_MODULE_A_DICT)
        self.assertEqual(
            _TEST_MODULE_A_JOIN_PATH_DICT,
            module_info_util._join_mk_local_path_to_source_paths(test_m_dict))


    def test_join_mk_local_path_to_source_paths_with_relative_paths(self):
        """Test _join_mk_local_path_to_source_paths a dictionary with source
        has relative path items.
        """
        test_m_dict = copy.deepcopy(_TEST_MODULE_WITH_RELATIVE_PATH_DICT)
        self.assertEqual(
            _TEST_MODULE_WITH_RELATIVE_PATH_DICT_RESULT,
            module_info_util._join_mk_local_path_to_source_paths(test_m_dict))


if __name__ == '__main__':
    unittest.main()
