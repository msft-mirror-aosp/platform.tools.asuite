#!/usr/bin/env python3
#
# Copyright 2020, The Android Open Source Project
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

"""Unittests for IML class."""

import os
import shutil
import tempfile
import unittest
from unittest import mock

from aidegen.lib import common_util
from aidegen.idea import iml


# pylint: disable=protected-access
class IMLGenUnittests(unittest.TestCase):
    """Unit tests for IMLGenerator class."""

    _TEST_DIR = None

    def setUp(self):
        """Prepare the testdata related path."""
        IMLGenUnittests._TEST_DIR = tempfile.mkdtemp()
        module = {
            "module_name": "test",
            "path": [
                "a/b"
            ],
            "srcjars": [
                'x/y.srcjar'
            ]
        }
        with mock.patch.object(common_util, 'get_android_root_dir') as obj:
            obj.return_value = IMLGenUnittests._TEST_DIR
            self.iml = iml.IMLGenerator(module)

    def tearDown(self):
        """Clear the testdata related path."""
        self.iml = None
        shutil.rmtree(IMLGenUnittests._TEST_DIR)

    def test_init(self):
        """Test initialize the attributes."""
        self.assertEqual(self.iml._mod_info['module_name'], 'test')

    @mock.patch.object(common_util, 'get_android_root_dir')
    def test_iml_path(self, mock_root_path):
        """Test iml_path."""
        mock_root_path.return_value = IMLGenUnittests._TEST_DIR
        iml_path = os.path.join(IMLGenUnittests._TEST_DIR, 'a/b/test.iml')
        self.assertEqual(self.iml.iml_path, iml_path)

    @mock.patch.object(common_util, 'get_android_root_dir')
    def test_create(self, mock_root_path):
        """Test create."""
        mock_root_path.return_value = IMLGenUnittests._TEST_DIR
        srcjar_path = os.path.join(IMLGenUnittests._TEST_DIR, 'x/y.srcjar')
        expected = """<?xml version="1.0" encoding="UTF-8"?>
<module type="JAVA_MODULE" version="4">
    <component name="NewModuleRootManager" inherit-compiler-output="true">
        <exclude-output />
        <content url="jar://{SRCJAR}!/">
            <sourceFolder url="jar://{SRCJAR}!/" isTestSource="False" />
        </content>
        <orderEntry type="sourceFolder" forTests="false" />
        <orderEntry type="inheritedJdk" />
    </component>
</module>
""".format(SRCJAR=srcjar_path)
        self.iml.create({'srcjars': True})
        gen_iml = os.path.join(IMLGenUnittests._TEST_DIR,
                               self.iml._mod_info['path'][0],
                               self.iml._mod_info['module_name'] + '.iml')
        result = common_util.read_file_content(gen_iml)
        self.assertEqual(result, expected)

    @mock.patch.object(iml.IMLGenerator, '_create_iml')
    @mock.patch.object(iml.IMLGenerator, '_generate_srcjars')
    def test_skip_create_iml(self, mock_gen_srcjars, mock_create_iml):
        """Test skipping create_iml."""
        self.iml.create({'srcjars': False})
        self.assertFalse(mock_gen_srcjars.called)
        self.assertFalse(mock_create_iml.called)


if __name__ == '__main__':
    unittest.main()
