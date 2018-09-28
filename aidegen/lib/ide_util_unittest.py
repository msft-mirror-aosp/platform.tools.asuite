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

import aidegen.unittest_constants as uc


#pylint: disable=protected-access
class IdeUtilUnittests(unittest.TestCase):
    """Unit tests for ide_util.py."""

    _TEST_PRJ_PATH1 = ''
    _TEST_PRJ_PATH2 = ''

    def setUp(self):
        """Prepare the testdata related path."""
        IdeUtilUnittests._TEST_PRJ_PATH1 = os.path.join(uc.TESTDATA_PATH,
                                                        'android_facet.iml')
        IdeUtilUnittests._TEST_PRJ_PATH2 = os.path.join(uc.TESTDATA_PATH,
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

    @mock.patch('subprocess.check_output', return_value=uc.IDEA_SH_FIND_NONE)
    def test_get_intellij_sh_with_none(self, mock_check_out):
        """Test with the cmd return none, test should have exception."""
        mock_check_out.return_value = uc.IDEA_SH_FIND_NONE
        with self.assertRaises(IndexError):
            ide_util._get_intellij_sh()

    @mock.patch('subprocess.check_output', return_value=uc.IDEA_SH_FIND)
    def test_get_intellij_sh_got_data(self, mock_check_out):
        """Test with the cmd return useful sh, test should not have except."""
        mock_check_out.return_value = uc.IDEA_SH_FIND
        self.assertEqual(uc.SH_GODEN_SAMPLE, ide_util._get_intellij_sh())

    def test_run_intellij_sh(self):
        """Follow the target behavior, with sh to show UI, else raise err."""
        sh_path = ide_util._get_intellij_sh()
        if sh_path:
            ide_util._run_intellij_sh(IdeUtilUnittests._TEST_PRJ_PATH1)
        else:
            self.assertRaises(cmd_err)


if __name__ == '__main__':
    unittest.main()
