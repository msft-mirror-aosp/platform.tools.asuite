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

"""Unittests for AidegenConfig class."""

import os
import unittest

from aidegen import unittest_constants
from aidegen.lib import config
from aidegen.lib import common_util


# pylint: disable=protected-access
class AidegenConfigUnittests(unittest.TestCase):
    """Unit tests for config.py"""

    _ENABLE_DEBUG_CONFIG_FILE = 'enable_debugger.iml'
    _TEST_API_LEVEL = '28'
    _TEST_DATA_PATH = unittest_constants.TEST_DATA_PATH
    _ANDROID_PROJECT_PATH = os.path.join(_TEST_DATA_PATH, 'android_project')
    _ENABLE_DEBUGGER_IML_SAMPLE = os.path.join(_TEST_DATA_PATH,
                                               _ENABLE_DEBUG_CONFIG_FILE)
    _GENERATED_ENABLE_DEBUGGER_IML = os.path.join(_ANDROID_PROJECT_PATH,
                                                  _ENABLE_DEBUG_CONFIG_FILE)

    def test_gen_enable_debugger_config(self):
        """Test _gen_enable_debugger_config."""
        try:
            _cfg = config.AidegenConfig()
            _cfg.DEBUG_ENABLED_FILE_PATH = os.path.join(
                self._ANDROID_PROJECT_PATH, _cfg._ENABLE_DEBUG_CONFIG_FILE)
            _cfg._gen_enable_debugger_config(self._TEST_API_LEVEL)
            expected_content = common_util.read_file_content(
                self._ENABLE_DEBUGGER_IML_SAMPLE)
            test_content = common_util.read_file_content(
                self._GENERATED_ENABLE_DEBUGGER_IML)
            self.assertEqual(test_content, expected_content)
        finally:
            if os.path.exists(self._GENERATED_ENABLE_DEBUGGER_IML):
                os.remove(self._GENERATED_ENABLE_DEBUGGER_IML)


if __name__ == '__main__':
    unittest.main()
