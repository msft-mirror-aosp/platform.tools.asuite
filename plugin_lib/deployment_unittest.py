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

"""Unittests for deployment."""
import subprocess
import unittest
from unittest import mock

from deployment import PluginDeployment


# pylint: disable=protected-access
class DeploymentUnittests(unittest.TestCase):
    """Unit tests for deployment.py."""

    @mock.patch('builtins.input')
    def test_ask_for_install(self, mock_input):
        """Test _ask_for_install."""
        mock_input.return_value = 'y'
        PluginDeployment()._ask_for_install()
        self.assertTrue(mock_input.call)

    @mock.patch.object(subprocess, 'check_call')
    def test_build_jars(self, mock_check_call):
        """Test _build_jars."""
        PluginDeployment()._build_jars()
        self.assertTrue(mock_check_call.call)
