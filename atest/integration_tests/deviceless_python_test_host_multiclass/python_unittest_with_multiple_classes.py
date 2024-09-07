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

"""A python unittest script that contains multiple test classes."""


import unittest


class ExampleOneTest(unittest.TestCase):

  def test_example1_pass(self):
    """A test which passes its assertion."""
    self.assertEqual(1, 1)

  def test_example1_fail(self):
    """A test which fails its assertion."""
    self.assertEqual(1, 2, 'Intentional fail')


class ExampleTwoTest(unittest.TestCase):

  def test_example2_pass(self):
    """A test which passes its assertion."""
    self.assertEqual(1, 1)

  def test_example2_fail(self):
    """A test which fails its assertion."""
    self.assertEqual(1, 2, 'Intentional fail')


if __name__ == '__main__':
  unittest.main()
