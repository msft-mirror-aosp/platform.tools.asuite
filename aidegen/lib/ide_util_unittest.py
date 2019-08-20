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


"""Unittests for ide_util."""

import os
import shutil
import subprocess
import tempfile
import unittest

from unittest import mock

from aidegen import unittest_constants
from aidegen.lib import android_dev_os
from aidegen.lib import ide_util
from aidegen.lib import sdk_config


# pylint: disable=protected-access
# pylint: disable-msg=too-many-arguments
class IdeUtilUnittests(unittest.TestCase):
    """Unit tests for ide_util.py."""

    _TEST_PRJ_PATH1 = ''
    _TEST_PRJ_PATH2 = ''
    _TEST_PRJ_PATH3 = ''
    _TEST_PRJ_PATH4 = ''
    _MODULE_XML_SAMPLE = ''

    def setUp(self):
        """Prepare the testdata related path."""
        IdeUtilUnittests._TEST_PRJ_PATH1 = os.path.join(
            unittest_constants.TEST_DATA_PATH, 'android_facet.iml')
        IdeUtilUnittests._TEST_PRJ_PATH2 = os.path.join(
            unittest_constants.TEST_DATA_PATH, 'project/test.java')
        IdeUtilUnittests._TEST_PRJ_PATH3 = unittest_constants.TEST_DATA_PATH
        IdeUtilUnittests._TEST_PRJ_PATH4 = os.path.join(
            unittest_constants.TEST_DATA_PATH, '.idea')
        IdeUtilUnittests._MODULE_XML_SAMPLE = os.path.join(
            unittest_constants.TEST_DATA_PATH, 'modules.xml')

    def tearDown(self):
        """Clear the testdata related path."""
        IdeUtilUnittests._TEST_PRJ_PATH1 = ''
        IdeUtilUnittests._TEST_PRJ_PATH2 = ''
        IdeUtilUnittests._TEST_PRJ_PATH3 = ''
        IdeUtilUnittests._TEST_PRJ_PATH4 = ''

    def test_is_intellij_project(self):
        """Test _is_intellij_project."""
        self.assertFalse(
            ide_util._is_intellij_project(IdeUtilUnittests._TEST_PRJ_PATH2))
        self.assertTrue(
            ide_util._is_intellij_project(IdeUtilUnittests._TEST_PRJ_PATH1))
        self.assertTrue(
            ide_util._is_intellij_project(IdeUtilUnittests._TEST_PRJ_PATH3))
        self.assertFalse(
            ide_util._is_intellij_project(IdeUtilUnittests._TEST_PRJ_PATH4))

    @mock.patch('glob.glob', return_value=unittest_constants.IDEA_SH_FIND_NONE)
    def test_get_intellij_sh_none(self, mock_glob):
        """Test with the cmd return none, test result should be None."""
        mock_glob.return_value = unittest_constants.IDEA_SH_FIND_NONE
        self.assertEqual(
            None,
            ide_util._get_intellij_version_path(
                ide_util.IdeLinuxIntelliJ()._ls_ce_path))
        self.assertEqual(
            None,
            ide_util._get_intellij_version_path(
                ide_util.IdeLinuxIntelliJ()._ls_ue_path))

    @mock.patch('builtins.input')
    @mock.patch('glob.glob', return_value=unittest_constants.IDEA_SH_FIND)
    def test_ask_preference(self, mock_glob, mock_input):
        """Ask users' preference, the result should be equal to test data."""
        mock_glob.return_value = unittest_constants.IDEA_SH_FIND
        mock_input.return_value = '1'
        self.assertEqual(
            ide_util._ask_preference(unittest_constants.IDEA_SH_FIND),
            unittest_constants.IDEA_SH_FIND[0])
        mock_input.return_value = '2'
        self.assertEqual(
            ide_util._ask_preference(unittest_constants.IDEA_SH_FIND),
            unittest_constants.IDEA_SH_FIND[1])

    @unittest.skip('Skip to use real command to launch IDEA.')
    def test_run_intellij_sh_in_linux(self):
        """Follow the target behavior, with sh to show UI, else raise err."""
        sh_path = ide_util.IdeLinuxIntelliJ()._get_script_from_system()
        if sh_path:
            ide_util_obj = ide_util.IdeUtil()
            ide_util_obj.config_ide(IdeUtilUnittests._TEST_PRJ_PATH1)
            ide_util_obj.launch_ide()
        else:
            self.assertRaises(subprocess.CalledProcessError)

    @mock.patch.object(ide_util, '_get_linux_ide')
    @mock.patch.object(ide_util, '_get_mac_ide')
    def test_get_ide(self, mock_mac, mock_linux):
        """Test if _get_ide calls the correct respective functions."""
        ide_util._get_ide(None, 'j', False, is_mac=True)
        self.assertTrue(mock_mac.called)
        ide_util._get_ide(None, 'j', False, is_mac=False)
        self.assertTrue(mock_linux.called)

    @mock.patch.object(ide_util.IdeIntelliJ, '_get_preferred_version')
    def test_get_mac_and_linux_ide(self, mock_preference):
        """Test if _get_mac_ide and _get_linux_ide return correct IDE class."""
        mock_preference.return_value = None
        self.assertIsInstance(ide_util._get_mac_ide(), ide_util.IdeMacIntelliJ)
        self.assertIsInstance(ide_util._get_mac_ide(None, 's'),
                              ide_util.IdeMacStudio)
        self.assertIsInstance(ide_util._get_mac_ide(None, 'e'),
                              ide_util.IdeMacEclipse)
        self.assertIsInstance(ide_util._get_linux_ide(),
                              ide_util.IdeLinuxIntelliJ)
        self.assertIsInstance(
            ide_util._get_linux_ide(None, 's'), ide_util.IdeLinuxStudio)
        self.assertIsInstance(
            ide_util._get_linux_ide(None, 'e'), ide_util.IdeLinuxEclipse)

    @mock.patch.object(ide_util, '_get_script_from_input_path')
    @mock.patch.object(ide_util.IdeIntelliJ, '_get_script_from_system')
    def test_init_ideintellij(self, mock_sys, mock_input):
        """Test IdeIntelliJ's __init__ method."""
        ide_util.IdeLinuxIntelliJ()
        self.assertTrue(mock_sys.called)
        ide_util.IdeMacIntelliJ()
        self.assertTrue(mock_sys.called)
        ide_util.IdeLinuxIntelliJ('some_path')
        self.assertTrue(mock_input.called)
        ide_util.IdeMacIntelliJ('some_path')
        self.assertTrue(mock_input.called)

    @mock.patch.object(ide_util.IdeIntelliJ, '_get_preferred_version')
    @mock.patch.object(sdk_config.SDKConfig, '_android_sdk_exists')
    @mock.patch.object(sdk_config.SDKConfig, '_target_jdk_exists')
    @mock.patch.object(ide_util.IdeIntelliJ, '_get_config_root_paths')
    @mock.patch.object(ide_util.IdeBase, 'apply_optional_config')
    def test_config_ide(self, mock_config, mock_paths, mock_jdk, mock_sdk,
                        mock_preference):
        """Test IDEA, IdeUtil.config_ide won't call base none implement api."""
        # Mock SDkConfig flow to not to generate real jdk config file.
        mock_preference.return_value = None
        mock_jdk.return_value = True
        mock_sdk.return_value = True
        test_path = os.path.join(tempfile.mkdtemp())
        module_path = os.path.join(test_path, 'test')
        idea_path = os.path.join(module_path, '.idea')
        os.makedirs(idea_path)
        shutil.copy(IdeUtilUnittests._MODULE_XML_SAMPLE, idea_path)
        try:
            util_obj = ide_util.IdeUtil()
            util_obj.config_ide(module_path)
            self.assertFalse(mock_config.called)
            self.assertFalse(mock_paths.called)
        finally:
            shutil.rmtree(test_path)

    @mock.patch.object(ide_util, '_get_script_from_input_path')
    @mock.patch.object(ide_util, '_get_script_from_internal_path')
    def test_get_linux_config_1(self, mock_path, mock_path_2):
        """Test to get unique config path for linux IDEA case."""
        if (not android_dev_os.AndroidDevOS.MAC ==
                android_dev_os.AndroidDevOS.get_os_type()):
            mock_path.return_value = '/opt/intellij-ce-2018.3/bin/idea.sh'
            mock_path_2.return_value = '/opt/intellij-ce-2018.3/bin/idea.sh'
            ide_obj = ide_util.IdeLinuxIntelliJ('default_path')
            self.assertEqual(1, len(ide_obj._get_config_root_paths()))
        else:
            self.assertTrue((android_dev_os.AndroidDevOS.MAC ==
                             android_dev_os.AndroidDevOS.get_os_type()))

    @mock.patch('glob.glob')
    @mock.patch.object(ide_util, '_get_script_from_input_path')
    @mock.patch.object(ide_util, '_get_script_from_internal_path')
    def test_get_linux_config_2(self, mock_path, mock_path_2, mock_filter):
        """Test to get unique config path for linux IDEA case."""
        if (not android_dev_os.AndroidDevOS.MAC ==
                android_dev_os.AndroidDevOS.get_os_type()):
            mock_path.return_value = '/opt/intelliJ-ce-2018.3/bin/idea.sh'
            mock_path_2.return_value = '/opt/intelliJ-ce-2018.3/bin/idea.sh'
            ide_obj = ide_util.IdeLinuxIntelliJ()
            mock_filter.called = False
            ide_obj._get_config_root_paths()
            self.assertFalse(mock_filter.called)
        else:
            self.assertTrue((android_dev_os.AndroidDevOS.MAC ==
                             android_dev_os.AndroidDevOS.get_os_type()))

    def test_get_mac_config_root_paths(self):
        """Return None if there's no install path."""
        if (android_dev_os.AndroidDevOS.MAC ==
                android_dev_os.AndroidDevOS.get_os_type()):
            mac_ide = ide_util.IdeMacIntelliJ()
            mac_ide._installed_path = None
            self.assertIsNone(mac_ide._get_config_root_paths())
        else:
            self.assertFalse((android_dev_os.AndroidDevOS.MAC ==
                              android_dev_os.AndroidDevOS.get_os_type()))

    @mock.patch('glob.glob')
    @mock.patch.object(ide_util, '_get_script_from_input_path')
    @mock.patch.object(ide_util, '_get_script_from_internal_path')
    def test_get_linux_config_root(self, mock_path_1, mock_path_2, mock_filter):
        """Test to go filter logic for self download case."""
        mock_path_1.return_value = '/usr/tester/IDEA/IC2018.3.3/bin'
        mock_path_2.return_value = '/usr/tester/IDEA/IC2018.3.3/bin'
        ide_obj = ide_util.IdeLinuxIntelliJ()
        mock_filter.reset()
        ide_obj._get_config_root_paths()
        self.assertTrue(mock_filter.called)

    @mock.patch.object(sdk_config.SDKConfig, '__init__')
    @mock.patch.object(ide_util.IdeIntelliJ, '_get_config_root_paths')
    def test_apply_optional_config(self, mock_path, mock_conf):
        """Test basic logic of _apply_optional_config."""
        with mock.patch.object(ide_util, 'IdeIntelliJ') as obj:
            obj._installed_path = None
            obj.apply_optional_config()
            self.assertFalse(mock_path.called)

            obj.reset()
            obj._installed_path = 'default_path'
            mock_path.return_value = ['path1', 'path2']
            obj._IDE_JDK_TABLE_PATH = '/JDK_path'

            obj.apply_optional_config()
            self.assertTrue(mock_conf.called_with('path1/JDK_path'))
            self.assertTrue(mock_conf.called_with('path2/JDK_path'))

    @mock.patch('os.path.realpath')
    @mock.patch('os.path.isfile')
    def test_merge_symbolic_version(self, mock_isfile, mock_realpath):
        """Test _merge_symbolic_version and _get_real_path."""
        symbolic_path = ide_util.IdeIntelliJ._SYMBOLIC_VERSIONS[0]
        original_path = 'intellij-ce-2019.1/bin/idea.sh'
        mock_isfile.return_value = True
        mock_realpath.return_value = original_path
        ide_obj = ide_util.IdeLinuxIntelliJ('default_path')
        merged_version = ide_obj._merge_symbolic_version(
            [symbolic_path, original_path])
        self.assertEqual(
            merged_version[0], symbolic_path + ' -> ' + original_path)
        self.assertEqual(
            ide_obj._get_real_path(merged_version[0]), symbolic_path)


if __name__ == '__main__':
    unittest.main()
