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

import unittest
import xml.etree.ElementTree
from unittest import mock

from aidegen.lib import aidegen_metrics
from aidegen.lib import common_util
from aidegen.sdk import android_sdk
from aidegen.sdk import jdk_table


# pylint: disable=protected-access
class JDKTableXMLUnittests(unittest.TestCase):
    """Unit tests for JDKTableXML class."""

    _XML_CONTENT = ('<application>\n  <component name="ProjectJdkTable">\n'
                    '  </component>\n</application>\n')
    _CONFIG_FILE = '/path/to/jdk.table.xml'
    _JDK_CONTENT = '<jdk></jdk>'
    _JDK_PATH = '/path/to/JDK'
    _DEFULAT_ANDROID_SDK_PATH = '/path/to/Android/SDK'

    def setUp(self):
        """Prepare the JDKTableXML class."""
        self.jdk_table_xml = jdk_table.JDKTableXML(
            self._CONFIG_FILE, self._JDK_CONTENT, self._JDK_PATH,
            self._DEFULAT_ANDROID_SDK_PATH)
        self.jdk_table_xml._config_string = self._XML_CONTENT

    def tearDown(self):
        """Clear the JDKTableXML class."""
        self.jdk_table_xml = None

    @mock.patch('os.path.exists')
    @mock.patch.object(common_util, 'read_file_content')
    def test_init(self, mock_read_file_content, mock_exists):
        """Test initialize the attributes."""
        self.assertEqual(self.jdk_table_xml._config_string, self._XML_CONTENT)
        self.assertEqual(self.jdk_table_xml._platform_version, None)
        self.assertEqual(self.jdk_table_xml._android_sdk_version, None)
        self.assertEqual(self.jdk_table_xml._modify_config, False)
        mock_exists.return_value = True
        mock_read_file_content.return_value = '<test></test>'
        excepted_result = '<test></test>'
        test_object = jdk_table.JDKTableXML(None, None, None, None)
        self.assertEqual(test_object._config_string, excepted_result)

    def test_android_sdk_version(self):
        """Test android_sdk_version."""
        self.assertEqual(self.jdk_table_xml.android_sdk_version, None)

    @mock.patch.object(jdk_table.JDKTableXML, '_check_jdk18_in_xml')
    def test_generate_jdk_config_string(self, mock_jdk_exists):
        """Test _generate_jdk_config_string."""
        self.jdk_table_xml._config_string = self._XML_CONTENT
        mock_jdk_exists.return_value = True
        self.jdk_table_xml._generate_jdk_config_string()
        self.assertFalse(self.jdk_table_xml._modify_config)
        mock_jdk_exists.return_value = False
        expected_result = ('<application>\n  '
                           '<component name="ProjectJdkTable">\n'
                           '<jdk></jdk>  </component>\n</application>\n')
        self.jdk_table_xml._generate_jdk_config_string()
        self.assertTrue(self.jdk_table_xml._modify_config)
        self.assertEqual(self.jdk_table_xml._config_string, expected_result)

    @mock.patch.object(common_util, 'file_generate')
    @mock.patch.object(jdk_table.JDKTableXML, '_generate_jdk_config_string')
    @mock.patch.object(jdk_table.JDKTableXML, '_generate_sdk_config_string')
    def test_config_jdk_table_xml(self, mock_gen_jdk, mock_gen_sdk,
                                  mock_get_file):
        """Test config_jdk_table_xml."""
        self.jdk_table_xml.config_jdk_table_xml()
        self.assertTrue(mock_gen_jdk.called)
        self.assertTrue(mock_gen_sdk.called)
        self.jdk_table_xml._modify_config = False
        self.jdk_table_xml.config_jdk_table_xml()
        self.assertFalse(mock_get_file.called)
        self.jdk_table_xml._modify_config = True
        self.jdk_table_xml.config_jdk_table_xml()
        self.assertTrue(mock_get_file.called)

    def test_check_jdk18_in_xml(self):
        """Test _check_jdk18_in_xml."""
        # Normal case.
        xml_str = ('<test><jdk><name value="JDK18" /><type value="JavaSDK" />'
                   '</jdk></test>')
        self.jdk_table_xml._xml = xml.etree.ElementTree.fromstring(xml_str)
        self.assertTrue(self.jdk_table_xml._check_jdk18_in_xml())

        # Incorrect JDK name.
        xml_str = ('<test><jdk><name value="test" /><type value="JavaSDK" />'
                   '</jdk></test>')
        self.jdk_table_xml._xml = xml.etree.ElementTree.fromstring(xml_str)
        self.assertFalse(self.jdk_table_xml._check_jdk18_in_xml())

        # No type.
        xml_str = ('<test><jdk><name value="test" /></jdk></test>')
        self.jdk_table_xml._xml = xml.etree.ElementTree.fromstring(xml_str)
        self.assertFalse(self.jdk_table_xml._check_jdk18_in_xml())

    @mock.patch.object(aidegen_metrics, 'send_exception_metrics')
    @mock.patch.object(xml.etree.ElementTree, 'fromstring')
    def test_parse_xml(self, mock_fromstring, mock_metrics):
        """Test _parse_xml."""
        mock_fromstring.side_effect = xml.etree.ElementTree.ParseError()
        self.jdk_table_xml._config_string = '<test></test>'
        self.jdk_table_xml._parse_xml()
        self.assertTrue(mock_metrics.called)

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
        self.jdk_table_xml._xml = xml.etree.ElementTree.fromstring(xml_str)
        self.assertFalse(self.jdk_table_xml._check_android_sdk_in_xml())

        # No homePath.
        xml_str = ('<test><jdk><name value="Android SDK 29 platform" />'
                   '<type value="Android SDK" />'
                   '<additional jdk="JDK18" sdk="android-29" />'
                   '</jdk></test>')
        self.jdk_table_xml._xml = xml.etree.ElementTree.fromstring(xml_str)
        self.assertFalse(self.jdk_table_xml._check_android_sdk_in_xml())

        # The platform version android-28 does not exist in platform mapping.
        xml_str = ('<test><jdk><name value="Android SDK 28 platform" />'
                   '<type value="Android SDK" />'
                   '<homePath value="/path/to/Android/SDK" />'
                   '<additional jdk="JDK18" sdk="android-28" />'
                   '</jdk></test>')
        self.jdk_table_xml._xml = xml.etree.ElementTree.fromstring(xml_str)
        self.assertFalse(self.jdk_table_xml._check_android_sdk_in_xml())

        # Normal case.
        xml_str = ('<test><jdk><name value="Android SDK 29 platform" />'
                   '<type value="Android SDK" />'
                   '<homePath value="/path/to/Android/SDK" />'
                   '<additional jdk="JDK18" sdk="android-29" />'
                   '</jdk></test>')
        self.jdk_table_xml._xml = xml.etree.ElementTree.fromstring(xml_str)
        self.assertTrue(self.jdk_table_xml._check_android_sdk_in_xml())

        # Incorrect Android SDK path.
        mock_is_android_sdk.return_value = False
        self.jdk_table_xml._xml = xml.etree.ElementTree.fromstring(xml_str)
        self.assertFalse(self.jdk_table_xml._check_android_sdk_in_xml())


if __name__ == '__main__':
    unittest.main()
