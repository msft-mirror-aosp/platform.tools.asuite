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

"""Unittests for native_util."""

import unittest
from unittest import mock

from aidegen.lib import common_util
from aidegen.lib import native_util


# pylint: disable=protected-access
# pylint: disable=invalid-name
class AidegenNativeUtilUnittests(unittest.TestCase):
    """Unit tests for native_util.py"""

    _MODULE_INFO = mock.MagicMock()
    _TARGETS = ['native_a', 'native_b']
    _JAVA_TARGETS = ['java_a', 'java_b']
    _ABS = 'abs_path'

    @mock.patch.object(native_util, '_generate_clion_projects_file')
    @mock.patch('os.path.isfile')
    def test_check_native_projects_file_not_exist(
            self, mock_is_file, mock_gen_clion):
        """Test check_native_projects when cmake files' list deosn't exist."""
        mock_is_file.return_value = False
        expected = [], set(self._TARGETS)
        self.assertEqual(
            expected, native_util.check_native_projects(
                self._MODULE_INFO, set(self._TARGETS)))
        self.assertTrue(mock_gen_clion.called)

    @mock.patch.object(native_util, '_separate_native_and_java_projects')
    @mock.patch.object(common_util, 'read_file_line_to_list')
    @mock.patch('os.path.isfile')
    def test_check_native_projects_file_exist(
            self, mock_is_file, mock_read_file, mock_sep):
        """Test check_native_projects when cmake files' list exists."""
        mock_is_file.return_value = True
        native_util.check_native_projects(self._MODULE_INFO, set(self._TARGETS))
        self.assertTrue(mock_read_file.called)
        self.assertTrue(mock_sep.called)

    @mock.patch.object(common_util, 'get_related_paths')
    def test_separate_native_and_java_projects_without_native(
            self, mock_get_related):
        """Test _separate_native_and_java_projects without native in targets."""
        mock_get_related.return_value = self._JAVA_TARGETS[0], self._ABS
        expected = [], self._JAVA_TARGETS
        self.assertEqual(
            expected, native_util._separate_native_and_java_projects(
                self._MODULE_INFO, self._JAVA_TARGETS, self._TARGETS))
        mock_get_related.return_value = self._JAVA_TARGETS[1], self._ABS
        self.assertEqual(
            expected, native_util._separate_native_and_java_projects(
                self._MODULE_INFO, self._JAVA_TARGETS, self._TARGETS))

    @mock.patch('os.path.relpath')
    @mock.patch.object(common_util, 'get_related_paths')
    def test_separate_native_and_java_projects_with_native(
            self, mock_get_related, mock_relpath):
        """Test _separate_native_and_java_projects with native in targets."""
        mock_get_related.return_value = self._TARGETS[0], self._ABS
        mock_relpath.return_value = self._ABS
        expected = [self._ABS], []
        self.assertEqual(
            expected, native_util._separate_native_and_java_projects(
                self._MODULE_INFO, [self._TARGETS[0]], self._TARGETS))
        mock_get_related.return_value = self._TARGETS[1], self._ABS
        mock_relpath.return_value = self._ABS
        expected = [self._ABS], []
        self.assertEqual(
            expected, native_util._separate_native_and_java_projects(
                self._MODULE_INFO, [self._TARGETS[1]], self._TARGETS))


if __name__ == '__main__':
    unittest.main()
