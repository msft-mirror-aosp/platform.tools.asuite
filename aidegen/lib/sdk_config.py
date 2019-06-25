#!/usr/bin/env python3
#
# Copyright 2019 - The Android Open Source Project
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

"""Config SDK in jdk.table.xml."""

from __future__ import absolute_import

import logging
import os
import re
import xml.dom.minidom

from aidegen import constant
from aidegen.lib import common_util

_API_LEVEL = 'api_level'
_PLATFORMS = 'platforms'


class SDKConfig():
    """SDK config.

    Instance attributes:
        config_file: The absolute file path of the jdk.table.xml, the file
                     might not exist.
        template_jdk_file: The JDK table template file path.
        jdk_path: The path of JDK in android project.
        config_exists: A boolean, True if the config_file exists otherwise
                       False.
        config_string: A string, it will be written into config_file.
        xml_dom: An object which contains the xml file parsing result of the
                 config_file.
        jdks: An element list with tag named "jdk" in xml_dom.

    Class attrubute:
        android_sdk_path: The path to the Android SDK, None if the Android SDK
                          doesn't exist.
        max_api_level: An integer, parsed from the folder named android-{n}
                       under Android/Sdk/platforms.
    """

    android_sdk_path = None
    max_api_level = 0
    _TARGET_JDK_NAME_TAG = '<name value="JDK18" />'
    _COMPONENT_END_TAG = '  </component>'
    _XML_CONTENT = ('<application>\n  <component name="ProjectJdkTable">\n'
                    '  </component>\n</application>\n')
    _TAG_JDK = 'jdk'
    _TAG_NAME = 'name'
    _TAG_TYPE = 'type'
    _ATTRIBUTE_VALUE = 'value'
    _TYPE_JAVASDK = 'JavaSDK'
    _NAME_JDK18 = 'JDK18'
    _TYPE_ANDROID_SDK = 'Android SDK'
    _INPUT_QUERY_TIMES = 3
    _API_FOLDER_RE = re.compile(r'platforms/android-(?P<api_level>[\d]+)')
    _ROOT_DIR = constant.AIDEGEN_ROOT_PATH
    _TEMPLATE_ANDROID_SDK = os.path.join(
        _ROOT_DIR, 'templates/jdkTable/part.android.sdk.xml')
    _ENTER_ANDROID_SDK_PATH = ('\nThe Android SDK folder:{} doesn\'t exist. '
                               'The debug function "Attach debugger to Android '
                               'process" is disabled without Android SDK in '
                               'IntelliJ. Please set it up to enable the '
                               'function. \nPlease enter the absolute path '
                               'to Android SDK:')
    _WARNING_API_LEVEL = ('Cannot find the Android SDK API folder from {}. '
                          'Please install the SDK platform, otherwise the '
                          'debug function "Attach debugger to Android process" '
                          'cannot be enabled in IntelliJ.')

    def __init__(self, config_file, template_jdk_file, jdk_path,
                 default_android_sdk_path):
        """SDKConfig initialize.

        Args:
            config_file: The absolute file path of the jdk.table.xml, the file
                         might not exist.
            template_jdk_file: The JDK table template file path.
            jdk_path: The path of JDK in android project.
            default_android_sdk_path: The default path to the Android SDK, it
                                      might not exist.
        """
        self.config_file = config_file
        self.template_jdk_file = template_jdk_file
        self.jdk_path = jdk_path
        self.config_exists = os.path.isfile(config_file)
        self.config_string = self._get_default_config_content()
        self.xml_dom = xml.dom.minidom.parseString(self.config_string)
        self.jdks = self.xml_dom.getElementsByTagName(self._TAG_JDK)
        SDKConfig.android_sdk_path = default_android_sdk_path

    def _get_default_config_content(self):
        """Get the default content of self.config_file.

        If self.config_file exists, read the content as default. Otherwise, load
        the content of self.template_jdk_file.

        Returns:
            String: The content will be written into self.config_file.
        """
        if self.config_exists:
            with open(self.config_file) as config:
                return config.read()
        return self._XML_CONTENT

    def _get_first_element_value(self, node, element_name):
        """Get the first element if it exists in node.

        Example:
            The node:
                <jdk version="2">
                    <name value="JDK18" />
                    <type value="JavaSDK" />
                </jdk>
            The element_name could be name or type. And the value of name is
            JDK18, the value of type is JavaSDK.

        Args:
            node: A minidom object parsed from a xml.
            element_name: A string of tag name in xml.

        Returns:
            String: None if the element_name doesn't exist.
        """
        elements = node.getElementsByTagName(element_name)
        return (elements[0].getAttribute(self._ATTRIBUTE_VALUE) if elements
                else None)

    def _target_jdk_exists(self):
        """Check if the JDK18 is already set in jdk.table.xml.

        Returns:
            Boolean: True if the JDK18 exists else False.
        """
        for jdk in self.jdks:
            jdk_type = self._get_first_element_value(jdk, self._TAG_TYPE)
            jdk_name = self._get_first_element_value(jdk, self._TAG_NAME)
            if jdk_type == self._TYPE_JAVASDK and jdk_name == self._NAME_JDK18:
                return True
        return False

    def _android_sdk_exists(self):
        """Check if the Android SDK is already set in jdk.table.xml.

        Returns:
            Boolean: True if the Android SDK configuration exists, otherwise
                     False.
        """
        for jdk in self.jdks:
            jdk_type = self._get_first_element_value(jdk, self._TAG_TYPE)
            if jdk_type == self._TYPE_ANDROID_SDK:
                return True
        return False

    @staticmethod
    def _enter_android_sdk_path(input_message):
        """Ask user input the path to Android SDK."""
        return input(input_message)

    @classmethod
    def _get_android_sdk_path(cls):
        """Get the Android SDK path.

        Returns: The android sdk path if it exists, otherwise None.
        """
        # Set the maximum times require user to input the path of Android Sdk.
        _check_times = cls._INPUT_QUERY_TIMES
        while not cls._set_max_api_level():
            if _check_times == 0:
                cls.android_sdk_path = None
                break
            cls.android_sdk_path = cls._enter_android_sdk_path(
                common_util.COLORED_FAIL(cls._ENTER_ANDROID_SDK_PATH.format(
                    cls.android_sdk_path)))
            _check_times -= 1
        return cls.android_sdk_path

    @classmethod
    def _set_max_api_level(cls):
        """Set the max API level from Android SDK folder.

        1. Find the api folder such as android-28 in platforms folder.
        2. Parse the API level 28 from folder name android-28.

        Returns: An integer, the max api level. Defatult is 0 if there is no
                 android-{x} folder under android_sdk_path.
        """
        platforms_dir = cls._get_platforms_dir_path()
        if os.path.isdir(platforms_dir):
            for abspath, _, _ in os.walk(platforms_dir):
                match_api_folder = cls._API_FOLDER_RE.search(abspath)
                if match_api_folder:
                    api_level = int(match_api_folder.group(_API_LEVEL))
                    if api_level > cls.max_api_level:
                        cls.max_api_level = api_level
        return cls.max_api_level

    @classmethod
    def _get_platforms_dir_path(cls):
        """Get the platform's dir path from user input Android SDK path.

        Supposed users could input the SDK or platforms path:
        e.g.
        /.../Android/Sdk or /.../Android/Sdk/platforms
        In order to minimize the search range for android-x folder, we check if
        the last folder name is platforms from user input. If it is, return the
        path, otherwise return the path which combines user input and platforms
        folder name.

        Returns: The platforms folder path string.
        """
        if cls.android_sdk_path.split(os.sep)[-1] == _PLATFORMS:
            return cls.android_sdk_path
        return os.path.join(cls.android_sdk_path, _PLATFORMS)

    def _append_jdk_config_string(self, new_jdk_config):
        """Add a jdk configuration at the last of <component>.

        Args:
            new_jdk_config: A string of new jdk configuration.
        """
        self.config_string = self.config_string.replace(
            self._COMPONENT_END_TAG, new_jdk_config + self._COMPONENT_END_TAG)

    def _write_jdk_config_file(self):
        """Override the jdk.table.xml with the config_string."""
        try:
            common_util.file_generate(self.config_file, self.config_string)
        except (IOError, OSError) as err:
            logging.warning('Can\'t write the JDK info in %s.\n %s',
                            self.config_file, err)

    def generate_jdk_config_string(self):
        """Generate the default jdk confiduration."""
        if not self._target_jdk_exists():
            self._append_jdk_config_string(
                common_util.read_file_content(self.template_jdk_file))
        self.config_string = self.config_string.format(JDKpath=self.jdk_path)

    def generate_sdk_config_string(self):
        """Generate Android SDK confiduration."""
        if not self._android_sdk_exists():
            if self._get_android_sdk_path():
                self._append_jdk_config_string(
                    common_util.read_file_content(self._TEMPLATE_ANDROID_SDK))
                self.config_string = self.config_string.format(
                    ANDROID_SDK_PATH=SDKConfig.android_sdk_path,
                    API_LEVEL=SDKConfig.max_api_level)
            else:
                print('\n{} {}\n'.format(common_util.COLORED_INFO('Warning:'),
                                         self._WARNING_API_LEVEL.format(
                                             SDKConfig.max_api_level)))

    def config_jdk_file(self):
        """Generate the content of config and write it to the jdk.table.xml."""
        if self._target_jdk_exists() and self._android_sdk_exists():
            return
        self.generate_jdk_config_string()
        self.generate_sdk_config_string()
        self._write_jdk_config_file()
