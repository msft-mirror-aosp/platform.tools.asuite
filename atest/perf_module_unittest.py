#!/usr/bin/env python
#
# Copyright 2025, The Android Open Source Project
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
from atest import arg_parser


class TestPerfModule(unittest.TestCase):

  def test_process_parsed_args_adds_iter_to_custom_args(self):
    argv = ['--perf', '--iter', '12345', 'MyModule']

    args = arg_parser.parse_args(argv)

    self.assertTrue(any('12345' in arg for arg in args.custom_args))

  def test_parse_args_with_perf_and_iter_sets_iter_attribute(self):
    argv = ['--perf', '--iter', '10', 'MyModule']

    args = arg_parser.parse_args(argv)

    self.assertTrue(hasattr(args, 'iter'))
    self.assertEqual(args.iter, 10)

  def test_parse_args_without_perf_does_not_set_iter_attribute(self):
    argv = ['--iter', '10', 'MyModule']

    args = arg_parser.parse_args(argv)

    self.assertFalse(hasattr(args, 'iter'))


if __name__ == '__main__':
  unittest.main()
