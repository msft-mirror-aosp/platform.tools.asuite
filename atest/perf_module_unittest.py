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
from atest import perf_module
from atest.test_finders import test_info


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

  def test_is_perf_test_with_args_perf_returns_true(self):
    args = arg_parser.parse_args(['--perf', 'MyModule'])

    res = perf_module.is_perf_test(args)

    self.assertTrue(res)

  def test_is_perf_test_without_perf_returns_false(self):
    args = arg_parser.parse_args(['MyModule'])

    res = perf_module.is_perf_test(args)

    self.assertFalse(res)

  def test_is_perf_test_with_test_infos_perf_suite_returns_true(self):
    test_infos = [
        test_info.TestInfo(
            test_name='MyModule',
            test_runner='MyRunner',
            build_targets=[],
            compatibility_suites=['performance-tests'],
        )
    ]

    res = perf_module.is_perf_test(test_infos=test_infos)

    self.assertTrue(res)

  def test_is_perf_test_with_test_infos_no_perf_suite_returns_false(self):
    test_infos = [
        test_info.TestInfo(
            test_name='MyModule',
            test_runner='MyRunner',
            build_targets=[],
            compatibility_suites=['cts'],
        )
    ]

    res = perf_module.is_perf_test(test_infos=test_infos)

    self.assertFalse(res)

  def test_is_perf_test_with_no_args_and_no_test_infos_returns_false(self):
    res = perf_module.is_perf_test()

    self.assertFalse(res)

  def test_set_default_argument_values_sets_request_upload_result_if_not_disabled(
      self,
  ):
    args = arg_parser.parse_args(['MyModule'])

    perf_module.set_default_argument_values(args)

    self.assertTrue(args.request_upload_result)

  def test_set_default_argument_values_does_not_set_request_upload_result_if_disabled(
      self,
  ):
    args = arg_parser.parse_args(['--disable-upload-result', 'MyModule'])

    perf_module.set_default_argument_values(args)

    self.assertFalse(args.request_upload_result)


if __name__ == '__main__':
  unittest.main()
