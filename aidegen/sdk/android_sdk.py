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

"""Config Android SDK information.

In order to create the configuration of Android SDK in IntelliJ automatically,
parses the Android SDK information from the Android SDK path.

Usage example:
    android_sdk = AndroidSDK()
    android_sdk.path_analysis(default_sdk_path)
    api_level = android_sdk.max_api_level
    android_sdk_path = android_sdk.android_sdk_path
    platform_mapping = android_sdk.platform_mapping
"""

from __future__ import absolute_import

import re

from aidegen.lib import common_util


class AndroidSDK:
    """Configures API level from the Android SDK path.

    Attributes:
        _android_sdk_path: The path to the Android SDK, None if the Android SDK
                           doesn't exist.
        _max_api_level: An integer, the max API level in the platforms folder.
        _platform_mapping: A dictionary of Android platform versions mapping to
                           the API level and the Android version code name.
                           e.g.
                           {
                             'android-29': {'api_level': 29, 'code_name': '29'},
                             'android-Q': {'api_level': 29, 'code_name': 'Q'}
                           }
    """

    _API_LEVEL = 'api_level'
    _CODE_NAME = 'code_name'
    _RE_API_LEVEL = re.compile(r'AndroidVersion.ApiLevel=(?P<api_level>[\d]+)')
    _RE_CODE_NAME = re.compile(r'AndroidVersion.CodeName=(?P<code_name>[A-Z])')

    def __init__(self):
        """Initializes AndroidSDK."""
        self._max_api_level = 0
        self._platform_mapping = {}
        self._android_sdk_path = None

    @property
    def max_api_level(self):
        """Gets the max API level."""
        return self._max_api_level

    @property
    def platform_mapping(self):
        """Gets the Android platform mapping."""
        return self._platform_mapping

    @property
    def android_sdk_path(self):
        """Gets the Android SDK path."""
        return self._android_sdk_path

    def _parse_max_api_level(self):
        """Parses the max API level from self._platform_mapping.

        Returns:
            An integer of API level and 0 means no Android platform exists.
        """
        return max(
            [v[self._API_LEVEL] for v in self._platform_mapping.values()],
            default=0)

    def _parse_api_info(self, properties_file):
        """Parses the API information from the source.properties file.

        For the preview platform like android-Q, the source.properties file
        contains two properties named AndroidVersion.ApiLevel, API level of
        the platform, and AndroidVersion.CodeName such as Q, the code name of
        the plarform.
        However, the formal platform like android-29, there is no property
        AndroidVersion.CodeName.

        Args:
            properties_file: A path of the source.properties file.

        Returns:
            A tuple contains the API level and Code name of the
            source.properties file.
            API level: An integer of the platform, e.g. 29.
            Code name: A string, e.g. 29 or Q.
        """
        api_level = 0
        properties = common_util.read_file_content(properties_file)
        match_api_level = self._RE_API_LEVEL.search(properties)
        if match_api_level:
            api_level = match_api_level.group(self._API_LEVEL)
        match_code_name = self._RE_CODE_NAME.search(properties)
        if match_code_name:
            code_name = match_code_name.group(self._CODE_NAME)
        else:
            code_name = api_level
        return api_level, code_name

    def _gen_platform_mapping(self, path):
        """Generates the Android platforms mapping.

        Args:
            path: A string, the path of Android SDK.
        """

    def _is_android_sdk_path(self, path):
        """Checks if the Android SDK path is correct.

        Confirm the Android SDK path is correct by checking if it has
        platform versions.

        Args:
            path: A string, the path of Android SDK user input.

        Returns:
            True when get a platform version, otherwise False.
        """

    def path_analysis(self, sdk_path):
        """Analyses the Android SDK path.

        Confirm the path is a Android SDK folder. If it's not correct, ask user
        to enter a new one. Skip asking when enter nothing.

        Args:
            sdk_path: A string, the path of Android SDK.

        Returns:
            True when get an Android SDK path, otherwise False.
        """
