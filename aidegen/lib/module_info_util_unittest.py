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
import os.path
import unittest
from unittest import mock

from aidegen import unittest_constants
from aidegen.lib import common_util
from aidegen.lib import errors
from aidegen.lib import module_info_util

from atest import atest_utils

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
        'srcs': ['Bar'],
        'compatibility_suites': ['null-suite'],
        'module_name': ['ltp_fstat03_64']
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

    @mock.patch.object(os.path, 'getmtime')
    @mock.patch.object(atest_utils, 'build')
    @mock.patch('os.path.isfile')
    def test_build_bp_info_normal(self, mock_isfile, mock_build, mock_time):
        """Test _build_target with verbose true and false."""
        amodule_info = mock.MagicMock()
        skip = True
        mock_isfile.return_value = True
        mock_build.return_value = True
        module_info_util._build_bp_info(amodule_info, unittest_constants.
                                        TEST_MODULE, False, skip)
        self.assertFalse(mock_build.called)
        skip = False
        mock_time.return_value = float()
        module_info_util._build_bp_info(amodule_info, unittest_constants.
                                        TEST_MODULE, False, skip)
        self.assertTrue(mock_time.called)
        self.assertEqual(mock_build.call_count, 2)

    @mock.patch('os.path.getmtime')
    @mock.patch('os.path.isfile')
    def test_is_new_json_file_generated(self, mock_isfile, mock_getmtime):
        """Test _is_new_json_file_generated with different situations."""
        jfile = 'path/test.json'
        mock_isfile.return_value = True
        self.assertEqual(
            mock_isfile.return_value,
            module_info_util._is_new_json_file_generated(jfile, None))
        mock_isfile.return_value = False
        self.assertEqual(
            mock_isfile.return_value,
            module_info_util._is_new_json_file_generated(jfile, None))
        original_file_mtime = 1000
        mock_getmtime.return_value = original_file_mtime
        self.assertEqual(
            False,
            module_info_util._is_new_json_file_generated(
                jfile, original_file_mtime))
        mock_getmtime.return_value = 1001
        self.assertEqual(
            True,
            module_info_util._is_new_json_file_generated(
                jfile, original_file_mtime))

    @mock.patch('builtins.input')
    @mock.patch('glob.glob')
    def test_build_failed_handle(self, mock_glob, mock_input):
        """Test _build_failed_handle with different situations."""
        mock_glob.return_value = ['project/file.iml']
        mock_input.return_value = 'N'
        with self.assertRaises(SystemExit) as cm:
            module_info_util._build_failed_handle(
                unittest_constants.TEST_MODULE)
        self.assertEqual(cm.exception.code, 1)
        mock_glob.return_value = []
        with self.assertRaises(errors.BuildFailureError):
            module_info_util._build_failed_handle(
                unittest_constants.TEST_MODULE)

    @mock.patch('builtins.open')
    def test_get_soong_build_json_dict_failed(self, mock_open):
        """Test _get_soong_build_json_dict failure and raise error."""
        mock_open.side_effect = IOError
        with self.assertRaises(errors.JsonFileNotExistError):
            module_info_util._get_soong_build_json_dict()

    @mock.patch('aidegen.lib.module_info_util._build_failed_handle')
    @mock.patch.object(common_util, 'get_related_paths')
    @mock.patch('aidegen.lib.module_info_util._is_new_json_file_generated')
    @mock.patch.object(atest_utils, 'build')
    def test_build_bp_info(self, mock_build, mock_new, mock_path, mock_handle):
        """Test _build_bp_info with different arguments."""
        main_project = 'Settings'
        amodule_info = {}
        verbose = False
        mock_build.return_value = False
        mock_new.return_value = False
        module_info_util._build_bp_info(amodule_info, main_project, verbose)
        self.assertTrue(mock_new.called)
        self.assertFalse(mock_handle.called)
        mock_new.return_value = True
        mock_path.return_value = None, 'packages/apps/Settings'
        module_info_util._build_bp_info(amodule_info, main_project, verbose)
        self.assertTrue(mock_new.called)
        self.assertTrue(mock_handle.called)


if __name__ == '__main__':
    unittest.main()
