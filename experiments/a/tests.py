#!/usr/bin/env python3
#
# Copyright 2024 - The Android Open Source Project
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
#
"""Gathers and runs all tests."""

import importlib
import unittest

if __name__ == '__main__':
  test_modules = ['tools.update_test']

  for mod in test_modules:
    importlib.import_module(mod)
  loader = unittest.defaultTestLoader
  test_suite = loader.loadTestsFromNames(test_modules)
  runner = unittest.TextTestRunner(verbosity=2)
  runner.run(test_suite)
