#!/usr/bin/env python3
#
# Copyright 2019 - The Android Open Source Project
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


"""Unittests for clion_project_file_gen."""

import unittest

from aidegen.lib import clion_project_file_gen


# pylint: disable=protected-access
class ClionProjectFileGenUnittests(unittest.TestCase):
    """Unit tests for clion_project_file_gen.py."""

    def test_add_dollar_sign(self):
        """Test _add_dollar_sign function."""
        param = 'ANDROID'
        expected = '${ANDROID}'
        result = clion_project_file_gen._add_dollar_sign(param)
        self.assertEqual(expected, result)

    def test_build_cmake_path(self):
        """Test _build_cmake_path function."""
        param = 'prebuilts/clang/host/linux-x86/clang-r370808/bin/clang'
        expected = ('${ANDROID_ROOT}/prebuilts/clang/host/linux-x86/'
                    'clang-r370808/bin/clang')
        result = clion_project_file_gen._build_cmake_path(param)
        self.assertEqual(expected, result)
        tag = '    '
        expected = ('    ${ANDROID_ROOT}/prebuilts/clang/host/linux-x86/'
                    'clang-r370808/bin/clang')
        result = clion_project_file_gen._build_cmake_path(param, tag)
        self.assertEqual(expected, result)


if __name__ == '__main__':
    unittest.main()
