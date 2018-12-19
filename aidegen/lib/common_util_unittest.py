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

"""Unittests for common_util."""

import unittest

from aidegen.lib import common_util
from atest import module_info


# pylint: disable=invalid-name
class AidegenModuleInfoUtilUnittests(unittest.TestCase):
    """Unit tests for common_utils.py"""

    def test_get_related_paths_with_fake_module(self):
        """Test get_related_paths with a fake module."""
        self.assertEqual((None, None),
                         common_util.get_related_paths(module_info.ModuleInfo(),
                                                       'com.android.runtime'))


if __name__ == '__main__':
    unittest.main()
