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

"""Unittests for AndroidSDK class."""

import unittest

from aidegen.sdk import android_sdk


# pylint: disable=protected-access
class AndroidSDKUnittests(unittest.TestCase):
    """Unit tests for AndroidSDK class."""

    def setUp(self):
        """Prepare the testdata related path."""
        self.sdk = android_sdk.AndroidSDK()

    def tearDown(self):
        """Clear the testdata related path."""
        self.sdk = None

    def test_init(self):
        """Test initialize the attributes."""
        self.assertEqual(self.sdk.max_api_level, 0)
        self.assertEqual(self.sdk.platform_mapping, {})
        self.assertEqual(self.sdk.android_sdk_path, None)

    def test_parse_max_api_level(self):
        """Test _parse_max_api_level."""
        self.sdk._platform_mapping = {
            'android-29': {
                'api_level': 29,
                'code_name': '29',
            },
            'android-28': {
                'api_level': 28,
                'code_name': '28',
            },
        }
        api_level = self.sdk._parse_max_api_level()
        self.assertEqual(api_level, 29)

        self.sdk._platform_mapping = {
            'android-28': {
                'api_level': 28,
                'code_name': '28',
            },
            'android-Q': {
                'api_level': 29,
                'code_name': 'Q',
            },
        }
        api_level = self.sdk._parse_max_api_level()
        self.assertEqual(api_level, 29)

if __name__ == '__main__':
    unittest.main()
