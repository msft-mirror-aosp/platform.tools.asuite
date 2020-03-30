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

from aidegen import templates
from aidegen import unittest_constants
from aidegen.lib import common_util
from aidegen.lib import project_file_gen
from aidegen.lib import project_info
from atest import module_info


# pylint: disable=protected-access
# pylint: disable-msg=too-many-arguments
class AidegenProjectFileGenUnittest(unittest.TestCase):
    """Unit tests for project_file_gen.py."""

    maxDiff = None
    _TEST_DATA_PATH = unittest_constants.TEST_DATA_PATH
    _ANDROID_PROJECT_PATH = unittest_constants.ANDROID_PROJECT_PATH
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
    _IML_PATH = os.path.join(_ANDROID_PROJECT_PATH, 'android_project.iml')
    _DEPENDENCIES_IML_PATH = os.path.join(_ANDROID_PROJECT_PATH,
                                          'dependencies.iml')
    _IDEA_PATH = os.path.join(_ANDROID_PROJECT_PATH, '.idea')
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
        mock_project.project_absolute_path = self._ANDROID_PROJECT_PATH
        android_facet = project_file_gen.ProjectFileGenerator(
            mock_project)._handle_facet(templates.FILE_IML)
        sample_android_facet = common_util.read_file_content(
            self._ANDROID_FACET_SAMPLE)
        self.assertEqual(android_facet, sample_android_facet)

    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_handle_facet_for_normal(self, mock_project):
        """Test _handle_facet with normal module."""
        mock_project.project_absolute_path = self._PROJECT_PATH
        project_facet = project_file_gen.ProjectFileGenerator(
            mock_project)._handle_facet(templates.FILE_IML)
        sample_project_facet = common_util.read_file_content(
            self._PROJECT_FACET_SAMPLE)
        self.assertEqual(project_facet, sample_project_facet)

    def test_handle_module_dependency(self):
        """Test _module_dependency."""
        module_dependency = templates.FILE_IML.replace(
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
        source = project_file_gen.ProjectFileGenerator(
            mock_project)._handle_source_folder(
                templates.FILE_IML, copy.deepcopy(
                    unittest_constants.ANDROID_SOURCE_DICT), True)
        sample_source = common_util.read_file_content(self._SOURCE_SAMPLE)
        self.assertEqual(source, sample_source)

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_generate_iml(self, mock_project, mock_get_root):
        """Test _generate_iml."""
        mock_get_root.return_value = self._AOSP_FOLDER
        mock_project.project_absolute_path = self._ANDROID_PROJECT_PATH
        mock_project.project_relative_path = self._ANDROID_SOURCE_RELATIVE_PATH
        mock_project.source_path['jar_path'] = set(
            unittest_constants.JAR_DEP_LIST)
        pfile_gen = project_file_gen.ProjectFileGenerator(mock_project)
        # Test for main project.
        try:
            iml_path, dependencies_iml_path = pfile_gen._generate_iml(
                copy.deepcopy(unittest_constants.ANDROID_SOURCE_DICT))
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
                copy.deepcopy(unittest_constants.ANDROID_SOURCE_DICT))
            test_iml = common_util.read_file_content(iml_path)
            sample_iml = common_util.read_file_content(self._IML_SAMPLE)
        finally:
            os.remove(iml_path)
        self.assertEqual(test_iml, sample_iml)

    @mock.patch.object(common_util, 'file_generate')
    @mock.patch.object(project_file_gen.ProjectFileGenerator,
                       '_handle_srcjar_folder')
    @mock.patch.object(project_file_gen.ProjectFileGenerator, '_handle_facet')
    @mock.patch.object(project_file_gen.ProjectFileGenerator,
                       '_handle_source_folder')
    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_generate_iml_for_module(self, mock_project, mock_get_root,
                                     mock_do_src, mock_do_facet,
                                     mock_do_srcjar, mock_file_gen):
        """Test _generate_iml for generating module's iml."""
        mock_get_root.return_value = self._AOSP_FOLDER
        mock_project.project_absolute_path = self._ANDROID_PROJECT_PATH
        mock_project.project_relative_path = self._ANDROID_SOURCE_RELATIVE_PATH
        mock_project.source_path['jar_path'] = set(
            unittest_constants.JAR_DEP_LIST)
        test_srcjar_for_sub = ('test', 'srcjar', 'path')
        mock_project.source_path['srcjar_path'] = test_srcjar_for_sub
        mock_project.is_main_project = False
        pfile_gen = project_file_gen.ProjectFileGenerator(mock_project)
        mock_do_facet.return_value = 'facet'
        mock_do_src.return_value = 'source'
        mock_do_srcjar.return_value = 'srcjar'
        mock_file_gen.return_value = None

        # Test for module iml generation.
        pfile_gen._generate_iml(copy.deepcopy(
            unittest_constants.ANDROID_SOURCE_DICT))
        self.assertTrue(mock_do_facet.called)
        self.assertTrue(mock_do_src.called_with(True))
        self.assertTrue(mock_do_srcjar.called_with(test_srcjar_for_sub))
        self.assertEqual(mock_file_gen.call_count, 1)

    @mock.patch('aidegen.lib.project_config.ProjectConfig')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_generate_modules_xml(self, mock_project, mock_config):
        """Test _generate_modules_xml."""
        mock_config.is_launch_ide = True
        mock_project.project_absolute_path = self._ANDROID_PROJECT_PATH
        pfile_gen = project_file_gen.ProjectFileGenerator(mock_project)
        # Test for main project.
        try:
            pfile_gen._generate_modules_xml([])
            project_file_gen.update_enable_debugger(self._ANDROID_PROJECT_PATH)
            test_module = common_util.read_file_content(self._MODULE_PATH)
        finally:
            shutil.rmtree(self._IDEA_PATH)
        sample_module = common_util.read_file_content(self._MODULE_XML_SAMPLE)
        self.assertEqual(test_module, sample_module)

        # Test for sub projects which only has self module.
        try:
            pfile_gen._generate_modules_xml()
            project_file_gen.update_enable_debugger(self._ANDROID_PROJECT_PATH)
            test_module = common_util.read_file_content(self._MODULE_PATH)
        finally:
            shutil.rmtree(self._IDEA_PATH)
        sample_module = common_util.read_file_content(
            self._MAIN_MODULE_XML_SAMPLE)
        self.assertEqual(test_module, sample_module)

    @mock.patch('os.path.isdir')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_get_project_git_path(self, mock_project, mock_isdir):
        """Test _get_project_git_path."""
        mock_project.project_absolute_path = '/a/b'
        mock_isdir.return_value = True
        expected_git_path = '/a/b'
        pfile_gen = project_file_gen.ProjectFileGenerator(mock_project)
        test_git_path = pfile_gen._get_project_git_path()
        self.assertEqual(test_git_path, expected_git_path)

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    @mock.patch('aidegen.lib.project_file_gen._get_all_git_path')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_merge_project_vcs_xmls(self, mock_project, mock_get_all_git_path,
                                    mock_get_root):
        """Test _merge_project_vcs_xmls."""
        mock_project.project_absolute_path = (
            unittest_constants.ANDROID_PROJECT_PATH)
        mock_project.git_path = unittest_constants.ANDROID_PROJECT_PATH
        project_file_gen._merge_project_vcs_xmls([mock_project])
        test_vcs = common_util.read_file_content(self._VCS_PATH)
        sample_vcs = common_util.read_file_content(self._VCS_XML_SAMPLE)
        # The sample must base on the real path.
        sample_vcs = sample_vcs.replace(self._LOCAL_PATH_TOKEN,
                                        self._ANDROID_PROJECT_PATH)
        self.assertEqual(test_vcs, sample_vcs)
        mock_get_root.return_value = unittest_constants.ANDROID_PROJECT_PATH
        project_file_gen._merge_project_vcs_xmls([mock_project])
        self.assertTrue(mock_get_all_git_path.called)

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
        for path in test_paths:
            path_list.append(path)
        print('{} {}.'.format('path list with length:', len(path_list)))

        names = [project_file_gen.ProjectFileGenerator.get_unique_iml_name(f)
                 for f in path_list]
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
        mock_project.project_absolute_path = self._ANDROID_PROJECT_PATH
        project_file_gen.ProjectFileGenerator(
            mock_project)._copy_constant_project_files()
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

    @mock.patch('logging.error')
    @mock.patch('os.symlink')
    @mock.patch.object(os.path, 'exists')
    def test_generate_git_ignore(self, mock_path_exist, mock_link,
                                 mock_loggin_error):
        """Test _generate_git_ignore."""
        mock_path_exist.return_value = True
        project_file_gen._generate_git_ignore(
            common_util.get_aidegen_root_dir())
        self.assertFalse(mock_link.called)

        # Test for creating symlink exception.
        mock_path_exist.return_value = False
        mock_link.side_effect = OSError()
        project_file_gen._generate_git_ignore(
            common_util.get_aidegen_root_dir())
        self.assertTrue(mock_loggin_error.called)

    def test_filter_out_source_paths(self):
        """Test _filter_out_source_paths."""
        test_set = {'a/a.java', 'b/b.java', 'c/c.java'}
        module_relpath = {'a', 'c'}
        expected_result = {'b/b.java'}
        result_set = project_file_gen._filter_out_source_paths(test_set,
                                                               module_relpath)
        self.assertEqual(result_set, expected_result)

    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_merge_all_source_paths(self, mock_main_project, mock_sub_project):
        """Test _merge_all_shared_source_paths."""
        mock_main_project.project_relative_path = 'main'
        mock_main_project.source_path = {
            'source_folder_path': {
                'main/java.java',
                'sub/java.java',
                'share1/java.java'
            },
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

    @mock.patch('aidegen.lib.project_config.ProjectConfig')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_update_enable_debugger(self, mock_project, mock_config):
        """Test update_enable_debugger."""
        mock_config.is_launch_ide = True
        enable_debugger_iml = '/path/to/enable_debugger/enable_debugger.iml'
        sample_module = common_util.read_file_content(
            self._ENABLE_DEBUGGER_MODULE_SAMPLE)
        mock_project.project_absolute_path = self._ANDROID_PROJECT_PATH
        pfile_gen = project_file_gen.ProjectFileGenerator(mock_project)
        try:
            pfile_gen._generate_modules_xml([])
            project_file_gen.update_enable_debugger(self._ANDROID_PROJECT_PATH,
                                                    enable_debugger_iml)
            test_module = common_util.read_file_content(self._MODULE_PATH)
            self.assertEqual(test_module, sample_module)
        finally:
            shutil.rmtree(self._IDEA_PATH)

    @mock.patch('aidegen.lib.common_util.get_android_root_dir')
    @mock.patch('aidegen.lib.project_info.ProjectInfo')
    def test_handle_srcjar_folder(self, mock_project, mock_get_root):
        """Test _handle_srcjar_folder."""
        mock_get_root.return_value = self._AOSP_FOLDER
        source = project_file_gen.ProjectFileGenerator(
            mock_project)._handle_srcjar_folder(templates.FILE_IML,
                                                {'out/aapt2.srcjar!/'})
        sample_source = common_util.read_file_content(self._SRCJAR_SAMPLE)
        self.assertEqual(source, sample_source)

    @mock.patch.object(project_file_gen.ProjectFileGenerator,
                       '_get_project_git_path')
    @mock.patch.object(project_file_gen.ProjectFileGenerator,
                       '_generate_iml')
    @mock.patch.object(project_file_gen.ProjectFileGenerator,
                       '_generate_source_section')
    @mock.patch.object(project_file_gen.ProjectFileGenerator,
                       '_generate_modules_xml')
    @mock.patch.object(project_info, 'ProjectInfo')
    def test_generate_intellij_project_file(self, mock_project,
                                            mock_gen_xml, mock_gen_source,
                                            mock_gen_iml, mock_get_git_path):
        """Test generate_intellij_project_file."""
        mock_project.project_absolute_path = self._ANDROID_PROJECT_PATH
        mock_gen_source.return_value = {'a', 'true'}
        mock_gen_iml.return_value = ('iml/path', '')
        mock_get_git_path.return_value = 'git/path'
        project_gen = project_file_gen.ProjectFileGenerator(mock_project)
        project_gen.project_info.is_main_project = False
        project_gen.generate_intellij_project_file()
        self.assertEqual(project_gen.project_info.iml_path, 'iml/path')
        self.assertEqual(project_gen.project_info.git_path, 'git/path')
        self.assertFalse(mock_gen_xml.called)
        project_gen.project_info.is_main_project = True
        project_gen.generate_intellij_project_file()
        self.assertTrue(mock_gen_xml.called)

    @mock.patch.object(project_info, 'ProjectInfo')
    def test_generate_source_section(self, mock_project):
        """Test _generate_source_section."""
        mock_project.project_absolute_path = self._ANDROID_PROJECT_PATH
        mock_project.source_path = {
            'source': ['a', 'b']
        }
        project_gen = project_file_gen.ProjectFileGenerator(mock_project)
        expected_result = {'a': False, 'b': False}
        test_result = project_gen._generate_source_section('source', False)
        self.assertEqual(test_result, expected_result)

    @mock.patch.object(common_util, 'get_android_root_dir')
    @mock.patch.object(project_info, 'ProjectInfo')
    def test_is_project_relative_source(self, mock_project, mock_get_root):
        """Test _is_project_relative_source."""
        mock_get_root.return_value = '/aosp'
        mock_project.project_absolute_path = '/aosp'
        mock_project.project_relative_path = ''
        project_gen = project_file_gen.ProjectFileGenerator(mock_project)
        self.assertTrue(project_gen._is_project_relative_source('a/b'))

        mock_project.project_absolute_path = '/aosp/a/b'
        mock_project.project_relative_path = 'a/b'
        project_gen = project_file_gen.ProjectFileGenerator(mock_project)
        self.assertTrue(project_gen._is_project_relative_source('a/b/c'))

        mock_project.project_absolute_path = '/test/a/b'
        mock_project.project_relative_path = 'a/b'
        project_gen = project_file_gen.ProjectFileGenerator(mock_project)
        self.assertFalse(project_gen._is_project_relative_source('d/e'))

    @mock.patch('os.walk')
    def test_get_all_git_path(self, mock_os_walk):
        """Test _get_all_git_path."""
        # Test .git folder exists.
        mock_os_walk.return_value = [('/root', ['.git', 'a'], None)]
        test_result = list(project_file_gen._get_all_git_path('/root'))
        expected_result = ['/root']
        self.assertEqual(test_result, expected_result)

        # Test .git folder does not exist.
        mock_os_walk.return_value = [('/root', ['a'], None)]
        test_result = list(project_file_gen._get_all_git_path('/root'))
        expected_result = []
        self.assertEqual(test_result, expected_result)

    @mock.patch.object(common_util, 'file_generate')
    @mock.patch('os.path.isfile')
    def test_generate_test_mapping_schema(self, mock_is_file,
                                          mock_file_generate):
        """Test _generate_test_mapping_schema."""
        mock_is_file.return_value = False
        project_file_gen._generate_test_mapping_schema('')
        self.assertFalse(mock_file_generate.called)
        mock_is_file.return_value = True
        project_file_gen._generate_test_mapping_schema('')
        self.assertTrue(mock_file_generate.called)


if __name__ == '__main__':
    unittest.main()
