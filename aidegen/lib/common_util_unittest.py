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

import os
import unittest
from unittest import mock

import aidegen.unittest_constants as uc
from aidegen import constant
from aidegen.lib import common_util
from atest import module_info


# pylint: disable=invalid-name
class AidegenCommonUtilUnittests(unittest.TestCase):
    """Unit tests for common_utils.py"""

    @mock.patch.object(module_info.ModuleInfo, 'get_module_names')
    @mock.patch.object(module_info.ModuleInfo, 'get_paths')
    @mock.patch.object(module_info.ModuleInfo, 'is_module')
    def test_get_related_paths(self, mock_is_mod, mock_get, mock_names):
        """Test get_related_paths with different conditions."""
        mock_is_mod.return_value = True
        mock_get.return_value = []
        mod_info = module_info.ModuleInfo()
        self.assertEqual((None, None),
                         common_util.get_related_paths(mod_info,
                                                       uc.TEST_MODULE))
        constant.ANDROID_ROOT_PATH = uc.TEST_PATH
        mock_get.return_value = [uc.TEST_MODULE]
        expected = (uc.TEST_MODULE, os.path.join(uc.TEST_PATH, uc.TEST_MODULE))
        self.assertEqual(
            expected,
            common_util.get_related_paths(mod_info, uc.TEST_MODULE))
        mock_is_mod.return_value = False
        mock_names.return_value = True
        self.assertEqual(
            expected,
            common_util.get_related_paths(mod_info, uc.TEST_MODULE))

    @mock.patch.object(common_util, 'get_related_paths')
    def test_is_target_android_root(self, mock_get):
        """Test is_target_android_root with different conditions."""
        mock_get.return_value = None, uc.TEST_PATH
        self.assertTrue(
            common_util.is_target_android_root(module_info.ModuleInfo(),
                                               [uc.TEST_MODULE]))
        mock_get.return_value = None, ''
        self.assertFalse(
            common_util.is_target_android_root(module_info.ModuleInfo(),
                                               [uc.TEST_MODULE]))


if __name__ == '__main__':
    unittest.main()
