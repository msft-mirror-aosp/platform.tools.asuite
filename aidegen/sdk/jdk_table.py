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

"""Configs the jdk.table.xml.

In order to enable the feature "Attach debugger to Android process" in Android
Studio or IntelliJ, AIDEGen needs the JDK and Android SDK been set-up. The class
JDKTableXML parses the jdk.table.xml to find the existing JDK and Android SDK
information. If they do not exist, AIDEGen will create them.

    Usage example:
    jdk_table_xml = JDKTableXML(jdk_table_xml_file,
                                jdk_template,
                                default_jdk_path,
                                default_android_sdk_path)
    jdk_table_xml.config_jdk_table_xml()
    android_sdk_version = jdk_table_xml.android_sdk_version
"""

from __future__ import absolute_import

import os
import xml.etree.ElementTree

from aidegen import constant
from aidegen.lib import aidegen_metrics
from aidegen.lib import common_util
from aidegen.sdk import android_sdk


class JDKTableXML():
    """Configs jdk.table.xml for IntelliJ and Android Studio.

    Attributes:
        _config_file: The absolute file path of the jdk.table.xml, the file
                      might not exist.
        _jdk_content: A string, the content of the JDK configuration.
        _jdk_path: The path of JDK in android project.
        _default_android_sdk_path: The default path to the Android SDK.
        _config_string: A string, content of _config_file.
        _platform_version: The version name of the platform, e.g. android-29
        _android_sdk_version: The version name of the Android SDK in the
                              jdk.table.xml, e.g. Android API 29 Platform
        _modify_config: A boolean, True to write new content to jdk.table.xml.
        _xml: An xml.etree.ElementTree object contains the XML parsing result.
        _sdk: An AndroidSDK object to get the Android SDK path and platform
              mapping.
    """
    _JDK = 'jdk'
    _NAME = 'name'
    _TYPE = 'type'
    _VALUE = 'value'
    _SDK = 'sdk'
    _HOMEPATH = 'homePath'
    _ADDITIONAL = 'additional'
    _ANDROID_SDK = 'Android SDK'
    _JAVA_SDK = 'JavaSDK'
    _JDK_VERSION = 'JDK18'
    _XML_CONTENT = ('<application>\n  <component name="ProjectJdkTable">\n'
                    '  </component>\n</application>\n')
    _COMPONENT_END_TAG = '  </component>'
    _INVALID_XML = 'The content of {XML_FILE} is not valid.'

    def __init__(self, config_file, jdk_content, jdk_path,
                 default_android_sdk_path):
        """JDKTableXML initialize.

        Args:
            config_file: The absolute file path of the jdk.table.xml, the file
                         might not exist.
            jdk_content: A string, the content of the JDK configuration.
            jdk_path: The path of JDK in android project.
            default_android_sdk_path: The default absolute path to the Android
                                      SDK.
        """
        self._config_file = config_file
        self._jdk_content = jdk_content
        self._jdk_path = jdk_path
        self._default_android_sdk_path = default_android_sdk_path
        self._config_string = self._XML_CONTENT
        if os.path.exists(config_file):
            self._config_string = common_util.read_file_content(config_file)
        self._platform_version = None
        self._android_sdk_version = None
        self._modify_config = False
        self._xml = None
        self._parse_xml()
        self._sdk = android_sdk.AndroidSDK()

    @property
    def android_sdk_version(self):
        """Gets the Android SDK version."""
        return self._android_sdk_version

    def _parse_xml(self):
        """Parses the string of a XML file."""
        try:
            self._xml = xml.etree.ElementTree.fromstring(self._config_string)
        except xml.etree.ElementTree.ParseError as err:
            aidegen_metrics.send_exception_metrics(
                constant.XML_PARSING_FAILURE, err, self._config_string,
                self._INVALID_XML.format(XML_FILE=self._config_file))

    def _check_jdk18_in_xml(self):
        """Checks if the JDK18 is already set in jdk.table.xml.

        Returns:
            Boolean: True if the JDK18 exists else False.
        """
        for jdk in self._xml.iter(self._JDK):
            _name = jdk.find(self._NAME)
            _type = jdk.find(self._TYPE)
            if None in (_name, _type):
                continue
            if (_type.get(self._VALUE) == self._JAVA_SDK
                    and _name.get(self._VALUE) == self._JDK_VERSION):
                return True
        return False

    def _check_android_sdk_in_xml(self):
        """Checks if the Android SDK is already set in jdk.table.xml.

        If the Android SDK exists in xml, validate the value of Android SDK path
        and platform version.
        1. Check if the Android SDK path is valid.
        2. Check if the platform version exists in the Android SDK.
        The Android SDK version can be used to generate enble_debugger module
        when condition 1 and 2 are true.

        Returns:
            Boolean: True if the Android SDK configuration exists, otherwise
                     False.
        """
        for tag in self._xml.iter(self._JDK):
            _name = tag.find(self._NAME)
            _type = tag.find(self._TYPE)
            _homepath = tag.find(self._HOMEPATH)
            _additional = tag.find(self._ADDITIONAL)
            if None in (_name, _type, _homepath, _additional):
                continue

            tag_type = _type.get(self._VALUE)
            home_path = _homepath.get(self._VALUE).replace(
                constant.USER_HOME, os.path.expanduser('~'))
            platform = _additional.get(self._SDK)
            if (tag_type != self._ANDROID_SDK
                    or not self._sdk.is_android_sdk_path(home_path)
                    or platform not in self._sdk.platform_mapping):
                continue
            self._android_sdk_version = _name.get(self._VALUE)
            self._platform_version = platform
            return True
        return False

    def _append_config(self, new_config):
        """Adds a <jdk> configuration at the last of <component>.

        Args:
            new_config: A string of new <jdk> configuration.
        """
        self._config_string = self._config_string.replace(
            self._COMPONENT_END_TAG, new_config + self._COMPONENT_END_TAG)

    def _generate_jdk_config_string(self):
        """Generates the default JDK configuration."""
        if self._check_jdk18_in_xml():
            return
        self._append_config(self._jdk_content)
        self._config_string = self._config_string.format(JDKpath=self._jdk_path)
        self._modify_config = True

    def _generate_sdk_config_string(self):
        """Generates Android SDK configuration."""

    def config_jdk_table_xml(self):
        """Configures the jdk.table.xml.

        1. Generate the JDK18 configuration if it does not exist.
        2. Generate the Android SDK configuration if it does not exist and
           save the Android SDK path.
        3. Update the jdk.table.xml if AIDEGen needs to append JDK18 or
           Android SDK configuration.
        """
        self._generate_jdk_config_string()
        self._generate_sdk_config_string()
        if self._modify_config:
            common_util.file_generate(self._config_file, self._config_string)
