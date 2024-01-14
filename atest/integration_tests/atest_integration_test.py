#!/usr/bin/env python3
#
# Copyright 2023, The Android Open Source Project
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

"""Base test module for Atest integration tests."""

import unittest

import split_build_test_script

# Exporting for test modules' reference
AtestIntegrationTest = split_build_test_script.AtestIntegrationTest

# Exporting for test modules' reference
main = split_build_test_script.main


class AtestTestCase(unittest.TestCase):
    """Base test case for build-test environment split integration tests."""

    injected_config = None

    def create_atest_integration_test(self):
        """Create an instance of atest integration test utility."""
        return AtestIntegrationTest(self.id(), self.injected_config)
