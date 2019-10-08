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

"""Unittests for project_info."""

import collections
import os
import shutil
import tempfile
import unittest
from unittest import mock

from aidegen import unittest_constants
from aidegen.lib import common_util
from aidegen.lib import project_info
from aidegen.lib import project_config

_MODULE_INFO = {
    'm1': {
        'class': ['JAVA_LIBRARIES'],
        'dependencies': ['m2', 'm6'],
        'path': ['m1']
    },
    'm2': {
        'class': ['JAVA_LIBRARIES'],
        'dependencies': ['m3', 'm4']
    },
    'm3': {
        'class': ['JAVA_LIBRARIES'],
        'dependencies': []
    },
    'm4': {
        'class': ['JAVA_LIBRARIES'],
        'dependencies': ['m6']
    },
    'm5': {
        'class': ['JAVA_LIBRARIES'],
        'dependencies': []
    },
    'm6': {
        'class': ['JAVA_LIBRARIES'],
        'dependencies': ['m2']
    },
}
_EXPECT_DEPENDENT_MODULES = {
    'm1': {
        'class': ['JAVA_LIBRARIES'],
        'dependencies': ['m2', 'm6'],
        'path': ['m1'],
        'depth': 0
    },
    'm2': {
        'class': ['JAVA_LIBRARIES'],
        'dependencies': ['m3', 'm4'],
        'depth': 1
    },
    'm3': {
        'class': ['JAVA_LIBRARIES'],
        'dependencies': [],
        'depth': 2
    },
    'm4': {
        'class': ['JAVA_LIBRARIES'],
        'dependencies': ['m6'],
        'depth': 2
    },
    'm6': {
        'class': ['JAVA_LIBRARIES'],
        'dependencies': ['m2'],
        'depth': 1
    },
}


# pylint: disable=protected-access
# pylint: disable=invalid-name
class ProjectInfoUnittests(unittest.TestCase):
    """Unit tests for project_info.py"""

    def setUp(self):
        """Initialize arguments for ProjectInfo."""
        self.args = mock.MagicMock()
        self.args.module_name = 'm1'
        self.args.project_path = ''

    @mock.patch('atest.module_info.ModuleInfo')
    def test_get_dep_modules(self, mock_module_info):
        """Test get_dep_modules recursively find dependent modules."""
        mock_module_info.name_to_module_info = _MODULE_INFO
        mock_module_info.is_module.return_value = True
        mock_module_info.get_paths.return_value = ['m1']
        mock_module_info.get_module_names.return_value = ['m1']
        project_info.ProjectInfo.modules_info = mock_module_info
        proj_info = project_info.ProjectInfo(self.args.module_name, False)
        self.assertEqual(proj_info.dep_modules, _EXPECT_DEPENDENT_MODULES)

    @mock.patch.object(common_util, 'get_android_root_dir')
    def test_get_target_name(self, mock_get_root):
        """Test _get_target_name with different conditions."""
        mock_get_root.return_value = unittest_constants.TEST_DATA_PATH
        self.assertEqual(
            project_info.ProjectInfo._get_target_name(
                unittest_constants.TEST_MODULE,
                unittest_constants.TEST_DATA_PATH),
            os.path.basename(unittest_constants.TEST_DATA_PATH))
        self.assertEqual(
            project_info.ProjectInfo._get_target_name(
                unittest_constants.TEST_MODULE, unittest_constants.TEST_PATH),
            unittest_constants.TEST_MODULE)

    # pylint: disable=too-many-locals
    @mock.patch.object(common_util, 'get_android_root_dir')
    @mock.patch('atest.module_info.ModuleInfo')
    @mock.patch('atest.atest_utils.build')
    def test_locate_source(self, mock_atest_utils_build, mock_module_info,
                           mock_get_root):
        """Test locate_source handling."""
        mock_atest_utils_build.build.return_value = True
        test_root_path = os.path.join(tempfile.mkdtemp(), 'test')
        shutil.copytree(unittest_constants.TEST_DATA_PATH, test_root_path)
        mock_get_root.return_value = test_root_path
        generated_jar = ('out/soong/.intermediates/packages/apps/test/test/'
                         'android_common/generated.jar')
        locate_module_info = dict(unittest_constants.MODULE_INFO)
        locate_module_info['srcs'].extend(
            [('out/soong/.intermediates/packages/apps/test/test/android_common/'
              'gen/test.srcjar')])
        locate_module_info['installed'] = [generated_jar]
        mock_module_info.is_module.return_value = True
        mock_module_info.get_paths.return_value = [
            unittest_constants.MODULE_PATH
        ]
        mock_module_info.get_module_names.return_value = [
            unittest_constants.TEST_MODULE
        ]
        Args = collections.namedtuple(
            'Args',
            'no_launch depth ide skip_build android_tree targets verbose')
        args = Args(True, 0, ['j'], True, False,
                    [unittest_constants.TEST_MODULE], False)
        project_info.ProjectInfo.config = project_config.ProjectConfig(args)
        project_info_obj = project_info.ProjectInfo(mock_module_info)
        project_info_obj.dep_modules = {
            unittest_constants.TEST_MODULE: locate_module_info
        }
        project_info_obj._init_source_path()
        # Show warning when the jar not exists after build the module.
        result_jar = set()
        project_info_obj.locate_source()
        self.assertEqual(project_info_obj.source_path['jar_path'], result_jar)

        # Test on jar exists.
        jar_abspath = os.path.join(test_root_path, generated_jar)
        result_jar = set([generated_jar])
        try:
            open(jar_abspath, 'w').close()
            project_info_obj.locate_source()
            self.assertEqual(project_info_obj.source_path['jar_path'],
                             result_jar)
        finally:
            shutil.rmtree(test_root_path)

        # Test collects source and test folders.
        result_source = set(['packages/apps/test/src/main/java'])
        result_test = set(['packages/apps/test/tests'])
        self.assertEqual(project_info_obj.source_path['source_folder_path'],
                         result_source)
        self.assertEqual(project_info_obj.source_path['test_folder_path'],
                         result_test)

        # Test loading jar from dependencies parameter.
        default_jar = os.path.join(unittest_constants.MODULE_PATH, 'test.jar')
        locate_module_info['dependencies'] = [default_jar]
        result_jar = set([generated_jar, default_jar])
        project_info_obj.locate_source()
        self.assertEqual(project_info_obj.source_path['jar_path'], result_jar)

    def test_separate_build_target(self):
        """Test separate_build_target."""
        test_list = ['1', '22', '333', '4444', '55555', '1', '7777777']
        target = []
        sample = [['1', '22', '333'], ['4444'], ['55555', '1'], ['7777777']]
        for start, end in iter(
                project_info._separate_build_targets(test_list, 9)):
            target.append(test_list[start:end])
        self.assertEqual(target, sample)

    @mock.patch.object(project_info.ProjectInfo, 'locate_source')
    @mock.patch('atest.module_info.ModuleInfo')
    def test_rebuild_jar_once(self, mock_module_info, mock_locate_source):
        """Test rebuild the jar/srcjar only one time."""
        mock_module_info.get_paths.return_value = ['m1']
        project_info.ProjectInfo.modules_info = mock_module_info
        proj_info = project_info.ProjectInfo(self.args.module_name, False)
        proj_info.locate_source(build=False)
        self.assertEqual(mock_locate_source.call_count, 1)
        proj_info.locate_source(build=True)
        self.assertEqual(mock_locate_source.call_count, 2)


if __name__ == '__main__':
    unittest.main()
