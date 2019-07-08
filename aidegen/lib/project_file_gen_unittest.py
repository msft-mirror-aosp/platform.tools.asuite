#!/usr/bin/env python3
#
# Copyright 2018 - The Android Open Source Project
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

"""Unittests for project_file_gen."""

import copy
import os
import shutil
import unittest
from unittest import mock

import aidegen.unittest_constants as uc
from aidegen import constant
from aidegen.lib import common_util
from aidegen.lib import project_file_gen
from aidegen.lib.project_file_gen import ProjectFileGenerator
from atest import module_info


# pylint: disable=protected-access
class AidegenProjectFileGenUnittest(unittest.TestCase):
    """Unit tests for project_file_gen.py."""

    maxDiff = None
    _TEST_DATA_PATH = uc.TEST_DATA_PATH
    _PROJECT_PATH = os.path.join(_TEST_DATA_PATH, 'project')
    _ANDROID_FACET_SAMPLE = os.path.join(_TEST_DATA_PATH, 'android_facet.iml')
    _PROJECT_FACET_SAMPLE = os.path.join(_TEST_DATA_PATH, 'project_facet.iml')
    _MODULE_DEP_SAMPLE = os.path.join(_TEST_DATA_PATH, 'module_dependency.iml')
    _IML_SAMPLE = os.path.join(_TEST_DATA_PATH, 'test.iml')
    _DEPENDENCIES_IML_SAMPLE = os.path.join(_TEST_DATA_PATH, 'dependencies.iml')
    _MODULE_XML_SAMPLE = os.path.join(_TEST_DATA_PATH, 'modules.xml')
    _MAIN_MODULE_XML_SAMPLE = os.path.join(_TEST_DATA_PATH,
                                           'modules_only_self_module.xml')
    _ENABLE_DEBUGGER_MODULE_SAMPLE = os.path.join(
        _TEST_DATA_PATH, 'modules_with_enable_debugger.xml')
    _VCS_XML_SAMPLE = os.path.join(_TEST_DATA_PATH, 'vcs.xml')
    _IML_PATH = os.path.join(uc.ANDROID_PROJECT_PATH, 'android_project.iml')
    _DEPENDENCIES_IML_PATH = os.path.join(uc.ANDROID_PROJECT_PATH,
                                          'dependencies.iml')
    _IDEA_PATH = os.path.join(uc.ANDROID_PROJECT_PATH, '.idea')
    _MODULE_PATH = os.path.join(_IDEA_PATH, 'modules.xml')
    _VCS_PATH = os.path.join(_IDEA_PATH, 'vcs.xml')
    _SOURCE_SAMPLE = os.path.join(_TEST_DATA_PATH, 'source.iml')
    _SRCJAR_SAMPLE = os.path.join(_TEST_DATA_PATH, 'srcjar.iml')
    _LOCAL_PATH_TOKEN = '@LOCAL_PATH@'
    _AOSP_FOLDER = '/aosp'
    _TEST_SOURCE_LIST = [
        'a/b/c/d', 'a/b/c/d/e', 'a/b/c/d/e/f', 'a/b/c/d/f', 'e/f/a', 'e/f/b/c',
        'e/f/g/h'
    ]
    _ANDROID_SOURCE_RELATIVE_PATH = 'test_data/project'
    _SAMPLE_CONTENT_LIST = ['a/b/c/d', 'e/f']
    _SAMPLE_TRIMMED_SOURCE_LIST = ['a/b/c/d', 'e/f/a', 'e/f/b/c', 'e/f/g/h']
    _SAMPLE_EXCLUDE_FOLDERS = [
        '            <excludeFolder url="file://%s/.idea" />\n'
        % _TEST_DATA_PATH,
        '            <excludeFolder url="file://%s/out" />\n' % _TEST_DATA_PATH,
    ]

    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_handle_facet_for_android(self, mock_project):
        """Test _handle_facet with android project."""
        mock_project.project_absolute_path = uc.ANDROID_PROJECT_PATH
        android_facet = ProjectFileGenerator(mock_project)._handle_facet(
            constant.FILE_IML)
        sample_android_facet = common_util.read_file_content(
            self._ANDROID_FACET_SAMPLE)
        self.assertEqual(android_facet, sample_android_facet)

    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_handle_facet_for_normal(self, mock_project):
        """Test _handle_facet with normal module."""
        mock_project.project_absolute_path = self._PROJECT_PATH
        project_facet = ProjectFileGenerator(mock_project)._handle_facet(
            constant.FILE_IML)
        sample_project_facet = common_util.read_file_content(
            self._PROJECT_FACET_SAMPLE)
        self.assertEqual(project_facet, sample_project_facet)

    def test_handle_module_dependency(self):
        """Test _module_dependency."""
        module_dependency = constant.FILE_IML.replace(
            project_file_gen._MODULE_DEP_TOKEN, '')
        correct_module_dep = common_util.read_file_content(
            self._MODULE_DEP_SAMPLE)
        self.assertEqual(correct_module_dep, module_dependency)

    def test_trim_same_root_source(self):
        """Test _trim_same_root_source."""
        url_list = project_file_gen._trim_same_root_source(
            self._TEST_SOURCE_LIST[:])
        self.assertEqual(url_list, self._SAMPLE_TRIMMED_SOURCE_LIST)

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_handle_source_folder(self, mock_project, mock_get_root):
        """Test _handle_source_folder."""
        mock_get_root.return_value = self._AOSP_FOLDER
        mock_project.project_relative_path = self._ANDROID_SOURCE_RELATIVE_PATH
        source = ProjectFileGenerator(mock_project)._handle_source_folder(
            constant.FILE_IML, copy.deepcopy(uc.ANDROID_SOURCE_DICT), True)
        sample_source = common_util.read_file_content(self._SOURCE_SAMPLE)
        self.assertEqual(source, sample_source)

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_generate_iml(self, mock_project, mock_get_root):
        """Test _generate_iml."""
        mock_get_root.return_value = self._AOSP_FOLDER
        mock_project.project_absolute_path = uc.ANDROID_PROJECT_PATH
        mock_project.project_relative_path = self._ANDROID_SOURCE_RELATIVE_PATH
        mock_project.source_path['jar_path'] = set(uc.JAR_DEP_LIST)
        pfile_gen = ProjectFileGenerator(mock_project)
        # Test for main project.
        try:
            iml_path, dependencies_iml_path = pfile_gen._generate_iml(
                copy.deepcopy(uc.ANDROID_SOURCE_DICT), is_main_module=True)
            test_iml = common_util.read_file_content(iml_path)
            sample_iml = common_util.read_file_content(self._IML_SAMPLE)
        finally:
            os.remove(iml_path)
            if dependencies_iml_path:
                os.remove(dependencies_iml_path)
        self.assertEqual(test_iml, sample_iml)

        # Test for sub projects.
        try:
            iml_path, _ = pfile_gen._generate_iml(
                copy.deepcopy(uc.ANDROID_SOURCE_DICT))
            test_iml = common_util.read_file_content(iml_path)
            sample_iml = common_util.read_file_content(self._IML_SAMPLE)
        finally:
            os.remove(iml_path)
        self.assertEqual(test_iml, sample_iml)

    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_generate_modules_xml(self, mock_project):
        """Test _generate_modules_xml."""
        mock_project.project_absolute_path = uc.ANDROID_PROJECT_PATH
        pfile_gen = ProjectFileGenerator(mock_project)
        # Test for main project.
        try:
            pfile_gen._generate_modules_xml([])
            project_file_gen.update_enable_debugger(uc.ANDROID_PROJECT_PATH)
            test_module = common_util.read_file_content(self._MODULE_PATH)
        finally:
            shutil.rmtree(self._IDEA_PATH)
        sample_module = common_util.read_file_content(self._MODULE_XML_SAMPLE)
        self.assertEqual(test_module, sample_module)

        # Test for sub projects which only has self module.
        try:
            pfile_gen._generate_modules_xml()
            project_file_gen.update_enable_debugger(uc.ANDROID_PROJECT_PATH)
            test_module = common_util.read_file_content(self._MODULE_PATH)
        finally:
            shutil.rmtree(self._IDEA_PATH)
        sample_module = common_util.read_file_content(
            self._MAIN_MODULE_XML_SAMPLE)
        self.assertEqual(test_module, sample_module)

    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_generate_vcs_xml(self, mock_project):
        """Test _generate_vcs_xml."""
        mock_project.project_absolute_path = uc.ANDROID_PROJECT_PATH
        try:
            git_path = os.path.join(uc.ANDROID_PROJECT_PATH,
                                    project_file_gen._GIT_FOLDER_NAME)
            if not os.path.exists(git_path):
                os.mkdir(git_path)
            pfile_gen = ProjectFileGenerator(mock_project)
            pfile_gen._generate_vcs_xml()
            test_vcs = common_util.read_file_content(self._VCS_PATH)
        finally:
            shutil.rmtree(git_path)
        sample_vcs = common_util.read_file_content(self._VCS_XML_SAMPLE)
        # The sample must base on the real path.
        sample_vcs = sample_vcs.replace(self._LOCAL_PATH_TOKEN,
                                        uc.ANDROID_PROJECT_PATH)
        self.assertEqual(test_vcs, sample_vcs)
        mock_project.project_absolute_path = common_util.get_android_root_dir()
        pfile_gen = ProjectFileGenerator(mock_project)
        self.assertIsNone(pfile_gen._generate_vcs_xml())

    def test_get_uniq_iml_name(self):
        """Test the unique name cache mechanism.

        By using the path data in module info json as input, if the count of
        name data set is the same as sub folder path count, then it means
        there's no duplicated name, the test PASS.
        """
        # Add following test path
        test_paths = {
            'cts/tests/tests/app',
            'cts/tests/app',
            'cts/tests/app/app1/../app',
            'cts/tests/app/app2/../app',
            'cts/tests/app/app3/../app',
            'frameworks/base/tests/xxxxxxxxxxxx/base',
            'frameworks/base',
            'external/xxxxx-xxx/robolectric',
            'external/robolectric',
        }
        mod_info = module_info.ModuleInfo()
        test_paths.update(mod_info._get_path_to_module_info(
            mod_info.name_to_module_info).keys())
        print('\n{} {}.'.format('Test_paths length:', len(test_paths)))

        path_list = []
        for k in test_paths:
            path_list.append(k)
        print('{} {}.'.format('path list with length:', len(path_list)))

        names = [ProjectFileGenerator.get_unique_iml_name(f) for f in path_list]
        print('{} {}.'.format('Names list with length:', len(names)))

        self.assertEqual(len(names), len(path_list))
        dic = {}
        for i, path in enumerate(path_list):
            dic[names[i]] = path
        print('{} {}.'.format('The size of name set is:', len(dic)))
        self.assertEqual(len(dic), len(path_list))

    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_copy_project_files(self, mock_project):
        """Test _copy_constant_project_files."""
        mock_project.project_absolute_path = uc.ANDROID_PROJECT_PATH
        ProjectFileGenerator(mock_project)._copy_constant_project_files()
        self.assertTrue(
            os.path.isfile(
                os.path.join(self._IDEA_PATH,
                             project_file_gen._CODE_STYLE_FOLDER,
                             'codeStyleConfig.xml')))
        self.assertTrue(
            os.path.isfile(
                os.path.join(self._IDEA_PATH,
                             project_file_gen._COPYRIGHT_FOLDER,
                             'Apache_2.xml')))
        self.assertTrue(
            os.path.isfile(
                os.path.join(self._IDEA_PATH,
                             project_file_gen._COPYRIGHT_FOLDER,
                             'profiles_settings.xml')))
        shutil.rmtree(self._IDEA_PATH)

    @mock.patch('os.symlink')
    @mock.patch.object(os.path, 'exists')
    def test_generate_git_ignore(self, mock_path_exist, mock_link):
        """Test _generate_git_ignore."""
        mock_path_exist.return_value = True
        project_file_gen._generate_git_ignore(
            common_util.get_aidegen_root_dir())
        self.assertFalse(mock_link.called)

    def test_filter_out_source_paths(self):
        """Test _filter_out_source_paths."""
        test_set = {'a/java.jar', 'b/java.jar'}
        module_relpath = 'a'
        expected_result = {'b/java.jar'}
        result_set = project_file_gen._filter_out_source_paths(test_set,
                                                               module_relpath)
        self.assertEqual(result_set, expected_result)

    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_merge_all_source_paths(self, mock_main_project, mock_sub_project):
        """Test _merge_all_shared_source_paths."""
        mock_main_project.project_relative_path = 'main'
        mock_main_project.source_path = {
            'source_folder_path': {'main/java.java', 'share1/java.java'},
            'test_folder_path': {'main/test.java', 'share1/test.java'},
            'jar_path': {'main/jar.jar', 'share1/jar.jar'},
            'r_java_path': {'out/R.java'},
        }
        mock_sub_project.project_relative_path = 'sub'
        mock_sub_project.source_path = {
            'source_folder_path': {'sub/java.java', 'share2/java.java'},
            'test_folder_path': {'sub/test.java', 'share2/test.java'},
            'jar_path': {'sub/jar.jar', 'share2/jar.jar'},
            'r_java_path': {'out/R.java'},
        }
        expected_result = {
            'source_folder_path': {
                'main/java.java',
                'share1/java.java',
                'share2/java.java',
            },
            'test_folder_path': {
                'main/test.java',
                'share1/test.java',
                'share2/test.java',
            },
            'jar_path': {
                'main/jar.jar',
                'sub/jar.jar',
                'share1/jar.jar',
                'share2/jar.jar',
            },
            'r_java_path': {'out/R.java'}
        }
        projects = [mock_main_project, mock_sub_project]
        project_file_gen._merge_all_shared_source_paths(projects)
        self.assertEqual(mock_main_project.source_path, expected_result)

    def test_get_exclude_folders(self):
        """Test _get_exclude_folders."""
        exclude_folders = project_file_gen._get_exclude_content(
            self._TEST_DATA_PATH)
        self.assertEqual(self._SAMPLE_EXCLUDE_FOLDERS, exclude_folders)

    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_update_enable_debugger(self, mock_project):
        """Test update_enable_debugger."""
        enable_debugger_iml = '/path/to/enable_debugger/enable_debugger.iml'
        sample_module = common_util.read_file_content(
            self._ENABLE_DEBUGGER_MODULE_SAMPLE)
        mock_project.project_absolute_path = uc.ANDROID_PROJECT_PATH
        pfile_gen = ProjectFileGenerator(mock_project)
        try:
            pfile_gen._generate_modules_xml([])
            project_file_gen.update_enable_debugger(
                uc.ANDROID_PROJECT_PATH, enable_debugger_iml)
            test_module = common_util.read_file_content(self._MODULE_PATH)
            self.assertEqual(test_module, sample_module)
        finally:
            shutil.rmtree(self._IDEA_PATH)

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_handle_srcjar_folder(self, mock_project, mock_get_root):
        """Test _handle_srcjar_folder."""
        mock_get_root.return_value = self._AOSP_FOLDER
        source = ProjectFileGenerator(mock_project)._handle_srcjar_folder(
            constant.FILE_IML, {'out/aapt2.srcjar!/'})
        sample_source = common_util.read_file_content(self._SRCJAR_SAMPLE)
        self.assertEqual(source, sample_source)


if __name__ == '__main__':
    unittest.main()
