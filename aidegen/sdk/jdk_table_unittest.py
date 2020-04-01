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

"""Unittests for JDKTableXML class."""

import os
import shutil
import tempfile
import unittest

from unittest import mock
from xml.etree import ElementTree

from aidegen.sdk import android_sdk
from aidegen.sdk import jdk_table


# pylint: disable=protected-access
class JDKTableXMLUnittests(unittest.TestCase):
    """Unit tests for JDKTableXML class."""

    _JDK_TABLE_XML = 'jdk.table.xml'
    _CONFIG_FILE = '/path/to/jdk.table.xml'
    _JDK_CONTENT = '<jdk />'
    _JDK_PATH = '/path/to/JDK'
    _DEFULAT_ANDROID_SDK_PATH = '/path/to/Android/SDK'

    def setUp(self):
        """Prepare the JDKTableXML class."""
        JDKTableXMLUnittests._TEST_DIR = tempfile.mkdtemp()
        self.jdk_table_xml = jdk_table.JDKTableXML(
            self._CONFIG_FILE, self._JDK_CONTENT, self._JDK_PATH,
            self._DEFULAT_ANDROID_SDK_PATH)

    def tearDown(self):
        """Clear the JDKTableXML class."""
        self.jdk_table_xml = None
        shutil.rmtree(JDKTableXMLUnittests._TEST_DIR)

    @mock.patch('os.path.exists')
    @mock.patch.object(ElementTree, 'parse')
    def test_init(self, mock_parse, mock_exists):
        """Test initialize the attributes."""
        self.assertEqual(self.jdk_table_xml._platform_version, None)
        self.assertEqual(self.jdk_table_xml._android_sdk_version, None)
        self.assertEqual(self.jdk_table_xml._modify_config, False)
        mock_exists.return_value = True
        mock_parse.return_value = None
        jdk_table.JDKTableXML(None, None, None, None)
        self.assertTrue(mock_parse.called)
        mock_exists.return_value = False
        jdk_table.JDKTableXML(None, None, None, None)
        self.assertTrue(mock_parse.called)

    def test_android_sdk_version(self):
        """Test android_sdk_version."""
        self.assertEqual(self.jdk_table_xml.android_sdk_version, None)

    def test_check_structure(self):
        """Test _check_structure."""
        tmp_file = os.path.join(self._TEST_DIR, self._JDK_TABLE_XML)
        xml_str = ('<application>\n</application>')
        with open(tmp_file, 'w') as tmp_jdk_xml:
            tmp_jdk_xml.write(xml_str)
        self.jdk_table_xml._xml = ElementTree.parse(tmp_file)
        self.assertFalse(self.jdk_table_xml._check_structure())
        xml_str = ('<application>\n'
                   '  <component>\n'
                   '  </component>\n'
                   '</application>')
        with open(tmp_file, 'w') as tmp_jdk_xml:
            tmp_jdk_xml.write(xml_str)
        self.jdk_table_xml._xml = ElementTree.parse(tmp_file)
        self.assertFalse(self.jdk_table_xml._check_structure())
        xml_str = ('<application>\n'
                   '  <component name="ProjectJdkTable">\n'
                   '  </component>\n'
                   '</application>')
        with open(tmp_file, 'w') as tmp_jdk_xml:
            tmp_jdk_xml.write(xml_str)
        self.jdk_table_xml._xml = ElementTree.parse(tmp_file)
        self.assertTrue(self.jdk_table_xml._check_structure())

    @mock.patch.object(jdk_table.JDKTableXML, '_check_jdk18_in_xml')
    def test_generate_jdk_config_string(self, mock_jdk_exists):
        """Test _generate_jdk_config_string."""
        mock_jdk_exists.return_value = True
        self.jdk_table_xml._generate_jdk_config_string()
        self.assertFalse(self.jdk_table_xml._modify_config)
        mock_jdk_exists.return_value = False
        expected_result = (b'<application>\n'
                           b'  <component name="ProjectJdkTable">\n'
                           b'    <jdk />\n'
                           b'  </component>\n'
                           b'</application>')
        self.jdk_table_xml._generate_jdk_config_string()
        test_result = ElementTree.tostring(self.jdk_table_xml._xml.getroot())
        self.assertTrue(self.jdk_table_xml._modify_config)
        self.assertEqual(test_result, expected_result)
        xml_str = ('<application>\n'
                   '  <component name="ProjectJdkTable">\n'
                   '    <jdk>\n'
                   '      <name value="test" />\n'
                   '      <type value="JavaSDK" />\n'
                   '    </jdk>\n'
                   '  </component>\n'
                   '</application>')
        expected_result = (b'<application>\n'
                           b'  <component name="ProjectJdkTable">\n'
                           b'    <jdk>\n'
                           b'      <name value="test" />\n'
                           b'      <type value="JavaSDK" />\n'
                           b'    </jdk>\n'
                           b'    <jdk />\n'
                           b'  </component>\n'
                           b'</application>')
        tmp_file = os.path.join(self._TEST_DIR, self._JDK_TABLE_XML)
        with open(tmp_file, 'w') as tmp_jdk_xml:
            tmp_jdk_xml.write(xml_str)
        self.jdk_table_xml._xml = ElementTree.parse(tmp_file)
        self.jdk_table_xml._generate_jdk_config_string()
        test_result = ElementTree.tostring(self.jdk_table_xml._xml.getroot())
        self.assertEqual(test_result, expected_result)

    @mock.patch.object(ElementTree.ElementTree, 'write')
    @mock.patch.object(jdk_table.JDKTableXML, '_generate_jdk_config_string')
    @mock.patch.object(jdk_table.JDKTableXML, '_generate_sdk_config_string')
    @mock.patch.object(jdk_table.JDKTableXML, '_check_structure')
    def test_config_jdk_table_xml(self, mock_check_structure, mock_gen_jdk,
                                  mock_gen_sdk, mock_xml_write):
        """Test config_jdk_table_xml."""
        mock_check_structure.return_value = True
        self.jdk_table_xml.config_jdk_table_xml()
        self.assertTrue(mock_gen_jdk.called)
        self.assertTrue(mock_gen_sdk.called)
        self.jdk_table_xml._modify_config = False
        self.jdk_table_xml.config_jdk_table_xml()
        self.assertFalse(mock_xml_write.called)
        self.jdk_table_xml._modify_config = True
        self.jdk_table_xml._android_sdk_version = 'test'
        self.jdk_table_xml.config_jdk_table_xml()
        self.assertTrue(mock_xml_write.called)
        mock_check_structure.return_value = False
        self.assertFalse(self.jdk_table_xml.config_jdk_table_xml())

    def test_check_jdk18_in_xml(self):
        """Test _check_jdk18_in_xml."""
        # Normal case.
        xml_str = ('<test><jdk><name value="JDK18" /><type value="JavaSDK" />'
                   '</jdk></test>')
        self.jdk_table_xml._xml = ElementTree.fromstring(xml_str)
        self.assertTrue(self.jdk_table_xml._check_jdk18_in_xml())

        # Incorrect JDK name.
        xml_str = ('<test><jdk><name value="test" /><type value="JavaSDK" />'
                   '</jdk></test>')
        self.jdk_table_xml._xml = ElementTree.fromstring(xml_str)
        self.assertFalse(self.jdk_table_xml._check_jdk18_in_xml())

        # No type.
        xml_str = ('<test><jdk><name value="test" /></jdk></test>')
        self.jdk_table_xml._xml = ElementTree.fromstring(xml_str)
        self.assertFalse(self.jdk_table_xml._check_jdk18_in_xml())

    @mock.patch.object(android_sdk.AndroidSDK, 'is_android_sdk_path')
    def test_check_android_sdk_in_xml(self, mock_is_android_sdk):
        """Test _check_android_sdk_in_xml."""
        self.jdk_table_xml._sdk._platform_mapping = {
            'android-29': {
                'api_level': 29,
                'code_name': '29',
            },
        }
        mock_is_android_sdk.return_value = True

        # Not an Android SDK tag.
        xml_str = ('<test><jdk><name value="JDK18" /><type value="JavaSDK" />'
                   '</jdk></test>')
        self.jdk_table_xml._xml = ElementTree.fromstring(xml_str)
        self.assertFalse(self.jdk_table_xml._check_android_sdk_in_xml())

        # No homePath.
        xml_str = ('<test><jdk><name value="Android SDK 29 platform" />'
                   '<type value="Android SDK" />'
                   '<additional jdk="JDK18" sdk="android-29" />'
                   '</jdk></test>')
        self.jdk_table_xml._xml = ElementTree.fromstring(xml_str)
        self.assertFalse(self.jdk_table_xml._check_android_sdk_in_xml())

        # The platform version android-28 does not exist in platform mapping.
        xml_str = ('<test><jdk><name value="Android SDK 28 platform" />'
                   '<type value="Android SDK" />'
                   '<homePath value="/path/to/Android/SDK" />'
                   '<additional jdk="JDK18" sdk="android-28" />'
                   '</jdk></test>')
        self.jdk_table_xml._xml = ElementTree.fromstring(xml_str)
        self.assertFalse(self.jdk_table_xml._check_android_sdk_in_xml())

        # Normal case.
        xml_str = ('<test><jdk><name value="Android SDK 29 platform" />'
                   '<type value="Android SDK" />'
                   '<homePath value="/path/to/Android/SDK" />'
                   '<additional jdk="JDK18" sdk="android-29" />'
                   '</jdk></test>')
        self.jdk_table_xml._xml = ElementTree.fromstring(xml_str)
        self.assertTrue(self.jdk_table_xml._check_android_sdk_in_xml())

        # Incorrect Android SDK path.
        mock_is_android_sdk.return_value = False
        self.jdk_table_xml._xml = ElementTree.fromstring(xml_str)
        self.assertFalse(self.jdk_table_xml._check_android_sdk_in_xml())


if __name__ == '__main__':
    unittest.main()
