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

"""Unittests for project_config."""

from __future__ import print_function

import os
import unittest
from unittest import mock

from aidegen.lib import project_config
from aidegen.lib import common_util


class AidegenProjectConfigUnittests(unittest.TestCase):
    """Unit tests for project_config.py"""

    @mock.patch.object(os, 'getcwd')
    def test_is_whole_android_tree(self, mock_getcwd):
        """Test _is_whole_android_tree with different conditions."""
        self.assertTrue(project_config.is_whole_android_tree(['a'], True))
        mock_getcwd.return_value = common_util.get_android_root_dir()
        self.assertTrue(project_config.is_whole_android_tree([''], False))
        self.assertFalse(project_config.is_whole_android_tree(['a'], False))


if __name__ == '__main__':
    unittest.main()
