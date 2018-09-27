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

import os
import shutil
import unittest

from aidegen.lib import project_file_gen


# pylint: disable=protected-access
# pylint: disable=invalid-name
class AidegenProjectFileGenUnittest(unittest.TestCase):
    """Unit tests for project_file_gen.py."""

    _TEST_DATA_PATH = os.path.join(project_file_gen._ROOT_DIR, 'test_data')
    _ANDROID_PROJECT_PATH = os.path.join(_TEST_DATA_PATH, 'android_project')
    _PROJECT_PATH = os.path.join(_TEST_DATA_PATH, 'project')
    _ANDROID_FACET_SAMPLE = os.path.join(_TEST_DATA_PATH, 'android_facet.iml')
    _PROJECT_FACET_SAMPLE = os.path.join(_TEST_DATA_PATH, 'project_facet.iml')
    _MODULE_DEP_SAMPLE = os.path.join(_TEST_DATA_PATH, 'module_dependency.iml')
    _IML_SAMPLE = os.path.join(_TEST_DATA_PATH, 'test.iml')
    _MODULE_XML_SAMPLE = os.path.join(_TEST_DATA_PATH, 'modules.xml')
    _VCS_XML_SAMPLE = os.path.join(_TEST_DATA_PATH, 'vcs.xml')
    _IML_PATH = os.path.join(_ANDROID_PROJECT_PATH, 'android_project.iml')
    _IDEA_PATH = os.path.join(_ANDROID_PROJECT_PATH, '.idea')
    _MODULE_PATH = os.path.join(_IDEA_PATH, 'modules.xml')
    _VCS_PATH = os.path.join(_IDEA_PATH, 'vcs.xml')
    _SOURCE_SAMPLE = os.path.join(_TEST_DATA_PATH, 'source.iml')
    _JAR_DEP = ['test1.jar', 'test2.jar']
    _TEST_SOURCE_LIST = [
        'a/b/c/d/', 'a/b/c/d/e', 'a/b/c/d/e/f', 'a/b/c/d/f', 'e/f/a', 'e/f/b/c',
        'e/f/g/h'
    ]
    _ANDROID_SOURCE_LIST = [
        'test_data/project/level11/level21',
        'test_data/project/level11/level22/level31',
        'test_data/project/level12/level22',
    ]
    _SAMPLE_CONTENT_URL = ['a/b/c/d', 'e/f']

    def test_handle_facet_with_android_project(self):
        """Test _handle_facet with android project."""
        template = project_file_gen._read_template(
            project_file_gen._TEMPLATE_IML_PATH)
        android_facet = project_file_gen._handle_facet(
            template, self._ANDROID_PROJECT_PATH)
        sample_android_facet = project_file_gen._read_template(
            self._ANDROID_FACET_SAMPLE)
        self.assertEqual(android_facet, sample_android_facet)

    def test_handle_facet_with_normal_module(self):
        """Test _handle_facet with normal module."""
        template = project_file_gen._read_template(
            project_file_gen._TEMPLATE_IML_PATH)
        project_facet = project_file_gen._handle_facet(template,
                                                       self._PROJECT_PATH)
        sample_project_facet = project_file_gen._read_template(
            self._PROJECT_FACET_SAMPLE)
        self.assertEqual(project_facet, sample_project_facet)

    def test_handle_module_dependency(self):
        """Test _module_dependency."""
        template = project_file_gen._read_template(
            project_file_gen._TEMPLATE_IML_PATH)
        module_dependency = project_file_gen._handle_module_dependency(
            template, self._JAR_DEP)
        correct_module_dep = project_file_gen._read_template(
            self._MODULE_DEP_SAMPLE)
        self.assertEqual(correct_module_dep, module_dependency)

    def test_collect_content_url(self):
        """Test _collect_content_url."""
        url_list = project_file_gen._collect_content_url(self._TEST_SOURCE_LIST)
        self.assertEqual(url_list, self._SAMPLE_CONTENT_URL)

    def test_handle_source_folder(self):
        """Test _handle_source_folder."""
        template = project_file_gen._read_template(
            project_file_gen._TEMPLATE_IML_PATH)
        source = project_file_gen._handle_source_folder(
            template, self._ANDROID_SOURCE_LIST)
        sample_source = project_file_gen._read_template(self._SOURCE_SAMPLE)
        self.assertEqual(source, sample_source)

    def test_generate_iml(self):
        """Test _generate_iml."""
        try:
            project_file_gen._generate_iml(self._ANDROID_PROJECT_PATH,
                                           self._ANDROID_SOURCE_LIST,
                                           self._JAR_DEP)
            test_iml = project_file_gen._read_template(self._IML_PATH)
        finally:
            os.remove(self._IML_PATH)
        sample_iml = project_file_gen._read_template(self._IML_SAMPLE)
        self.assertEqual(test_iml, sample_iml)

    def test_generate_modules_xml(self):
        """Test _generate_modules_xml."""
        try:
            project_file_gen._generate_modules_xml(self._ANDROID_PROJECT_PATH)
            test_module = project_file_gen._read_template(self._MODULE_PATH)
        finally:
            shutil.rmtree(self._IDEA_PATH)
        sample_module = project_file_gen._read_template(self._MODULE_XML_SAMPLE)
        self.assertEqual(test_module, sample_module)

    def test_generate_vcs_xml(self):
        """Test _generate_iml."""
        try:
            project_file_gen._generate_vcs_xml(self._ANDROID_PROJECT_PATH)
            test_vcs = project_file_gen._read_template(self._VCS_PATH)
        finally:
            shutil.rmtree(self._IDEA_PATH)
        sample_vcs = project_file_gen._read_template(self._VCS_XML_SAMPLE)
        # The sample must base on the real path.
        sample_vcs = sample_vcs.replace(project_file_gen._VCS_TOKEN,
                                        self._ANDROID_PROJECT_PATH)
        self.assertEqual(test_vcs, sample_vcs)


if __name__ == '__main__':
    unittest.main()
