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

import logging
import os
import unittest
from unittest import mock

from aidegen import constant
from aidegen import unittest_constants
from aidegen.lib import common_util
from aidegen.lib import errors

from atest import module_info


# pylint: disable=too-many-arguments
# pylint: disable=protected-access
class AidegenCommonUtilUnittests(unittest.TestCase):
    """Unit tests for common_util.py"""

    @mock.patch.object(common_util, 'get_android_root_dir')
    @mock.patch.object(module_info.ModuleInfo, 'get_module_names')
    @mock.patch.object(module_info.ModuleInfo, 'get_paths')
    @mock.patch.object(module_info.ModuleInfo, 'is_module')
    def test_get_related_paths(self, mock_is_mod, mock_get, mock_names,
                               mock_get_root):
        """Test get_related_paths with different conditions."""
        mock_is_mod.return_value = True
        mock_get.return_value = []
        mod_info = module_info.ModuleInfo()
        self.assertEqual((None, None),
                         common_util.get_related_paths(
                             mod_info, unittest_constants.TEST_MODULE))
        mock_get_root.return_value = unittest_constants.TEST_PATH
        mock_get.return_value = [unittest_constants.TEST_MODULE]
        expected = (unittest_constants.TEST_MODULE, os.path.join(
            unittest_constants.TEST_PATH, unittest_constants.TEST_MODULE))
        self.assertEqual(
            expected, common_util.get_related_paths(
                mod_info, unittest_constants.TEST_MODULE))
        mock_is_mod.return_value = False
        mock_names.return_value = True
        self.assertEqual(expected, common_util.get_related_paths(
            mod_info, unittest_constants.TEST_MODULE))
        self.assertEqual(('', unittest_constants.TEST_PATH),
                         common_util.get_related_paths(
                             mod_info, constant.WHOLE_ANDROID_TREE_TARGET))

    @mock.patch('os.getcwd')
    @mock.patch.object(common_util, 'is_android_root')
    @mock.patch.object(common_util, 'get_android_root_dir')
    @mock.patch.object(module_info.ModuleInfo, 'get_module_names')
    @mock.patch.object(module_info.ModuleInfo, 'is_module')
    def test_get_related_paths_2(self, mock_is_mod, mock_names, mock_get_root,
                                 mock_is_root, mock_getcwd):
        """Test get_related_paths with different conditions."""
        mock_get_root.return_value = '/a'
        mod_info = module_info.ModuleInfo()

        # Test get_module_names returns False, user inputs a relative path of
        # current directory.
        mock_is_mod.return_value = False
        mock_names.return_value = False
        mock_getcwd.return_value = '/a/b/c'
        input_target = 'd'
        # expected tuple: (rel_path, abs_path)
        expected = ('b/c/d', '/a/b/c/d')
        result = common_util.get_related_paths(mod_info, input_target)
        self.assertEqual(expected, result)

        # Test user doesn't input target and current working directory is the
        # android root folder.
        mock_getcwd.return_value = '/a'
        mock_is_root.return_value = True
        expected = ('', '/a')
        result = common_util.get_related_paths(mod_info, target=None)
        self.assertEqual(expected, result)

        # Test user doesn't input target and current working directory is not
        # android root folder.
        mock_getcwd.return_value = '/a/b'
        mock_is_root.return_value = False
        expected = ('b', '/a/b')
        result = common_util.get_related_paths(mod_info, target=None)
        self.assertEqual(expected, result)

    @mock.patch.object(common_util, 'is_android_root')
    @mock.patch.object(common_util, 'get_related_paths')
    def test_is_target_android_root(self, mock_get_rel, mock_get_root):
        """Test is_target_android_root with different conditions."""
        mock_get_rel.return_value = None, unittest_constants.TEST_PATH
        mock_get_root.return_value = True
        self.assertTrue(
            common_util.is_target_android_root(
                module_info.ModuleInfo(), [unittest_constants.TEST_MODULE]))
        mock_get_rel.return_value = None, ''
        mock_get_root.return_value = False
        self.assertFalse(
            common_util.is_target_android_root(
                module_info.ModuleInfo(), [unittest_constants.TEST_MODULE]))

    @mock.patch.object(common_util, 'get_android_root_dir')
    @mock.patch.object(common_util, 'has_build_target')
    @mock.patch('os.path.isdir')
    @mock.patch.object(common_util, 'get_related_paths')
    def test_check_module(self, mock_get, mock_isdir, mock_has_target,
                          mock_get_root):
        """Test if _check_module raises errors with different conditions."""
        mod_info = module_info.ModuleInfo()
        mock_get.return_value = None, None
        with self.assertRaises(errors.FakeModuleError) as ctx:
            common_util.check_module(mod_info, unittest_constants.TEST_MODULE)
            expected = common_util.FAKE_MODULE_ERROR.format(
                unittest_constants.TEST_MODULE)
            self.assertEqual(expected, str(ctx.exception))
        mock_get_root.return_value = unittest_constants.TEST_PATH
        mock_get.return_value = None, unittest_constants.TEST_MODULE
        with self.assertRaises(errors.ProjectOutsideAndroidRootError) as ctx:
            common_util.check_module(mod_info, unittest_constants.TEST_MODULE)
            expected = common_util.OUTSIDE_ROOT_ERROR.format(
                unittest_constants.TEST_MODULE)
            self.assertEqual(expected, str(ctx.exception))
        mock_get.return_value = None, unittest_constants.TEST_PATH
        mock_isdir.return_value = False
        with self.assertRaises(errors.ProjectPathNotExistError) as ctx:
            common_util.check_module(mod_info, unittest_constants.TEST_MODULE)
            expected = common_util.PATH_NOT_EXISTS_ERROR.format(
                unittest_constants.TEST_MODULE)
            self.assertEqual(expected, str(ctx.exception))
        mock_isdir.return_value = True
        mock_has_target.return_value = False
        mock_get.return_value = None, os.path.join(unittest_constants.TEST_PATH,
                                                   'test.jar')
        with self.assertRaises(errors.NoModuleDefinedInModuleInfoError) as ctx:
            common_util.check_module(mod_info, unittest_constants.TEST_MODULE)
            expected = common_util.NO_MODULE_DEFINED_ERROR.format(
                unittest_constants.TEST_MODULE)
            self.assertEqual(expected, str(ctx.exception))
        self.assertFalse(common_util.check_module(mod_info, '', False))
        self.assertFalse(common_util.check_module(mod_info, 'nothing', False))

    @mock.patch.object(common_util, 'check_module')
    def test_check_modules(self, mock_check):
        """Test _check_modules with different module lists."""
        mod_info = module_info.ModuleInfo()
        common_util._check_modules(mod_info, [])
        self.assertEqual(mock_check.call_count, 0)
        common_util._check_modules(mod_info, ['module1', 'module2'])
        self.assertEqual(mock_check.call_count, 2)
        target = 'nothing'
        mock_check.return_value = False
        self.assertFalse(common_util._check_modules(mod_info, [target], False))

    @mock.patch.object(common_util, 'get_android_root_dir')
    def test_get_abs_path(self, mock_get_root):
        """Test get_abs_path handling."""
        mock_get_root.return_value = unittest_constants.TEST_DATA_PATH
        self.assertEqual(unittest_constants.TEST_DATA_PATH,
                         common_util.get_abs_path(''))
        test_path = os.path.join(unittest_constants.TEST_DATA_PATH, 'test.jar')
        self.assertEqual(test_path, common_util.get_abs_path(test_path))
        self.assertEqual(test_path, common_util.get_abs_path('test.jar'))

    def test_is_target(self):
        """Test is_target handling."""
        self.assertTrue(
            common_util.is_target('packages/apps/tests/test.a', ['.so', '.a']))
        self.assertTrue(
            common_util.is_target('packages/apps/tests/test.so', ['.so', '.a']))
        self.assertFalse(
            common_util.is_target(
                'packages/apps/tests/test.jar', ['.so', '.a']))

    @mock.patch.object(logging, 'basicConfig')
    def test_configure_logging(self, mock_log_config):
        """Test configure_logging with different arguments."""
        common_util.configure_logging(True)
        log_format = common_util._LOG_FORMAT
        datefmt = common_util._DATE_FORMAT
        level = common_util.logging.DEBUG
        self.assertTrue(
            mock_log_config.called_with(
                level=level, format=log_format, datefmt=datefmt))
        common_util.configure_logging(False)
        level = common_util.logging.INFO
        self.assertTrue(
            mock_log_config.called_with(
                level=level, format=log_format, datefmt=datefmt))

    @mock.patch.object(common_util, '_check_modules')
    @mock.patch.object(module_info, 'ModuleInfo')
    def test_get_atest_module_info(self, mock_modinfo, mock_check_modules):
        """Test get_atest_module_info handling."""
        common_util.get_atest_module_info()
        self.assertEqual(mock_modinfo.call_count, 1)
        mock_modinfo.reset_mock()
        mock_check_modules.return_value = False
        common_util.get_atest_module_info(['nothing'])
        self.assertEqual(mock_modinfo.call_count, 2)

    @mock.patch('builtins.open', create=True)
    def test_read_file_content(self, mock_open):
        """Test read_file_content handling."""
        expacted_data1 = 'Data1'
        file_a = 'fileA'
        mock_open.side_effect = [
            mock.mock_open(read_data=expacted_data1).return_value
        ]
        self.assertEqual(expacted_data1, common_util.read_file_content(file_a))
        mock_open.assert_called_once_with(file_a, encoding='utf8')

    @mock.patch('os.getenv')
    @mock.patch.object(common_util, 'get_android_root_dir')
    def test_get_android_out_dir(self, mock_get_android_root_dir, mock_getenv):
        """Test get_android_out_dir handling."""
        root = 'my/path-to-root/master'
        default_root = 'out'
        android_out_root = 'eng_out'
        mock_get_android_root_dir.return_value = root
        mock_getenv.side_effect = ['', '']
        self.assertEqual(default_root, common_util.get_android_out_dir())
        mock_getenv.side_effect = [android_out_root, '']
        self.assertEqual(android_out_root, common_util.get_android_out_dir())
        mock_getenv.side_effect = ['', default_root]
        self.assertEqual(os.path.join(default_root, os.path.basename(root)),
                         common_util.get_android_out_dir())
        mock_getenv.side_effect = [android_out_root, default_root]
        self.assertEqual(android_out_root, common_util.get_android_out_dir())

    def test_has_build_target(self):
        """Test has_build_target handling."""
        mod_info = module_info.ModuleInfo()
        mod_info.path_to_module_info = ['a/b/c']
        rel_path = 'a/b'
        self.assertTrue(common_util.has_build_target(mod_info, rel_path))
        rel_path = 'd/e'
        self.assertFalse(common_util.has_build_target(mod_info, rel_path))


if __name__ == '__main__':
    unittest.main()
