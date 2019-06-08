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
import xml.dom.minidom


class SDKConfig():
    """SDK config.

    Currently this class only configures JDK.
    # TODO(b/134100832): configure Android SDK in jdk.table.xml.

    Attributes:
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
    """

    _TARGET_JDK_NAME_TAG = '<name value="JDK18" />'
    _JDK_PATH_TOKEN = '@JDKpath'
    _COMPONENT_END_TAG = '  </component>'
    _XML_CONTENT = ('<application>\n  <component name="ProjectJdkTable">\n{}'
                    '  </component>\n</application>\n')
    _TAG_JDK = 'jdk'
    _TAG_NAME = 'name'
    _TAG_TYPE = 'type'
    _ATTRIBUTE_VALUE = 'value'
    _TYPE_JAVASDK = 'JavaSDK'
    _NAME_JDK18 = 'JDK18'
    _TYPE_ANDROID_SDK = 'Android SDK'

    def __init__(self, config_file, template_jdk_file, jdk_path):
        """SDKConfig initialize.

        Args:
            config_file: The absolute file path of the jdk.table.xml, the file
                         might not exist.
            template_jdk_file: The JDK table template file path.
            jdk_path: The path of JDK in android project.
        """
        self.config_file = config_file
        self.template_jdk_file = template_jdk_file
        self.jdk_path = jdk_path
        self.config_exists = os.path.isfile(config_file)
        self.config_string = self._get_default_config_content()
        self.xml_dom = xml.dom.minidom.parseString(self.config_string)
        self.jdks = self.xml_dom.getElementsByTagName(self._TAG_JDK)

    def _load_template(self):
        """Read template file content.

        Returns:
            String: Content of the template file, empty string if the file
                    doesn't exists.
        """
        if os.path.isfile(self.template_jdk_file):
            with open(self.template_jdk_file) as template:
                return template.read()
        return ''

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
        return self._XML_CONTENT.format(self._load_template())

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
            with open(self.config_file, 'w') as jdk_file:
                jdk_file.write(self.config_string)
        except (IOError, OSError) as err:
            logging.warning('Can\'t write the JDK info in %s.\n %s',
                            self.config_file, err)

    def generate_jdk_config_string(self):
        """Generate the content of jdk confiduration."""
        # Add JDK18 configuration at the end of the <component> if the config
        # file exists but the JDK18 doesn't exist.
        if self.config_exists and not self._target_jdk_exists():
            self._append_jdk_config_string(self._load_template())
        self.config_string = self.config_string.replace(self._JDK_PATH_TOKEN,
                                                        self.jdk_path)

    def config_jdk_file(self):
        """Generate the content of config and write it to the jdk.table.xml."""
        # Skip the jdk configuration if it exists.
        if self.config_exists and self._target_jdk_exists():
            return
        self.generate_jdk_config_string()
        self._write_jdk_config_file()
