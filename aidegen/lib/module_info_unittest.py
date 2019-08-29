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

"""Unittests for module_info."""

import unittest

from aidegen.lib import module_info


class AidegenModuleInfoUnittests(unittest.TestCase):
    """Unit tests for module_info.py"""

    def test_is_target_module(self):
        """Test is_target_module with different conditions."""
        self.assertFalse(module_info.AidegenModuleInfo.is_target_module({}))
        self.assertFalse(module_info.AidegenModuleInfo.is_target_module(
            {'path': ''}))
        self.assertFalse(module_info.AidegenModuleInfo.is_target_module(
            {'class': ''}))
        self.assertTrue(module_info.AidegenModuleInfo.is_target_module(
            {'class': ['APPS']}))
        self.assertTrue(
            module_info.AidegenModuleInfo.is_target_module(
                {'class': ['JAVA_LIBRARIES']}))
        self.assertTrue(
            module_info.AidegenModuleInfo.is_target_module(
                {'class': ['ROBOLECTRIC']}))


if __name__ == '__main__':
    unittest.main()
