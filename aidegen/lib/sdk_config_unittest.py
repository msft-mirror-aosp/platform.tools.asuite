#!/usr/bin/env python3
#
# Copyright 2019, The Android Open Source Project
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

"""Unittests for checking the jdk is generated in jdk.table.xml.."""

import os
import shutil
import tempfile
import unittest
from unittest import mock
import xml

from aidegen import constant
from aidegen import unittest_constants
from aidegen.lib import errors
from aidegen.lib import sdk_config


# pylint: disable=protected-access
# pylint: disable=invalid-name
# pylint: disable=too-many-arguments
class SDKConfigUnittests(unittest.TestCase):
    """Unit tests for sdk_config.py"""
    _JDK_FILE_NAME = 'jdk.table.xml'
    _JDK_SAMPLE = os.path.join(unittest_constants.TEST_DATA_PATH,
                               'jdk_table_xml', 'jdk18.xml')
    _JDK_SAMPLE2 = os.path.join(unittest_constants.TEST_DATA_PATH,
                                'jdk_table_xml', 'jdk_nonexistent.xml')
    _JDK_SAMPLE3 = os.path.join(unittest_constants.TEST_DATA_PATH,
                                'jdk_table_xml', 'android_sdk.xml')
    _JDK_SAMPLE4 = os.path.join(unittest_constants.TEST_DATA_PATH,
                                'jdk_table_xml', 'android_sdk_nonexistent.xml')
    _JDK_PATH = os.path.join('/path', 'to', 'android', 'root',
                             'prebuilts', 'jdk', 'jdk8', 'linux-x86')
    _JDK_OTHER_CONTENT = """<application>
  <component name="ProjectJdkTable">
    <jdk version="2">
      <name value="JDK_OTHER" />
      <type value="JavaSDK" />
    </jdk>
  </component>
</application>
"""
    _NONEXISTENT_ANDROID_SDK_PATH = os.path.join('/path', 'to', 'Android',
                                                 'Sdk')
    _DEFAULT_ANDROID_SDK_PATH = os.path.join(unittest_constants.TEST_DATA_PATH,
                                             'Android/Sdk')
    _CUSTOM_ANDROID_SDK_PATH = os.path.join(unittest_constants.TEST_DATA_PATH,
                                            'Android/custom/sdk')
    _TEMP = 'temp'

    def test_generate_jdk_config(self):
        """Test generating jdk config."""
        expected_content = ''
        tmp_folder = tempfile.mkdtemp()
        config_file = os.path.join(tmp_folder, self._JDK_FILE_NAME)
        try:
            with open(self._JDK_SAMPLE) as sample:
                expected_content = sample.read()
            jdk = sdk_config.SDKConfig(config_file,
                                       constant.LINUX_JDK_XML,
                                       self._JDK_PATH,
                                       self._NONEXISTENT_ANDROID_SDK_PATH)
            jdk.generate_jdk_config_string()
            self.assertEqual(jdk.config_string, expected_content)
        finally:
            shutil.rmtree(tmp_folder)

    def test_jdk_config_no_change(self):
        """The config file exists and the JDK18 also exists.

        In this case, there is nothing to do, make sure the config content is
        not changed.
        """
        expected_content = ''
        tmp_folder = tempfile.mkdtemp()
        config_file = os.path.join(tmp_folder, self._JDK_FILE_NAME)
        try:
            with open(self._JDK_SAMPLE) as sample:
                expected_content = sample.read()
            # Reset the content of config file.
            with open(config_file, 'w') as cf:
                cf.write(expected_content)
            jdk = sdk_config.SDKConfig(config_file,
                                       constant.LINUX_JDK_XML,
                                       self._JDK_PATH,
                                       self._DEFAULT_ANDROID_SDK_PATH)
            jdk.generate_jdk_config_string()
            self.assertEqual(jdk.config_string, expected_content)
        finally:
            shutil.rmtree(tmp_folder)

    def test_append_jdk_config(self):
        """The config file exists, test on the JDK18 does not exist."""
        expected_content = ''
        tmp_folder = tempfile.mkdtemp()
        config_file = os.path.join(tmp_folder, self._JDK_FILE_NAME)
        try:
            with open(self._JDK_SAMPLE2) as sample:
                expected_content = sample.read()
            # Reset the content of config file.
            with open(config_file, 'w') as cf:
                cf.write(self._JDK_OTHER_CONTENT)
            jdk = sdk_config.SDKConfig(config_file,
                                       constant.LINUX_JDK_XML,
                                       self._JDK_PATH,
                                       self._NONEXISTENT_ANDROID_SDK_PATH)
            jdk.generate_jdk_config_string()
            self.assertEqual(jdk.config_string, expected_content)
        finally:
            shutil.rmtree(tmp_folder)

    def test_android_sdk_exist(self):
        """Test to check the Android SDK configuration does exist."""
        expected_content = ''
        tmp_folder = tempfile.mkdtemp()
        config_file = os.path.join(tmp_folder, self._JDK_FILE_NAME)
        try:
            with open(self._JDK_SAMPLE3) as sample:
                expected_content = sample.read()
            with open(config_file, 'w') as cf:
                cf.write(expected_content)
            jdk = sdk_config.SDKConfig(config_file,
                                       constant.LINUX_JDK_XML,
                                       self._JDK_PATH,
                                       self._NONEXISTENT_ANDROID_SDK_PATH)
            self.assertEqual(jdk._android_sdk_exists(), True)
        finally:
            shutil.rmtree(tmp_folder)

    def test_android_sdk_not_exist(self):
        """Test to check the Android SDK configuration doesn't exist."""
        expected_content = ''
        tmp_folder = tempfile.mkdtemp()
        config_file = os.path.join(tmp_folder, self._JDK_FILE_NAME)
        try:
            with open(self._JDK_SAMPLE4) as sample:
                expected_content = sample.read()
            with open(config_file, 'w') as cf:
                cf.write(expected_content)
            jdk = sdk_config.SDKConfig(config_file,
                                       constant.LINUX_JDK_XML,
                                       self._JDK_PATH,
                                       self._NONEXISTENT_ANDROID_SDK_PATH)
            self.assertEqual(jdk._android_sdk_exists(), False)
        finally:
            shutil.rmtree(tmp_folder)

    def test_get_android_sdk_path(self):
        """Test get default Android SDK path."""
        expected_content = self._DEFAULT_ANDROID_SDK_PATH
        jdk = sdk_config.SDKConfig(self._JDK_SAMPLE4,
                                   constant.LINUX_JDK_XML,
                                   self._JDK_PATH,
                                   self._DEFAULT_ANDROID_SDK_PATH)
        jdk._get_android_sdk_path()
        self.assertEqual(jdk.android_sdk_path, expected_content)

    def test_get_custom_android_sdk_path(self):
        """Test get custom Android SDK path."""
        api_folder = os.path.join(self._CUSTOM_ANDROID_SDK_PATH, 'platforms',
                                  'android-28')
        os.makedirs(api_folder)
        user_input = [self._CUSTOM_ANDROID_SDK_PATH]
        sdk_config.SDKConfig.max_api_level = 0
        expected_path = self._CUSTOM_ANDROID_SDK_PATH
        try:
            with mock.patch('builtins.input', side_effect=user_input):
                jdk = sdk_config.SDKConfig(self._JDK_SAMPLE4,
                                           constant.LINUX_JDK_XML,
                                           self._JDK_PATH,
                                           self._NONEXISTENT_ANDROID_SDK_PATH)
                jdk._get_android_sdk_path()
                self.assertEqual(jdk.android_sdk_path, expected_path)
        finally:
            shutil.rmtree(os.path.dirname(self._CUSTOM_ANDROID_SDK_PATH))

    def test_set_max_api_level(self):
        """Test set max API level."""
        expected_api_level = 28
        jdk = sdk_config.SDKConfig(self._JDK_SAMPLE3,
                                   constant.LINUX_JDK_XML,
                                   self._JDK_PATH,
                                   self._DEFAULT_ANDROID_SDK_PATH)
        jdk._set_max_api_level()
        self.assertEqual(jdk.max_api_level, expected_api_level)

        # Test Android SDK platforms folder doesn't exist.
        sdk_config.SDKConfig.max_api_level = 0
        expected_api_level = 0
        jdk = sdk_config.SDKConfig(self._JDK_SAMPLE3,
                                   constant.LINUX_JDK_XML,
                                   self._JDK_PATH,
                                   self._NONEXISTENT_ANDROID_SDK_PATH)
        jdk._set_max_api_level()
        self.assertEqual(jdk.max_api_level, expected_api_level)

    def test_generate_android_sdk_config(self):
        """Test generating Android SDK config."""
        expected_content = ''
        tmp_folder = tempfile.mkdtemp()
        config_file = os.path.join(tmp_folder, self._JDK_FILE_NAME)
        try:
            with open(self._JDK_SAMPLE3) as sample:
                expected_content = sample.read().replace(
                    self._NONEXISTENT_ANDROID_SDK_PATH,
                    self._DEFAULT_ANDROID_SDK_PATH)
            jdk = sdk_config.SDKConfig(config_file,
                                       constant.LINUX_JDK_XML,
                                       self._JDK_PATH,
                                       self._NONEXISTENT_ANDROID_SDK_PATH)
            user_input = [self._DEFAULT_ANDROID_SDK_PATH]
            with mock.patch('builtins.input', side_effect=user_input):
                jdk.generate_sdk_config_string()
                self.assertEqual(jdk.config_string, expected_content)
        finally:
            shutil.rmtree(tmp_folder)

    @mock.patch.object(xml.dom.minidom, 'parseString')
    def test_parse_xml_failed(self, mock_parse):
        """Test _parse_xml failed."""
        tmp_folder = self._TEMP
        config_file = os.path.join(tmp_folder, self._JDK_FILE_NAME)
        mock_parse.side_effect = TypeError()
        with self.assertRaises(errors.InvalidXMLError):
            sdk_config.SDKConfig(config_file,
                                 constant.LINUX_JDK_XML,
                                 self._JDK_PATH,
                                 self._NONEXISTENT_ANDROID_SDK_PATH)
        mock_parse.side_effect = AttributeError()
        with self.assertRaises(errors.InvalidXMLError):
            sdk_config.SDKConfig(config_file,
                                 constant.LINUX_JDK_XML,
                                 self._JDK_PATH,
                                 self._NONEXISTENT_ANDROID_SDK_PATH)

    def test_get_platforms_dir_path(self):
        """Test _get_platforms_dir_path."""
        default_android_sdk_path = '/a/b'
        expected_path = '/a/b/platforms'
        jdk = sdk_config.SDKConfig(self._JDK_SAMPLE3,
                                   constant.LINUX_JDK_XML,
                                   self._JDK_PATH,
                                   default_android_sdk_path)
        test_path = jdk._get_platforms_dir_path()
        self.assertEqual(test_path, expected_path)

        default_android_sdk_path = '/a/b/platforms'
        expected_path = '/a/b/platforms'
        jdk = sdk_config.SDKConfig(self._JDK_SAMPLE3,
                                   constant.LINUX_JDK_XML,
                                   self._JDK_PATH,
                                   default_android_sdk_path)
        test_path = jdk._get_platforms_dir_path()
        self.assertEqual(test_path, expected_path)

    @mock.patch.object(sdk_config.SDKConfig, '_write_jdk_config_file')
    @mock.patch.object(sdk_config.SDKConfig, 'generate_sdk_config_string')
    @mock.patch.object(sdk_config.SDKConfig, 'generate_jdk_config_string')
    @mock.patch.object(sdk_config.SDKConfig, '_android_sdk_exists')
    @mock.patch.object(sdk_config.SDKConfig, '_target_jdk_exists')
    def test_config_jdk_file_do_nothing(self, mock_jdk_exist, mock_sdk_exist,
                                        mock_gen_jdk, mock_gen_sdk, mock_write):
        """Test config_jdk_file check and return."""
        mock_jdk_exist.return_value = True
        mock_sdk_exist.return_value = True
        tmp_folder = self._TEMP
        config_file = os.path.join(tmp_folder, self._JDK_FILE_NAME)
        jdk = sdk_config.SDKConfig(config_file,
                                   constant.LINUX_JDK_XML,
                                   self._JDK_PATH,
                                   self._NONEXISTENT_ANDROID_SDK_PATH)
        jdk.config_jdk_file()
        self.assertFalse(mock_gen_jdk.called)
        self.assertFalse(mock_gen_sdk.called)
        self.assertFalse(mock_write.called)

    @mock.patch.object(sdk_config.SDKConfig, '_parse_xml')
    @mock.patch.object(sdk_config.SDKConfig, '_write_jdk_config_file')
    @mock.patch.object(sdk_config.SDKConfig, 'generate_sdk_config_string')
    @mock.patch.object(sdk_config.SDKConfig, 'generate_jdk_config_string')
    @mock.patch.object(sdk_config.SDKConfig, '_android_sdk_exists')
    @mock.patch.object(sdk_config.SDKConfig, '_target_jdk_exists')
    def test_config_jdk_file_do_something(self, mock_jdk_exist, mock_sdk_exist,
                                          mock_gen_jdk, mock_gen_sdk,
                                          mock_write, mock_parse):
        """Test config_jdk_file config jdk file."""
        mock_jdk_exist.return_value = True
        mock_sdk_exist.return_value = False
        tmp_folder = self._TEMP
        config_file = os.path.join(tmp_folder, self._JDK_FILE_NAME)
        jdk = sdk_config.SDKConfig(config_file,
                                   constant.LINUX_JDK_XML,
                                   self._JDK_PATH,
                                   self._NONEXISTENT_ANDROID_SDK_PATH)
        jdk.config_jdk_file()
        self.assertTrue(mock_gen_jdk.called)
        self.assertTrue(mock_gen_sdk.called)
        self.assertTrue(mock_write.called)
        self.assertTrue(mock_parse.called)
        mock_jdk_exist.return_value = False
        mock_sdk_exist.return_value = True
        jdk = sdk_config.SDKConfig(config_file,
                                   constant.LINUX_JDK_XML,
                                   self._JDK_PATH,
                                   self._NONEXISTENT_ANDROID_SDK_PATH)
        jdk.config_jdk_file()
        self.assertTrue(mock_gen_jdk.called)
        self.assertTrue(mock_gen_sdk.called)
        self.assertTrue(mock_write.called)
        self.assertTrue(mock_parse.called)

    @mock.patch.object(os.path, 'isfile')
    def test_get_default_config_content(self, mock_isfile):
        """Test _get_default_config_content."""
        mock_isfile.return_value = False
        tmp_folder = self._TEMP
        config_file = os.path.join(tmp_folder, self._JDK_FILE_NAME)
        jdk = sdk_config.SDKConfig(config_file,
                                   constant.LINUX_JDK_XML,
                                   self._JDK_PATH,
                                   self._NONEXISTENT_ANDROID_SDK_PATH)
        self.assertEqual(sdk_config.SDKConfig._XML_CONTENT,
                         jdk._get_default_config_content())

    def test_get_max_platform_api(self):
        """Test get max api level from the platforms folder."""
        jdk = sdk_config.SDKConfig(self._JDK_SAMPLE3,
                                   constant.LINUX_JDK_XML,
                                   self._JDK_PATH,
                                   self._DEFAULT_ANDROID_SDK_PATH)
        max_api = jdk._get_max_platform_api(self._DEFAULT_ANDROID_SDK_PATH)
        self.assertEqual(max_api, 28)

    def test_max_platform_api_failed(self):
        """Test get max api level failed from the platforms folder."""
        jdk = sdk_config.SDKConfig(self._JDK_SAMPLE3,
                                   constant.LINUX_JDK_XML,
                                   self._JDK_PATH,
                                   self._DEFAULT_ANDROID_SDK_PATH)
        max_api = jdk._get_max_platform_api(self._NONEXISTENT_ANDROID_SDK_PATH)
        self.assertEqual(max_api, 0)


if __name__ == '__main__':
    unittest.main()
