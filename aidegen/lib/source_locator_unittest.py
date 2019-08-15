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
import shutil
import tempfile
import unittest
from unittest import mock

from aidegen import constant
from aidegen import unittest_constants
from aidegen.lib import source_locator

_MODULE_NAME = 'test'
_MODULE_PATH = 'packages/apps/test'
_MODULE_INFO = {
    'path': [_MODULE_PATH],
    'srcs': [
        'packages/apps/test/src/main/java/com/android/java.java',
        'packages/apps/test/tests/com/android/test.java',
        'packages/apps/test/tests/test.srcjar'
    ],
    'dependencies': [],
    'installed': []
}
_MODULE_DEPTH = 0


# pylint: disable=protected-access
# pylint: disable=invalid-name
class SourceLocatorUnittests(unittest.TestCase):
    """Unit tests for source_locator.py"""

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    def test_collect_srcs_paths(self, mock_android_root_dir):
        """Test _collect_srcs_paths create the source path list."""
        result_source = set(['packages/apps/test/src/main/java'])
        result_test = set(['packages/apps/test/tests'])
        mock_android_root_dir.return_value = unittest_constants.TEST_DATA_PATH
        module_data = source_locator.ModuleData(_MODULE_NAME, _MODULE_INFO,
                                                _MODULE_DEPTH)
        module_data._collect_srcs_paths()
        self.assertEqual(module_data.src_dirs, result_source)
        self.assertEqual(module_data.test_dirs, result_test)

    def test_get_package_name(self):
        """test get the package name from a java file."""
        result_package_name = 'com.android'
        test_java = os.path.join(unittest_constants.TEST_DATA_PATH,
                                 _MODULE_PATH,
                                 'src/main/java/com/android/java.java')
        package_name = source_locator.ModuleData._get_package_name(test_java)
        self.assertEqual(package_name, result_package_name)

        # Test on java file with no package name.
        result_package_name = None
        test_java = os.path.join(unittest_constants.TEST_DATA_PATH,
                                 _MODULE_PATH,
                                 'src/main/java/com/android/no_package.java')
        package_name = source_locator.ModuleData._get_package_name(test_java)
        self.assertEqual(package_name, result_package_name)

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    def test_get_source_folder(self, mock_android_root_dir):
        """Test _get_source_folder process."""
        # Test for getting the source path by parse package name from a java.
        test_java = 'packages/apps/test/src/main/java/com/android/java.java'
        result_source = 'packages/apps/test/src/main/java'
        mock_android_root_dir.return_value = unittest_constants.TEST_DATA_PATH
        module_data = source_locator.ModuleData(_MODULE_NAME, _MODULE_INFO,
                                                _MODULE_DEPTH)
        src_path = module_data._get_source_folder(test_java)
        self.assertEqual(src_path, result_source)

        # Return path is None if the java file doesn't exist.
        test_java = 'file_not_exist.java'
        src_path = module_data._get_source_folder(test_java)
        self.assertEqual(src_path, None)

        # Return path is None on the java file without package name.
        test_java = ('packages/apps/test/src/main/java/com/android/'
                     'no_package.java')
        src_path = module_data._get_source_folder(test_java)
        self.assertEqual(src_path, None)

    def test_get_r_dir(self):
        """Test get_r_dir."""
        module_data = source_locator.ModuleData(_MODULE_NAME, _MODULE_INFO,
                                                _MODULE_DEPTH)
        # Test for aapt2.srcjar
        test_aapt2_srcjar = 'a/aapt2.srcjar'
        expect_result = 'a/aapt2'
        r_dir = module_data._get_r_dir(test_aapt2_srcjar)
        self.assertEqual(r_dir, expect_result)

        # Test for R.jar
        test_r_jar = 'b/R.jar'
        expect_result = 'b/aapt2/R'
        r_dir = module_data._get_r_dir(test_r_jar)
        self.assertEqual(r_dir, expect_result)

        # Test for the target file is not aapt2.srcjar or R.jar
        test_unknown_target = 'c/proto.srcjar'
        expect_result = None
        r_dir = module_data._get_r_dir(test_unknown_target)
        self.assertEqual(r_dir, expect_result)

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    def test_collect_r_src_path(self, mock_android_root_dir):
        """Test collect_r_src_path."""
        # Test on target srcjar exists in srcjars.
        test_module = dict(_MODULE_INFO)
        test_module['srcs'] = []
        mock_android_root_dir.return_value = unittest_constants.TEST_DATA_PATH
        module_data = source_locator.ModuleData(_MODULE_NAME, test_module,
                                                _MODULE_DEPTH)
        # Test the module is not APPS.
        module_data._collect_r_srcs_paths()
        expect_result = set()
        self.assertEqual(module_data.r_java_paths, expect_result)

        # Test the module is not a target module.
        test_module['depth'] = 1
        module_data = source_locator.ModuleData(_MODULE_NAME, test_module, 1)
        module_data._collect_r_srcs_paths()
        expect_result = set()
        self.assertEqual(module_data.r_java_paths, expect_result)

        # Test the srcjar target doesn't exist.
        test_module['class'] = ['APPS']
        test_module['srcjars'] = []
        module_data = source_locator.ModuleData(_MODULE_NAME, test_module,
                                                _MODULE_DEPTH)
        module_data._collect_r_srcs_paths()
        expect_result = set()
        self.assertEqual(module_data.r_java_paths, expect_result)

        # Test the srcjar target exists.
        test_module['srcjars'] = [('out/soong/.intermediates/packages/apps/'
                                   'test_aapt2/aapt2.srcjar')]
        module_data = source_locator.ModuleData(_MODULE_NAME, test_module,
                                                _MODULE_DEPTH)
        module_data._collect_r_srcs_paths()
        expect_result = {
            'out/soong/.intermediates/packages/apps/test_aapt2/aapt2'
        }
        self.assertEqual(module_data.r_java_paths, expect_result)

    def test_parse_source_path(self):
        """Test _parse_source_path."""
        # The package name of e.java is c.d.
        test_java = 'a/b/c/d/e.java'
        package_name = 'c.d'
        expect_result = 'a/b'
        src_path = source_locator.ModuleData._parse_source_path(test_java,
                                                                package_name)
        self.assertEqual(src_path, expect_result)

        # The package name of e.java is c.d.
        test_java = 'a/b/c.d/e.java'
        package_name = 'c.d'
        expect_result = 'a/b'
        src_path = source_locator.ModuleData._parse_source_path(test_java,
                                                                package_name)
        self.assertEqual(src_path, expect_result)

        # The package name of e.java is x.y.
        test_java = 'a/b/c/d/e.java'
        package_name = 'x.y'
        expect_result = 'a/b/c/d'
        src_path = source_locator.ModuleData._parse_source_path(test_java,
                                                                package_name)
        self.assertEqual(src_path, expect_result)

        # The package name of f.java is c.d.
        test_java = 'a/b/c.d/e/c/d/f.java'
        package_name = 'c.d'
        expect_result = 'a/b/c.d/e'
        src_path = source_locator.ModuleData._parse_source_path(test_java,
                                                                package_name)
        self.assertEqual(src_path, expect_result)

        # The package name of f.java is c.d.e.
        test_java = 'a/b/c.d/e/c.d/e/f.java'
        package_name = 'c.d.e'
        expect_result = 'a/b/c.d/e'
        src_path = source_locator.ModuleData._parse_source_path(test_java,
                                                                package_name)
        self.assertEqual(src_path, expect_result)

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    def test_append_jar_file(self, mock_android_root_dir):
        """Test _append_jar_file process."""
        # Append an existing jar file path to module_data.jar_files.
        test_jar_file = os.path.join(_MODULE_PATH, 'test.jar')
        result_jar_list = set([test_jar_file])
        mock_android_root_dir.return_value = unittest_constants.TEST_DATA_PATH
        module_data = source_locator.ModuleData(_MODULE_NAME, _MODULE_INFO,
                                                _MODULE_DEPTH)
        module_data._append_jar_file(test_jar_file)
        self.assertEqual(module_data.jar_files, result_jar_list)

        # Skip if the jar file doesn't exist.
        test_jar_file = os.path.join(_MODULE_PATH, 'jar_not_exist.jar')
        module_data.jar_files = set()
        module_data._append_jar_file(test_jar_file)
        self.assertEqual(module_data.jar_files, set())

        # Skip if it's not a jar file.
        test_jar_file = os.path.join(_MODULE_PATH, 'test.java')
        module_data.jar_files = set()
        module_data._append_jar_file(test_jar_file)
        self.assertEqual(module_data.jar_files, set())

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    def test_append_jar_from_installed(self, mock_android_root_dir):
        """Test _append_jar_from_installed handling."""
        # Test appends the first jar file of 'installed'.
        module_info = dict(_MODULE_INFO)
        module_info['installed'] = [
            os.path.join(_MODULE_PATH, 'test.aar'),
            os.path.join(_MODULE_PATH, 'test.jar'),
            os.path.join(_MODULE_PATH, 'tests/test_second.jar')
        ]
        result_jar_list = set([os.path.join(_MODULE_PATH, 'test.jar')])
        mock_android_root_dir.return_value = unittest_constants.TEST_DATA_PATH
        module_data = source_locator.ModuleData(_MODULE_NAME, module_info,
                                                _MODULE_DEPTH)
        module_data._append_jar_from_installed()
        self.assertEqual(module_data.jar_files, result_jar_list)

        # Test on the jar file path matches the path prefix.
        module_data.jar_files = set()
        result_jar_list = set(
            [os.path.join(_MODULE_PATH, 'tests/test_second.jar')])
        module_data._append_jar_from_installed(
            os.path.join(_MODULE_PATH, 'tests/'))
        self.assertEqual(module_data.jar_files, result_jar_list)

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    def test_set_jars_jarfile(self, mock_android_root_dir):
        """Test _set_jars_jarfile handling."""
        # Combine the module path with jar file name in 'jars' and then append
        # it to module_data.jar_files.
        module_info = dict(_MODULE_INFO)
        module_info['jars'] = [
            'test.jar',
            'src/test.jar',  # This jar file doesn't exist.
            'tests/test_second.jar'
        ]
        result_jar_list = set([
            os.path.join(_MODULE_PATH, 'test.jar'),
            os.path.join(_MODULE_PATH, 'tests/test_second.jar')
        ])
        mock_android_root_dir.return_value = unittest_constants.TEST_DATA_PATH
        module_data = source_locator.ModuleData(_MODULE_NAME, module_info,
                                                _MODULE_DEPTH)
        module_data._set_jars_jarfile()
        self.assertEqual(module_data.jar_files, result_jar_list)

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    def test_locate_sources_path(self, mock_android_root_dir):
        """Test locate_sources_path handling."""
        # Test collect source path.
        module_info = dict(_MODULE_INFO)
        result_src_list = set(['packages/apps/test/src/main/java'])
        result_test_list = set(['packages/apps/test/tests'])
        result_jar_list = set()
        result_r_path = set()
        mock_android_root_dir.return_value = unittest_constants.TEST_DATA_PATH
        module_data = source_locator.ModuleData(_MODULE_NAME, module_info,
                                                _MODULE_DEPTH)
        module_data.locate_sources_path()
        self.assertEqual(module_data.src_dirs, result_src_list)
        self.assertEqual(module_data.test_dirs, result_test_list)
        self.assertEqual(module_data.jar_files, result_jar_list)
        self.assertEqual(module_data.r_java_paths, result_r_path)

        # Test find jar files.
        jar_file = ('out/soong/.intermediates/packages/apps/test/test/'
                    'android_common/test.jar')
        module_info['jarjar_rules'] = ['jarjar-rules.txt']
        module_info['installed'] = [jar_file]
        result_jar_list = set([jar_file])
        module_data = source_locator.ModuleData(_MODULE_NAME, module_info,
                                                _MODULE_DEPTH)
        module_data.locate_sources_path()
        self.assertEqual(module_data.jar_files, result_jar_list)

        # Test find jar by srcjar.
        module_info = dict(_MODULE_INFO)
        module_info['srcs'].extend(
            [('out/soong/.intermediates/packages/apps/test/test/android_common/'
              'gen/test.srcjar')])
        module_info['installed'] = [
            ('out/soong/.intermediates/packages/apps/test/test/android_common/'
             'test.jar')
        ]
        result_jar_list = set([
            jar_file,
            ('out/soong/.intermediates/packages/apps/test/test/'
             'android_common/test.jar')
        ])
        module_data = source_locator.ModuleData(_MODULE_NAME, module_info,
                                                _MODULE_DEPTH)
        module_data.locate_sources_path()
        self.assertEqual(module_data.jar_files, result_jar_list)

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    def test_collect_jar_by_depth_value(self, mock_android_root_dir):
        """Test parameter --depth handling."""
        # Test find jar by module's depth greater than the --depth value from
        # command line.
        depth_by_source = 2
        module_info = dict(_MODULE_INFO)
        module_info['depth'] = 3
        module_info['installed'] = [
            ('out/soong/.intermediates/packages/apps/test/test/android_common/'
             'test.jar')
        ]
        result_src_list = set()
        result_jar_list = set(
            [('out/soong/.intermediates/packages/apps/test/test/'
              'android_common/test.jar')])
        mock_android_root_dir.return_value = unittest_constants.TEST_DATA_PATH
        module_data = source_locator.ModuleData(_MODULE_NAME, module_info,
                                                depth_by_source)
        module_data.locate_sources_path()
        self.assertEqual(module_data.src_dirs, result_src_list)
        self.assertEqual(module_data.jar_files, result_jar_list)

        # Test find source folder when module's depth equal to the --depth value
        # from command line.
        depth_by_source = 2
        module_info = dict(_MODULE_INFO)
        module_info['depth'] = 2
        result_src_list = set(['packages/apps/test/src/main/java'])
        result_test_list = set(['packages/apps/test/tests'])
        result_jar_list = set()
        result_r_path = set()
        module_data = source_locator.ModuleData(_MODULE_NAME, module_info,
                                                depth_by_source)
        module_data.locate_sources_path()
        self.assertEqual(module_data.src_dirs, result_src_list)
        self.assertEqual(module_data.test_dirs, result_test_list)
        self.assertEqual(module_data.jar_files, result_jar_list)
        self.assertEqual(module_data.r_java_paths, result_r_path)

        # Test find source folder when module's depth smaller than the --depth
        # value from command line.
        depth_by_source = 3
        module_info = dict(_MODULE_INFO)
        module_info['depth'] = 2
        result_src_list = set(['packages/apps/test/src/main/java'])
        result_test_list = set(['packages/apps/test/tests'])
        result_jar_list = set()
        result_r_path = set()
        module_data = source_locator.ModuleData(_MODULE_NAME, module_info,
                                                depth_by_source)
        module_data.locate_sources_path()
        self.assertEqual(module_data.src_dirs, result_src_list)
        self.assertEqual(module_data.test_dirs, result_test_list)
        self.assertEqual(module_data.jar_files, result_jar_list)
        self.assertEqual(module_data.r_java_paths, result_r_path)

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    @mock.patch('atest.atest_utils.build')
    def test_locate_source(self, mock_atest_utils_build, mock_project_info,
                           mock_android_root_dir):
        """Test locate_source handling."""
        mock_atest_utils_build.build.return_value = True
        test_root_path = os.path.join(tempfile.mkdtemp(), 'test')
        shutil.copytree(unittest_constants.TEST_DATA_PATH, test_root_path)
        mock_android_root_dir.return_value = test_root_path
        generated_jar = ('out/soong/.intermediates/packages/apps/test/test/'
                         'android_common/generated.jar')
        module_info = dict(_MODULE_INFO)
        module_info['srcs'].extend(
            [('out/soong/.intermediates/packages/apps/test/test/android_common/'
              'gen/test.srcjar')])
        module_info['installed'] = [generated_jar]
        mock_project_info.dep_modules = {'test': module_info}
        mock_project_info.source_path = {
            'source_folder_path': set(),
            'test_folder_path': set(),
            'jar_path': set(),
            'jar_module_path': dict(),
            'srcjar_path': set(),
            'r_java_path': set(),
        }
        # Show warning when the jar not exists after build the module.
        result_jar = set()
        source_locator.locate_source(mock_project_info, False, 0,
                                     constant.IDE_INTELLIJ, True)
        self.assertEqual(mock_project_info.source_path['jar_path'], result_jar)

        # Test on jar exists.
        jar_abspath = os.path.join(test_root_path, generated_jar)
        result_jar = set([generated_jar])
        result_jar_module_path = dict({generated_jar: module_info['path'][0]})
        try:
            open(jar_abspath, 'w').close()
            source_locator.locate_source(mock_project_info, False, 0,
                                         constant.IDE_INTELLIJ, False)
            self.assertEqual(mock_project_info.source_path['jar_path'],
                             result_jar)
            self.assertEqual(mock_project_info.source_path['jar_module_path'],
                             result_jar_module_path)
        finally:
            shutil.rmtree(test_root_path)

        # Test collects source and test folders.
        result_source = set(['packages/apps/test/src/main/java'])
        result_test = set(['packages/apps/test/tests'])
        result_r_path = set()
        self.assertEqual(mock_project_info.source_path['source_folder_path'],
                         result_source)
        self.assertEqual(mock_project_info.source_path['test_folder_path'],
                         result_test)
        self.assertEqual(mock_project_info.source_path['r_java_path'],
                         result_r_path)

        # Test loading jar from dependencies parameter.
        default_jar = os.path.join(_MODULE_PATH, 'test.jar')
        module_info['dependencies'] = [default_jar]
        result_jar = set([generated_jar, default_jar])
        source_locator.locate_source(mock_project_info, False, 0,
                                     constant.IDE_INTELLIJ, False)
        self.assertEqual(mock_project_info.source_path['jar_path'], result_jar)

    def test_separate_build_target(self):
        """Test separate_build_target."""
        test_list = ['1', '22', '333', '4444', '55555', '1', '7777777']
        target = []
        sample = [['1', '22', '333'], ['4444'], ['55555', '1'], ['7777777']]
        for start, end in iter(
                source_locator._separate_build_targets(test_list, 9)):
            target.append(test_list[start: end])
        self.assertEqual(target, sample)

    def test_collect_srcjar_path(self):
        """Test collect srcjar path."""
        srcjar_path = 'a/b/aapt2.srcjar'
        test_module = dict(_MODULE_INFO)
        test_module['srcjars'] = [srcjar_path]
        expacted_result = set(['%s!/' % srcjar_path])
        module_data = source_locator.ModuleData(_MODULE_NAME, test_module,
                                                _MODULE_DEPTH)
        module_data._collect_srcjar_path(srcjar_path)
        self.assertEqual(module_data.srcjar_paths, expacted_result)


if __name__ == '__main__':
    unittest.main()
