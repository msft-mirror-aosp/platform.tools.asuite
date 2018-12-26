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
import unittest
from unittest import mock

from subprocess import CalledProcessError as cmd_err
from aidegen.lib import ide_util
from aidegen.lib.ide_util import IdeIntelliJ
from aidegen.lib.ide_util import IdeLinuxEclipse
from aidegen.lib.ide_util import IdeLinuxIntelliJ
from aidegen.lib.ide_util import IdeLinuxStudio
from aidegen.lib.ide_util import IdeMacEclipse
from aidegen.lib.ide_util import IdeMacIntelliJ
from aidegen.lib.ide_util import IdeMacStudio
from aidegen.lib.ide_util import IdeUtil

import aidegen.unittest_constants as uc


#pylint: disable=protected-access
class IdeUtilUnittests(unittest.TestCase):
    """Unit tests for ide_util.py."""

    _TEST_PRJ_PATH1 = ''
    _TEST_PRJ_PATH2 = ''

    def setUp(self):
        """Prepare the testdata related path."""
        IdeUtilUnittests._TEST_PRJ_PATH1 = os.path.join(uc.TEST_DATA_PATH,
                                                        'android_facet.iml')
        IdeUtilUnittests._TEST_PRJ_PATH2 = os.path.join(uc.TEST_DATA_PATH,
                                                        'project/test.java')

    def tearDown(self):
        """Clear the testdata related path."""
        IdeUtilUnittests._TEST_PRJ_PATH1 = ''
        IdeUtilUnittests._TEST_PRJ_PATH2 = ''

    def test_is_intellij_project(self):
        """Test _is_intellij_project."""
        self.assertTrue(
            ide_util._is_intellij_project(IdeUtilUnittests._TEST_PRJ_PATH1))
        self.assertFalse(
            ide_util._is_intellij_project(IdeUtilUnittests._TEST_PRJ_PATH2))

    @mock.patch('glob.glob', return_value=uc.IDEA_SH_FIND_NONE)
    def test_get_intellij_sh_none(self, mock_glob):
        """Test with the cmd return none, test result should be None."""
        mock_glob.return_value = uc.IDEA_SH_FIND_NONE
        self.assertEqual(
            None,
            ide_util._get_intellij_version_path(IdeLinuxIntelliJ._LS_CE_PATH))
        self.assertEqual(
            None,
            ide_util._get_intellij_version_path(IdeLinuxIntelliJ._LS_UE_PATH))

    @mock.patch('builtins.input')
    @mock.patch('glob.glob', return_value=uc.IDEA_SH_FIND)
    def test_ask_preference(self, mock_glob, mock_input):
        """Ask users' preference, the result should be equal to test data."""
        mock_glob.return_value = uc.IDEA_SH_FIND
        mock_input.return_value = '1'
        self.assertEqual(
            ide_util._ask_preference(uc.IDEA_SH_FIND), uc.IDEA_SH_FIND[0])
        mock_input.return_value = '2'
        self.assertEqual(
            ide_util._ask_preference(uc.IDEA_SH_FIND), uc.IDEA_SH_FIND[1])

    @unittest.skip('Skip to use real command to launch IDEA.')
    def test_run_intellij_sh_in_linux(self):
        """Follow the target behavior, with sh to show UI, else raise err."""
        sh_path = IdeLinuxIntelliJ()._get_script_from_system()
        if sh_path:
            ide_util_obj = IdeUtil()
            ide_util_obj.launch_ide(IdeUtilUnittests._TEST_PRJ_PATH1)
        else:
            self.assertRaises(cmd_err)

    @mock.patch.object(ide_util, '_get_linux_ide')
    @mock.patch.object(ide_util, '_get_mac_ide')
    def test_get_ide(self, mock_mac, mock_linux):
        """Test if _get_ide calls the correct respective functions."""
        ide_util._get_ide(None, 'j', False, is_mac=True)
        self.assertTrue(mock_mac.called)
        ide_util._get_ide(None, 'j', False, is_mac=False)
        self.assertTrue(mock_linux.called)

    def test_get_mac_ide_and_get_linux_ide(self):
        """Test if _get_mac_ide and _get_linux_ide return correct IDE class."""
        self.assertIsInstance(ide_util._get_mac_ide(), IdeMacIntelliJ)
        self.assertIsInstance(ide_util._get_mac_ide(None, 's'), IdeMacStudio)
        self.assertIsInstance(ide_util._get_mac_ide(None, 'e'), IdeMacEclipse)
        self.assertIsInstance(ide_util._get_linux_ide(), IdeLinuxIntelliJ)
        self.assertIsInstance(
            ide_util._get_linux_ide(None, 's'), IdeLinuxStudio)
        self.assertIsInstance(
            ide_util._get_linux_ide(None, 'e'), IdeLinuxEclipse)

    @mock.patch.object(ide_util, '_get_script_from_input_path')
    @mock.patch.object(IdeIntelliJ, '_get_script_from_system')
    def test_init_ideintellij(self, mock_sys, mock_input):
        """Test IdeIntelliJ's __init__ method."""
        IdeIntelliJ()
        self.assertTrue(mock_sys.called)
        IdeIntelliJ('some_path')
        self.assertTrue(mock_input.called)

if __name__ == '__main__':
    unittest.main()
