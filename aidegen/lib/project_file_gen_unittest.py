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
import unittest

from aidegen.lib import project_file_gen


# pylint: disable=protected-access
# pylint: disable=invalid-name
class AidegenProjectFileGenUnittest(unittest.TestCase):
    """Unit tests for project_file_gen.py"""

    _TEST_DATA_PATH = os.path.join(project_file_gen._ROOT_DIR, "test_data")
    _ANDROID_PROJECT_PATH = os.path.join(_TEST_DATA_PATH, "android_project")
    _PROJECT_PATH = os.path.join(_TEST_DATA_PATH, "project")
    _ANDROID_FACET_SAMPLE = os.path.join(_TEST_DATA_PATH, "android_facet.iml")
    _PROJECT_FACET_SAMPLE = os.path.join(_TEST_DATA_PATH, "project_facet.iml")
    _MODULE_DEP_SAMPLE = os.path.join(_TEST_DATA_PATH, "module_dependency.iml")
    _JAR_DEP = ["test1.jar", "test2.jar"]

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


if __name__ == '__main__':
    unittest.main()
