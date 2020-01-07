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

"""Unittests for native_module_info."""

import unittest
from unittest import mock

from aidegen.lib import common_util
from aidegen.lib import native_module_info

_PATH_TO_MULT_MODULES_WITH_MULTI_ARCH = 'shared/path/to/be/used2'
_TESTABLE_MODULES_WITH_SHARED_PATH = [
    'multiarch', 'multiarch1', 'multiarch2', 'multiarch3', 'multiarch3_32'
]
_CC_NAME_TO_MODULE_INFO = {
    "multiarch": {
        "path": [
            "shared/path/to/be/used2"
        ],
        "module_name": "multiarch"
    },
    "multiarch1": {
        "path": [
            "shared/path/to/be/used2/arch1"
        ],
        "module_name": "multiarch1"
    },
    "multiarch2": {
        "path": [
            "shared/path/to/be/used2/arch2"
        ],
        "module_name": "multiarch2"
    },
    "multiarch3": {
        "path": [
            "shared/path/to/be/used2/arch3"
        ],
        "module_name": "multiarch3"
    },
    "multiarch3_32": {
        "path": [
            "shared/path/to/be/used2/arch3_32"
        ],
        "module_name": "multiarch3_32"
    }
}
_CC_MODULE_INFO = {
    "clang": "${ANDROID_ROOT}/prebuilts/clang/host/linux-x86/bin/clang",
    "clang++": "${ANDROID_ROOT}/prebuilts/clang/host/linux-x86/bin/clang++",
    "modules": _CC_NAME_TO_MODULE_INFO
}


#pylint: disable=protected-access
class NativeModuleInfoUnittests(unittest.TestCase):
    """Unit tests for module_info.py"""

    @mock.patch.object(
        native_module_info.NativeModuleInfo, '_load_module_info_file')
    @mock.patch.object(common_util, 'get_related_paths')
    def test_get_module_names_in_targets_paths(self, mock_relpath, mock_load):
        """Test get_module_names_in_targets_paths handling."""
        mock_load.return_value = None, _CC_NAME_TO_MODULE_INFO
        mod_info = native_module_info.NativeModuleInfo()
        mock_relpath.return_value = (_PATH_TO_MULT_MODULES_WITH_MULTI_ARCH, '')
        result = mod_info.get_module_names_in_targets_paths(['multiarch'])
        self.assertEqual(_TESTABLE_MODULES_WITH_SHARED_PATH, result)


if __name__ == '__main__':
    unittest.main()
