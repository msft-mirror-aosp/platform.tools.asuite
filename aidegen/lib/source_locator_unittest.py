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

"""Unittests for source_locator."""

import os
import unittest

from aidegen import constants
from aidegen.lib import source_locator

_MODULE_NAME = 'test'
_MODULE_PATH = 'packages/apps/test'
_MODULE_INFO = {'path': [_MODULE_PATH],
                'srcs': ['src/main/java/com/android/test.java',
                         ':test_filegroup',
                         'test/**/*.java'],
                'installed': []
               }
_TEST_DATA_PATH = os.path.join(constants.ROOT_DIR, 'test_data')

# pylint: disable=protected-access
# pylint: disable=invalid-name
class SourceLocatorUnittests(unittest.TestCase):
    """Unit tests for source_locator.py"""

    def test_collect_srcs_paths(self):
        """Test _collect_srcs_paths create the source path list."""
        result_source = [os.path.join(_MODULE_PATH, 'src/main/java'),
                         os.path.join(_MODULE_PATH, 'test')]
        module_data = source_locator.ModuleData(_TEST_DATA_PATH, _MODULE_NAME,
                                                _MODULE_INFO)
        module_data._collect_srcs_paths()
        self.assertEqual(module_data.src_dirs, result_source)

    def test_check_special_files(self):
        """Test _check_special_files for setting certain flag."""
        module_info = dict(_MODULE_INFO)
        module_info['srcs'].extend(['src/main/java/com/android/test.aidl',
                                    'src/main/java/com/android/test.logtags'])
        module_data = source_locator.ModuleData(_TEST_DATA_PATH, _MODULE_NAME,
                                                module_info)
        module_data._check_special_files()
        self.assertEqual(module_data.aidl_existed, True)
        self.assertEqual(module_data.logtags_existed, True)
        self.assertEqual(module_data.filegroup_existed, True)

    def test_get_source_folder(self):
        """Test _get_source_folder process."""
        # Test for getting the source path by parse package name from a java.
        test_java = 'src/main/java/com/android/test.java'
        result_source = 'src/main/java'
        module_data = source_locator.ModuleData(_TEST_DATA_PATH, _MODULE_NAME,
                                                _MODULE_INFO)
        src_path = module_data._get_source_folder(test_java)
        self.assertEqual(src_path, result_source)

        # Return path is None if the java file doesn't exist.
        test_java = 'file_not_exist.java'
        src_path = module_data._get_source_folder(test_java)
        self.assertEqual(src_path, None)

        # Return path is None on the java file without package name.
        test_java = 'src/main/java/com/android/wrong_package.java'
        src_path = module_data._get_source_folder(test_java)
        self.assertEqual(src_path, None)

    def test_append_jar_file(self):
        """Test _append_jar_file process."""
        # Append an existing jar file path to module_data.jar_files.
        test_jar_file = os.path.join(_MODULE_PATH, 'test.jar')
        result_jar_list = [test_jar_file]
        module_data = source_locator.ModuleData(_TEST_DATA_PATH, _MODULE_NAME,
                                                _MODULE_INFO)
        module_data._append_jar_file(test_jar_file)
        self.assertEqual(module_data.jar_files, result_jar_list)

        # Skip if the jar file doesn't exist.
        test_jar_file = os.path.join(_MODULE_PATH, 'jar_not_exist.jar')
        module_data.jar_files = []
        module_data._append_jar_file(test_jar_file)
        self.assertEqual(module_data.jar_files, [])

        # Skip if it's not a jar file.
        test_jar_file = os.path.join(_MODULE_PATH, 'test.java')
        module_data.jar_files = []
        module_data._append_jar_file(test_jar_file)
        self.assertEqual(module_data.jar_files, [])

    def test_append_src_dir(self):
        """Test _append_src_dir process ."""
        # Append an existing source path to module_data.src_dirs.
        test_folder = os.path.join(_MODULE_PATH, 'src/main/java')
        result_src_dir = [test_folder]
        module_data = source_locator.ModuleData(_TEST_DATA_PATH, _MODULE_NAME,
                                                _MODULE_INFO)
        module_data._append_src_dir(test_folder)
        self.assertEqual(module_data.src_dirs, result_src_dir)

        # Skip if the folder doesn't exist.
        test_folder = os.path.join(_MODULE_PATH, 'dir_not_exist')
        module_data.src_dirs = []
        module_data._append_src_dir(test_folder)
        self.assertEqual(module_data.src_dirs, [])

    def test_append_jar_from_installed(self):
        """Test _append_jar_from_installed handling."""
        # Test appends the first jar file of 'installed'.
        module_info = dict(_MODULE_INFO)
        module_info['installed'] = [
            os.path.join(_MODULE_PATH, 'test.aar'),
            os.path.join(_MODULE_PATH, 'test.jar'),
            os.path.join(_MODULE_PATH, 'test/test_second.jar')]
        result_jar_list = [os.path.join(_MODULE_PATH, 'test.jar')]
        module_data = source_locator.ModuleData(_TEST_DATA_PATH, _MODULE_NAME,
                                                module_info)
        module_data._append_jar_from_installed()
        self.assertEqual(module_data.jar_files, result_jar_list)

        # Test on the jar file path matches the path prefix.
        module_data.jar_files = []
        result_jar_list = [os.path.join(_MODULE_PATH, 'test/test_second.jar')]
        module_data._append_jar_from_installed(
            os.path.join(_MODULE_PATH, 'test/'))
        self.assertEqual(module_data.jar_files, result_jar_list)

    def test_set_jars_jarfile(self):
        """Test _set_jars_jarfile handling."""
        # Combine the module path with jar file name in 'jars' and then append
        # it to module_data.jar_files.
        module_info = dict(_MODULE_INFO)
        module_info['jars'] = [
            'test.jar',
            'src/test.jar', # This jar file doesn't exist.
            'test/test_second.jar']
        result_jar_list = [
            os.path.join(_MODULE_PATH, 'test.jar'),
            os.path.join(_MODULE_PATH, 'test/test_second.jar')]
        module_data = source_locator.ModuleData(_TEST_DATA_PATH, _MODULE_NAME,
                                                module_info)
        module_data._set_jars_jarfile()
        self.assertEqual(module_data.jar_files, result_jar_list)

    def test_locate_sources_path(self):
        """Test locate_sources_path handling."""
        # Test collect source path.
        module_info = dict(_MODULE_INFO)
        module_info['srcs'].extend(['src/main/java/com/android/test.aidl',
                                    'src/main/java/com/android/test.logtags'])
        result_src_list = [
            os.path.join(_MODULE_PATH, 'src/main/java'),
            os.path.join(_MODULE_PATH, 'test'),
            'out/target/common/obj/JAVA_LIBRARIES/test_intermediates/aidl',
            'out/target/common/obj/JAVA_LIBRARIES/test_intermediates/logtags']
        result_jar_list = []
        module_data = source_locator.ModuleData(_TEST_DATA_PATH, _MODULE_NAME,
                                                module_info)
        module_data.locate_sources_path()
        self.assertEqual(module_data.src_dirs, result_src_list)
        self.assertEqual(module_data.jar_files, result_jar_list)

        # Test find jar files.
        jar_file = ('out/soong/.intermediates/packages/apps/test/test/'
                    'android_common/test.jar')
        module_info['jarjar_rules'] = ['jarjar-rules.txt']
        module_info['installed'] = [jar_file]
        result_src_list = []
        result_jar_list = [jar_file]
        module_data = source_locator.ModuleData(_TEST_DATA_PATH, _MODULE_NAME,
                                                module_info)
        module_data.locate_sources_path()
        self.assertEqual(module_data.src_dirs, result_src_list)
        self.assertEqual(module_data.jar_files, result_jar_list)


if __name__ == '__main__':
    unittest.main()
