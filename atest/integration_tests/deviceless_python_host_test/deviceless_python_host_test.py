#!/usr/bin/env python3
#
# Copyright 2024, The Android Open Source Project
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

import unittest


class DevicelessPythonHostTest(unittest.TestCase):
  """Simple python host unit test."""

  @classmethod
  def setUpClass(cls):
    super(DevicelessPythonHostTest, cls).setUpClass()

  @classmethod
  def tearDownClass(cls):
    super(DevicelessPythonHostTest, cls).tearDownClass()

  def setUp(self):
    super().setUp()

  def tearDown(self):
    super().tearDown()

  def test_passing_test_1of2(self):
    self.assertTrue(True)

  def test_passing_test_2of2(self):
    self.assertTrue(True)

  def test_failing_test_1of1(self):
    self.assertTrue(False, 'Intentionally failed test')


if __name__ == '__main__':
  unittest.main(verbosity=3)
