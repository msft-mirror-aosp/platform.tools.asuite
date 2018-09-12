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

import unittest

from aidegen.lib import module_info_util

_TEST_CLASS_DICT = {"class":["JAVA_LIBRARIES"]}
_TEST_DEP_SRC_DICT = {"dependencies":["Foo"], "srcs":["Bar"]}
_TEST_MODULE_A_DICT = {"module_a":{"class":["JAVA_LIBRARIES"],
                                   "path":["path_a"],
                                   "installed":["out/path_a/a.jar"],
                                   "dependencies":["Foo"],
                                   "srcs":["Bar"]}}

# pylint: disable=protected-access
# pylint: disable=invalid-name
class AidegenModuleInfoUtilUnittests(unittest.TestCase):
    """Unit tests for moduole_info_utils.py"""

    def test_merge_module_keys_with_empty_dict(self):
        """Test _merge_module_keys with an empty dictionary."""
        test_b_dict = {}
        test_m_dict = {"dependencies":["Foo"], "srcs":["Bar"]}
        module_info_util._merge_module_keys(test_m_dict, test_b_dict)
        self.assertEqual(_TEST_DEP_SRC_DICT, test_m_dict)


    def test_merge_module_keys_with_key_not_in_orginial_dict(self):
        """Test _merge_module_keys with the key does not exist in the dictionary
        to be merged into."""
        test_b_dict = {"srcs":["Bar"]}
        test_m_dict = {"dependencies":["Foo"]}
        module_info_util._merge_module_keys(test_m_dict, test_b_dict)
        self.assertEqual(_TEST_DEP_SRC_DICT, test_m_dict)


    def test_merge_module_keys_with_key_in_orginial_dict(self):
        """Test _merge_module_keys with with the key exists in the dictionary
        to be merged into."""
        test_b_dict = {"srcs":["Baz"]}
        test_m_dict = {"dependencies":["Foo"], "srcs":["Bar"]}
        want_dict = {"dependencies":["Foo"], "srcs":["Baz", "Bar"]}
        module_info_util._merge_module_keys(test_m_dict, test_b_dict)
        self.assertEqual(want_dict, test_m_dict)


    def test_merge_module_keys_with_duplicated_item_dict(self):
        """Test _merge_module_keys with with the key exists in the dictionary
        to be merged into."""
        test_b_dict = _TEST_CLASS_DICT
        test_m_dict = {"class":["JAVA_LIBRARIES"]}
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
        test_mk_dict = {"module_a":{"class":["JAVA_LIBRARIES"],
                                    "path":["path_a"],
                                    "installed":["out/path_a/a.jar"],
                                    "dependencies":["Foo"],
                                    "srcs":["Bar"]}}
        self.assertEqual(_TEST_MODULE_A_DICT,
                         module_info_util._copy_needed_items_from(test_mk_dict))


    def test_copy_needed_items_from_some_needed_items_dict(self):
        """Test _copy_needed_items_from a dictionary with some needed items."""
        test_mk_dict = {"module_a":{"class":["JAVA_LIBRARIES"],
                                    "path":["path_a"],
                                    "installed":["out/path_a/a.jar"],
                                    "dependencies":["Foo"],
                                    "srcs":["Bar"],
                                    "compatibility_suites": ["null-suite"],
                                    "module_name": ["ltp_fstat03_64"]}}
        self.assertEqual(_TEST_MODULE_A_DICT,
                         module_info_util._copy_needed_items_from(test_mk_dict))


if __name__ == '__main__':
    unittest.main()
