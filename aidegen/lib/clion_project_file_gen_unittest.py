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

import os
import unittest
from unittest import mock

from io import StringIO

from aidegen import constant
from aidegen import templates
from aidegen.lib import clion_project_file_gen
from aidegen.lib import common_util
from aidegen.lib import errors


# pylint: disable=protected-access
class ClionProjectFileGenUnittests(unittest.TestCase):
    """Unit tests for clion_project_file_gen.py."""

    _FLAG_LIST = ['a', 'b']
    _FLAG_DICT = {clion_project_file_gen._KEY_FLAG: _FLAG_LIST}
    _MOD_INFO = {clion_project_file_gen._KEY_GLOBAL_COMMON_FLAGS: _FLAG_DICT}
    _MOD_PATH = 'path_to_mod'
    _PATH_DICT = {'path': [_MOD_PATH]}
    _MOD_NAME = 'M'
    _MOD_NAME_DICT = {'module_name': _MOD_NAME}
    _ROOT_DIR = 'path_to_root'
    _SRC_PATH = 'path_to_src'
    _SRC_DICT = {constant.KEY_SRCS: [_SRC_PATH]}

    def test_init_without_mod_info(self):
        """Test __init__ without mod_info."""
        with self.assertRaises(errors.ModuleInfoEmptyError):
            clion_project_file_gen.CLionProjectFileGenerator({})

    def test_init_with_mod_info_without_mod_name(self):
        """Test __init__ without mod_info."""
        mod_info = dict(self._MOD_INFO)
        mod_info.update(self._PATH_DICT)
        with self.assertRaises(errors.NoModuleNameDefinedInModuleInfoError):
            clion_project_file_gen.CLionProjectFileGenerator(mod_info)

    def test_init_with_mod_info_without_mod_path(self):
        """Test __init__ without mod_info."""
        mod_info = dict(self._MOD_INFO)
        mod_info.update(self._MOD_NAME_DICT)
        with self.assertRaises(errors.NoPathDefinedInModuleInfoError):
            clion_project_file_gen.CLionProjectFileGenerator(mod_info)

    @mock.patch('os.path.exists')
    def test_write_header(self, mock_exists):
        """Test _write_header function."""
        hfile = StringIO()
        mock_exists.return_value = True
        mod_info = dict(self._MOD_INFO)
        mod_info.update(self._PATH_DICT)
        mod_info.update(self._MOD_NAME_DICT)
        clion_gen = clion_project_file_gen.CLionProjectFileGenerator(mod_info)
        clion_gen._write_header(hfile)
        hfile.seek(0)
        content = hfile.read()
        expected = templates.CMAKELISTS_HEADER.replace(
            clion_project_file_gen._MIN_VERSION_TOKEN,
            clion_project_file_gen._MINI_VERSION)
        expected = expected.replace(
            clion_project_file_gen._PROJECT_NAME_TOKEN, clion_gen.mod_name)
        expected = expected.replace(
            clion_project_file_gen._ANDOIR_ROOT_TOKEN,
            common_util.get_android_root_dir())
        self.assertEqual(content, expected)

    @mock.patch('os.path.exists')
    def test_write_source_files_without_content(self, mock_exists):
        """Test _write_source_files function without content."""
        hfile = StringIO()
        mock_exists.return_value = True
        mod_info = dict(self._MOD_INFO)
        mod_info.update(self._PATH_DICT)
        mod_info.update(self._MOD_NAME_DICT)
        clion_gen = clion_project_file_gen.CLionProjectFileGenerator(mod_info)
        clion_gen._write_source_files(hfile)
        hfile.seek(0)
        content = hfile.read()
        expected = ''
        self.assertEqual(content, expected)

    def test_write_source_files_with_content(self):
        """Test _write_source_files function with content."""
        hfile = StringIO()
        mod_info = dict(self._MOD_INFO)
        mod_info.update(self._PATH_DICT)
        mod_info.update(self._MOD_NAME_DICT)
        mod_info.update(self._SRC_DICT)
        clion_gen = clion_project_file_gen.CLionProjectFileGenerator(mod_info)
        clion_gen._write_source_files(hfile)
        hfile.seek(0)
        content = hfile.read()
        srcs = clion_project_file_gen._build_cmake_path(self._SRC_PATH, '    ')
        header = clion_project_file_gen._LIST_APPEND_HEADER
        src_heads = ['     ', clion_project_file_gen._SOURCE_FILES_HEADER, '\n']
        tail = ')\n'
        expected = header + ''.join(src_heads) + srcs + '\n' + tail
        self.assertEqual(content, expected)

    def test_write_flags_without_content(self):
        """Test _write_flags function without content."""
        hfile = StringIO()
        mod_info = dict(self._PATH_DICT)
        mod_info.update(self._MOD_NAME_DICT)
        key = clion_project_file_gen._KEY_GLOBAL_COMMON_FLAGS
        clion_gen = clion_project_file_gen.CLionProjectFileGenerator(mod_info)
        clion_gen._write_flags(hfile, key, True, True)
        hfile.seek(0)
        content = hfile.read()
        expected = clion_project_file_gen._FLAGS_DICT.get(key, '')
        self.assertEqual(content, expected)

    def test_parse_compiler_parameters_with_flag(self):
        """Test _parse_compiler_parameters function with flag."""
        mod_info = dict(self._MOD_INFO)
        mod_info.update(self._PATH_DICT)
        mod_info.update(self._MOD_NAME_DICT)
        expected = {
            clion_project_file_gen._KEY_HEADER: [],
            clion_project_file_gen._KEY_SYSTEM: [],
            clion_project_file_gen._KEY_FLAG: self._FLAG_LIST,
            clion_project_file_gen._KEY_SYSTEM_ROOT: '',
            clion_project_file_gen._KEY_RELATIVE: {}
        }
        clion_gen = clion_project_file_gen.CLionProjectFileGenerator(mod_info)
        flag = clion_project_file_gen._KEY_GLOBAL_COMMON_FLAGS
        ret = clion_gen._parse_compiler_parameters(flag)
        self.assertEqual(ret, expected)

    @mock.patch.object(clion_project_file_gen, '_write_all_flags')
    @mock.patch.object(clion_project_file_gen,
                       '_write_all_relative_file_path_flags')
    @mock.patch.object(clion_project_file_gen, '_write_all_include_directories')
    def test_translate_to_cmake_with_empty_dict(
            self, mock_write_all_inc, mock_write_rel, mock_write_all_flags):
        """Test _translate_to_cmake function with empty dictionary."""
        hfile = StringIO()
        params_dict = {
            clion_project_file_gen._KEY_HEADER: [],
            clion_project_file_gen._KEY_SYSTEM: [],
            clion_project_file_gen._KEY_FLAG: [],
            clion_project_file_gen._KEY_SYSTEM_ROOT: '',
            clion_project_file_gen._KEY_RELATIVE: {}
        }
        clion_project_file_gen._translate_to_cmake(hfile, params_dict, True,
                                                   True)
        hfile.seek(0)
        content = hfile.read()
        self.assertEqual(content, '')
        self.assertTrue(mock_write_all_inc.call_count, 2)
        self.assertTrue(mock_write_rel, 2)
        self.assertTrue(mock_write_all_flags, 2)

    @mock.patch.object(clion_project_file_gen, '_write_all_flags')
    @mock.patch.object(clion_project_file_gen,
                       '_write_all_relative_file_path_flags')
    @mock.patch.object(clion_project_file_gen, '_write_all_include_directories')
    def test_translate_to_cmake_with_system_root_info(
            self, mock_write_all_inc, mock_write_rel, mock_write_all_flags):
        """Test _translate_to_cmake function with empty dictionary."""
        hfile = StringIO()
        root = 'path_to_root'
        params_dict = {
            clion_project_file_gen._KEY_HEADER: [],
            clion_project_file_gen._KEY_SYSTEM: [],
            clion_project_file_gen._KEY_FLAG: [],
            clion_project_file_gen._KEY_SYSTEM_ROOT: root,
            clion_project_file_gen._KEY_RELATIVE: {}
        }
        clion_project_file_gen._translate_to_cmake(hfile, params_dict, True,
                                                   False)
        hfile.seek(0)
        content = hfile.read()
        path = os.path.join(
            root, clion_project_file_gen._USR, clion_project_file_gen._INCLUDE)
        expected = clion_project_file_gen._INCLUDE_SYSTEM.format(
            clion_project_file_gen._build_cmake_path(path))
        self.assertEqual(content, expected)
        self.assertTrue(mock_write_all_inc.call_count, 2)
        self.assertTrue(mock_write_rel, 1)
        self.assertTrue(mock_write_all_flags, 1)

    def test_write_all_relative_flags_without_content(self):
        """Test _write_all_relative_file_path_flags function without content."""
        hfile = StringIO()
        clion_project_file_gen._write_all_relative_file_path_flags(
            hfile, {}, '')
        hfile.seek(0)
        content = hfile.read()
        self.assertEqual(content, '')

    def test_write_all_relative_flags_with_content(self):
        """Test _write_all_relative_file_path_flags function with content."""
        hfile = StringIO()
        flag = 'flag'
        path = 'path_to_rel'
        tag = '_CMAKE_C_FLAGS'
        clion_project_file_gen._write_all_relative_file_path_flags(
            hfile, {flag: path}, tag)
        hfile.seek(0)
        content = hfile.read()
        expected = clion_project_file_gen._SET_RELATIVE_PATH.format(
            tag, clion_project_file_gen._add_dollar_sign(tag), flag,
            clion_project_file_gen._build_cmake_path(path))
        self.assertEqual(content, expected)

    def test_add_dollar_sign(self):
        """Test _add_dollar_sign function."""
        param = 'ANDROID'
        expected = '${ANDROID}'
        result = clion_project_file_gen._add_dollar_sign(param)
        self.assertEqual(expected, result)

    def test_write_all_flags_without_content(self):
        """Test _write_all_flags function without content."""
        hfile = StringIO()
        clion_project_file_gen._write_all_flags(hfile, [], '')
        hfile.seek(0)
        content = hfile.read()
        self.assertEqual(content, '')

    def test_write_all_flags_with_content(self):
        """Test _write_all_flags function with content."""
        hfile = StringIO()
        flag = 'flag'
        tag = '_CMAKE_C_FLAGS'
        clion_project_file_gen._write_all_flags(hfile, [flag], tag)
        hfile.seek(0)
        content = hfile.read()
        expected = clion_project_file_gen._SET_ALL_FLAGS.format(
            tag, clion_project_file_gen._add_dollar_sign(tag), flag)
        self.assertEqual(content, expected)

    def test_build_cmake_path_without_tag(self):
        """Test _build_cmake_path function without tag."""
        param = 'prebuilts/clang/host/linux-x86/clang-r370808/bin/clang'
        expected = ('${ANDROID_ROOT}/prebuilts/clang/host/linux-x86/'
                    'clang-r370808/bin/clang')
        result = clion_project_file_gen._build_cmake_path(param)
        self.assertEqual(expected, result)

    def test_build_cmake_path_with_tag(self):
        """Test _build_cmake_path function with tag."""
        param = 'prebuilts/clang/host/linux-x86/clang-r370808/bin/clang'
        tag = '    '
        expected = ('    ${ANDROID_ROOT}/prebuilts/clang/host/linux-x86/'
                    'clang-r370808/bin/clang')
        result = clion_project_file_gen._build_cmake_path(param, tag)
        self.assertEqual(expected, result)

    def test_write_all_includes_without_content(self):
        """Test _write_all_includes function without content."""
        hfile = StringIO()
        clion_project_file_gen._write_all_includes(hfile, [], True)
        hfile.seek(0)
        content = hfile.read()
        self.assertEqual(content, '')
        clion_project_file_gen._write_all_includes(hfile, [], False)
        hfile.seek(0)
        content = hfile.read()
        self.assertEqual(content, '')

    def test_write_all_headers_without_content(self):
        """Test _write_all_headers function without content."""
        hfile = StringIO()
        clion_project_file_gen._write_all_headers(hfile, [])
        hfile.seek(0)
        content = hfile.read()
        self.assertEqual(content, '')

    def test_write_all_headers_with_content(self):
        """Test _write_all_headers function with content."""
        hfile = StringIO()
        include = 'path_to_include'
        clion_project_file_gen._write_all_headers(hfile, [include])
        hfile.seek(0)
        content = hfile.read()
        head = clion_project_file_gen._GLOB_RECURSE_TMP_HEADERS
        middle = clion_project_file_gen._ALL_HEADER_FILES.format(
            clion_project_file_gen._build_cmake_path(include))
        tail1 = clion_project_file_gen._END_WITH_ONE_BLANK_LINE
        tail2 = clion_project_file_gen._APPEND_SOURCE_FILES
        expected = head + middle + tail1 + tail2
        self.assertEqual(content, expected)

    def test_write_all_includes_with_content(self):
        """Test _write_all_includes function with content."""
        hfile = StringIO()
        include = 'path_to_include'
        clion_project_file_gen._write_all_includes(hfile, [include], True)
        hfile.seek(0)
        content = hfile.read()
        system = clion_project_file_gen._SYSTEM
        head = clion_project_file_gen._INCLUDE_DIR.format(system)
        middle = clion_project_file_gen._SET_INCLUDE_FORMAT.format(
            clion_project_file_gen._build_cmake_path(include))
        tail = clion_project_file_gen._END_WITH_TWO_BLANK_LINES
        expected = head + middle + tail
        self.assertEqual(content, expected)
        hfile = StringIO()
        clion_project_file_gen._write_all_includes(hfile, [include], False)
        hfile.seek(0)
        content = hfile.read()
        head = clion_project_file_gen._INCLUDE_DIR.format('')
        expected = head + middle + tail
        self.assertEqual(content, expected)


if __name__ == '__main__':
    unittest.main()
