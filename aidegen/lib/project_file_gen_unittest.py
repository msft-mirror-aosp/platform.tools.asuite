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

from aidegen import unittest_constants
from aidegen.lib import project_file_gen


# pylint: disable=protected-access
# pylint: disable=invalid-name
class AidegenProjectFileGenUnittest(unittest.TestCase):
    """Unit tests for project_file_gen.py."""

    maxDiff = None
    _TEST_DATA_PATH = unittest_constants.TEST_DATA_PATH
    _ANDROID_PROJECT_PATH = os.path.join(_TEST_DATA_PATH, 'android_project')
    _PROJECT_PATH = os.path.join(_TEST_DATA_PATH, 'project')
    _ANDROID_FACET_SAMPLE = os.path.join(_TEST_DATA_PATH, 'android_facet.iml')
    _PROJECT_FACET_SAMPLE = os.path.join(_TEST_DATA_PATH, 'project_facet.iml')
    _MODULE_DEP_SAMPLE = os.path.join(_TEST_DATA_PATH, 'module_dependency.iml')
    _IML_SAMPLE = os.path.join(_TEST_DATA_PATH, 'test.iml')
    _IML_TEMPLEATE_SAMPLE = os.path.join(_TEST_DATA_PATH, 'test-template.iml')
    _DEPENDENCIES_IML_SAMPLE = os.path.join(_TEST_DATA_PATH, 'dependencies.iml')
    _MODULE_XML_SAMPLE = os.path.join(_TEST_DATA_PATH, 'modules.xml')
    _VCS_XML_SAMPLE = os.path.join(_TEST_DATA_PATH, 'vcs.xml')
    _IML_PATH = os.path.join(_ANDROID_PROJECT_PATH, 'android_project.iml')
    _DEPENDENCIES_IML_PATH = os.path.join(_ANDROID_PROJECT_PATH,
                                          'dependencies.iml')
    _IDEA_PATH = os.path.join(_ANDROID_PROJECT_PATH, '.idea')
    _MODULE_PATH = os.path.join(_IDEA_PATH, 'modules.xml')
    _VCS_PATH = os.path.join(_IDEA_PATH, 'vcs.xml')
    _SOURCE_SAMPLE = os.path.join(_TEST_DATA_PATH, 'source.iml')
    _LOCAL_PATH_TOKEN = '@LOCAL_PATH@'
    _AOSP_FOLDER = '/aosp'
    _JAR_DEP_LIST = ['test1.jar', 'test2.jar']
    _TEST_SOURCE_LIST = [
        'a/b/c/d', 'a/b/c/d/e', 'a/b/c/d/e/f', 'a/b/c/d/f', 'e/f/a', 'e/f/b/c',
        'e/f/g/h'
    ]
    _ANDROID_SOURCE_DICT = {
        'test_data/project/level11/level21': True,
        'test_data/project/level11/level22/level31': False,
        'test_data/project/level12/level22': False,
    }
    _ANDROID_SOURCE_RELATIVE_PATH = 'test_data/project/level12/'
    _SAMPLE_CONTENT_LIST = ['a/b/c/d', 'e/f']
    _SAMPLE_TRIMMED_SOURCE_LIST = ['a/b/c/d', 'e/f/a', 'e/f/b/c', 'e/f/g/h']
    _TEST_DICT = {'SystemUI': 'SystemUI.iml', 'tradefed': 'core.iml'}
    _PRODUCT_DIR = '$PROJECT_DIR$'

    def test_handle_facet_with_android_project(self):
        """Test _handle_facet with android project."""
        template = project_file_gen._read_file_content(
            project_file_gen._TEMPLATE_IML_PATH)
        android_facet = project_file_gen._handle_facet(
            template, self._ANDROID_PROJECT_PATH)
        sample_android_facet = project_file_gen._read_file_content(
            self._ANDROID_FACET_SAMPLE)
        self.assertEqual(android_facet, sample_android_facet)

    def test_handle_facet_with_normal_module(self):
        """Test _handle_facet with normal module."""
        template = project_file_gen._read_file_content(
            project_file_gen._TEMPLATE_IML_PATH)
        project_facet = project_file_gen._handle_facet(template,
                                                       self._PROJECT_PATH)
        sample_project_facet = project_file_gen._read_file_content(
            self._PROJECT_FACET_SAMPLE)
        self.assertEqual(project_facet, sample_project_facet)

    def test_handle_module_dependency(self):
        """Test _module_dependency."""
        module_dependency = project_file_gen._read_file_content(
            project_file_gen._TEMPLATE_IML_PATH)
        module_dependency = module_dependency.replace(
            project_file_gen._MODULE_DEP_TOKEN, '')
        correct_module_dep = project_file_gen._read_file_content(
            self._MODULE_DEP_SAMPLE)
        self.assertEqual(correct_module_dep, module_dependency)

    def test_collect_content_url(self):
        """Test _collect_content_url."""
        url_list = project_file_gen._collect_content_url(
            self._TEST_SOURCE_LIST[:])
        self.assertEqual(url_list, self._SAMPLE_CONTENT_LIST)

    def test_trim_same_root_source(self):
        """Test _trim_same_root_source."""
        url_list = project_file_gen._trim_same_root_source(
            self._TEST_SOURCE_LIST[:])
        self.assertEqual(url_list, self._SAMPLE_TRIMMED_SOURCE_LIST)

    def test_handle_source_folder(self):
        """Test _handle_source_folder."""
        template = project_file_gen._read_file_content(
            project_file_gen._TEMPLATE_IML_PATH)
        source = project_file_gen._handle_source_folder(
            self._AOSP_FOLDER, template,
            copy.deepcopy(self._ANDROID_SOURCE_DICT), True)
        sample_source = project_file_gen._read_file_content(self._SOURCE_SAMPLE)
        self.assertEqual(source, sample_source)

    def test_generate_iml(self):
        """Test _generate_iml."""
        try:
            iml_path, dependencies_iml_path = project_file_gen._generate_iml(
                self._AOSP_FOLDER, self._ANDROID_PROJECT_PATH,
                copy.deepcopy(self._ANDROID_SOURCE_DICT), self._JAR_DEP_LIST,
                self._ANDROID_SOURCE_RELATIVE_PATH)
            test_iml = project_file_gen._read_file_content(iml_path)
            sample_iml = project_file_gen._read_file_content(self._IML_SAMPLE)
        finally:
            os.remove(iml_path)
            os.remove(dependencies_iml_path)
        self.assertEqual(test_iml, sample_iml)
        sample_temp_iml = project_file_gen._read_file_content(
            self._IML_TEMPLEATE_SAMPLE)
        module_dependency = project_file_gen._handle_module_depend_for_project(
            self._AOSP_FOLDER, self._JAR_DEP_LIST)
        sample_temp_iml = sample_temp_iml.replace(
            project_file_gen._MODULE_DEP_TOKEN + '\n', module_dependency)
        self.assertEqual(sample_iml, sample_temp_iml)

    def test_generate_modules_xml(self):
        """Test _generate_modules_xml."""
        try:
            project_file_gen._generate_modules_xml(self._ANDROID_PROJECT_PATH)
            test_module = project_file_gen._read_file_content(self._MODULE_PATH)
        finally:
            shutil.rmtree(self._IDEA_PATH)
        sample_module = project_file_gen._read_file_content(
            self._MODULE_XML_SAMPLE)
        self.assertEqual(test_module, sample_module)

    def test_generate_vcs_xml(self):
        """Test _generate_vcs_xml."""
        try:
            project_file_gen._generate_vcs_xml(self._ANDROID_PROJECT_PATH)
            test_vcs = project_file_gen._read_file_content(self._VCS_PATH)
        finally:
            shutil.rmtree(self._IDEA_PATH)
        sample_vcs = project_file_gen._read_file_content(self._VCS_XML_SAMPLE)
        # The sample must base on the real path.
        sample_vcs = sample_vcs.replace(self._LOCAL_PATH_TOKEN,
                                        self._ANDROID_PROJECT_PATH)
        self.assertEqual(test_vcs, sample_vcs)


if __name__ == '__main__':
    unittest.main()
