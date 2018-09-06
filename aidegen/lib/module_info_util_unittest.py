#!/usr/bin/env python
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

# pylint: disable=protected-access
# pylint: disable=invalid-name
class AidegenModuleInfoUtilUnittests(unittest.TestCase):
    """Unit tests for moduole_info_utils.py"""


    def test_merge_module_keys_with_empty_dict(self):
        """Test _merge_module_keys with an empty dictionary."""
        test_b_dict = {}
        test_m_dict = {"dependencies":["Foo"], "srcs":["Bar"]}
        want_dict = {"dependencies":["Foo"], "srcs":["Bar"]}
        module_info_util._merge_module_keys(test_m_dict, test_b_dict)
        self.assertEqual(want_dict, test_m_dict)


    def test_merge_module_keys_with_key_not_in_orginial_dict(self):
        """Test _merge_module_keys with the key does not exist in the dictionary
        to be merged into."""
        test_b_dict = {"srcs":["Bar"]}
        test_m_dict = {"dependencies":["Foo"]}
        want_dict = {"dependencies":["Foo"], "srcs":["Bar"]}
        module_info_util._merge_module_keys(test_m_dict, test_b_dict)
        self.assertEqual(want_dict, test_m_dict)


    def test_merge_module_keys_with_key_in_orginial_dict(self):
        """Test _merge_module_keys with with the key exists in the dictionary
        to be merged into."""
        test_b_dict = {"srcs":["Baz"]}
        test_m_dict = {"dependencies":["Foo"], "srcs":["Bar"]}
        want_dict = {"dependencies":["Foo"], "srcs":["Bar", "Baz"]}
        module_info_util._merge_module_keys(test_m_dict, test_b_dict)
        self.assertEqual(want_dict, test_m_dict)


if __name__ == '__main__':
    unittest.main()
