#!/usr/bin/env python3
#
# Copyright 2020 - The Android Open Source Project
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

"""Unittests for source_splitter."""

import shutil
import tempfile
import unittest
from unittest import mock

from aidegen.lib import project_info
from aidegen.project import source_splitter


# pylint: disable=protected-access
class ProjectSplitterUnittest(unittest.TestCase):
    """Unit tests for ProjectSplitter class."""

    _TEST_DIR = None

    def setUp(self):
        """Prepare the testdata related data."""
        projects = []
        targets = ['a', 'b', 'c']
        ProjectSplitterUnittest._TEST_DIR = tempfile.mkdtemp()
        for i, target in enumerate(targets):
            with mock.patch.object(project_info, 'ProjectInfo') as proj_info:
                projects.append(proj_info(target, i == 0))
        projects[0].project_relative_path = 'src1'
        projects[0].source_path = {
            'source_folder_path': {'src1', 'src2', 'other1'},
            'test_folder_path': {'src1/tests'},
            'jar_path': {'jar1.jar'},
            'jar_module_path': dict(),
            'r_java_path': set(),
            'srcjar_path': {'srcjar1.srcjar'}
        }
        projects[1].project_relative_path = 'src2'
        projects[1].source_path = {
            'source_folder_path': {'src2', 'src2/src3', 'src2/lib', 'other2'},
            'test_folder_path': {'src2/tests'},
            'jar_path': set(),
            'jar_module_path': dict(),
            'r_java_path': set(),
            'srcjar_path': {'srcjar2.srcjar'}
        }
        projects[2].project_relative_path = 'src2/src3'
        projects[2].source_path = {
            'source_folder_path': {'src2/src3', 'src2/lib'},
            'test_folder_path': {'src2/src3/tests'},
            'jar_path': {'jar3.jar'},
            'jar_module_path': dict(),
            'r_java_path': set(),
            'srcjar_path': {'srcjar3.srcjar'}
        }
        self.split_projs = source_splitter.ProjectSplitter(projects)

    def tearDown(self):
        """Clear the testdata related path."""
        self.split_projs = None
        shutil.rmtree(ProjectSplitterUnittest._TEST_DIR)

    def test_init(self):
        """Test initialize the attributes."""
        self.assertEqual(len(self.split_projs._projects), 3)

    @mock.patch.object(source_splitter.ProjectSplitter,
                       '_remove_duplicate_sources')
    @mock.patch.object(source_splitter.ProjectSplitter,
                       '_keep_local_sources')
    @mock.patch.object(source_splitter.ProjectSplitter,
                       '_collect_all_srcs')
    def test_revise_source_folders(self, mock_copy_srcs, mock_keep_srcs,
                                   mock_remove_srcs):
        """Test revise_source_folders."""
        self.split_projs.revise_source_folders()
        self.assertTrue(mock_copy_srcs.called)
        self.assertTrue(mock_keep_srcs.called)
        self.assertTrue(mock_remove_srcs.called)

    def test_collect_all_srcs(self):
        """Test _collect_all_srcs."""
        self.split_projs._collect_all_srcs()
        sources = self.split_projs._all_srcs
        expected_srcs = {'src1', 'src2', 'src2/src3', 'src2/lib', 'other1',
                         'other2'}
        self.assertEqual(sources['source_folder_path'], expected_srcs)
        expected_tests = {'src1/tests', 'src2/tests', 'src2/src3/tests'}
        self.assertEqual(sources['test_folder_path'], expected_tests)

    def test_keep_local_sources(self):
        """Test _keep_local_sources."""
        self.split_projs._collect_all_srcs()
        self.split_projs._keep_local_sources()
        srcs1 = self.split_projs._projects[0].source_path
        srcs2 = self.split_projs._projects[1].source_path
        srcs3 = self.split_projs._projects[2].source_path
        all_srcs = self.split_projs._all_srcs
        expected_srcs1 = {'src1'}
        expected_srcs2 = {'src2', 'src2/src3', 'src2/lib'}
        expected_srcs3 = {'src2/src3'}
        expected_all_srcs = {'other1', 'other2'}
        expected_all_tests = set()
        self.assertEqual(srcs1['source_folder_path'], expected_srcs1)
        self.assertEqual(srcs2['source_folder_path'], expected_srcs2)
        self.assertEqual(srcs3['source_folder_path'], expected_srcs3)
        self.assertEqual(all_srcs['source_folder_path'], expected_all_srcs)
        self.assertEqual(all_srcs['test_folder_path'], expected_all_tests)

    def test_remove_duplicate_sources(self):
        """Test _remove_duplicate_sources."""
        self.split_projs._collect_all_srcs()
        self.split_projs._keep_local_sources()
        self.split_projs._remove_duplicate_sources()
        srcs2 = self.split_projs._projects[1].source_path
        srcs3 = self.split_projs._projects[2].source_path
        expected_srcs2 = {'src2', 'src2/lib'}
        expected_srcs3 = {'src2/src3'}
        self.assertEqual(srcs2['source_folder_path'], expected_srcs2)
        self.assertEqual(srcs3['source_folder_path'], expected_srcs3)

    def test_get_dependencies(self):
        """Test get_dependencies."""
        self.split_projs.get_dependencies()
        dep1 = ['framework-all', 'src2', 'dependencies']
        dep2 = ['framework-all', 'dependencies']
        dep3 = ['framework-all', 'src2', 'dependencies']
        self.assertEqual(self.split_projs._projects[0].dependencies, dep1)
        self.assertEqual(self.split_projs._projects[1].dependencies, dep2)
        self.assertEqual(self.split_projs._projects[2].dependencies, dep3)


if __name__ == '__main__':
    unittest.main()
