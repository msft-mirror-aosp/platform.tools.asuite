#!/usr/bin/env python3
#
# Copyright 2021, The Android Open Source Project
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

"""Unit tests for bazel_mode."""

import tempfile
import unittest

from unittest import mock
# pylint: disable=import-error
from pyfakefs import fake_filesystem_unittest

import bazel_mode
import constants
import module_info

from test_finders import test_info
from test_runners import atest_tf_test_runner


ATEST_TF_RUNNER = atest_tf_test_runner.AtestTradefedTestRunner.NAME
BAZEL_RUNNER = bazel_mode.BazelTestRunner.NAME
MODULE_BUILD_TARGETS = {'foo1', 'foo2', 'foo3'}
MODULE_NAME = 'foo'

class DecorateFinderMethodTest(fake_filesystem_unittest.TestCase):
    """Tests for _decorate_find_method()."""

    # pylint: disable=missing-function-docstring
    def setUp(self):
        self.setUpPyfakefs()

    # pylint: disable=protected-access
    # pylint: disable=missing-function-docstring
    # TODO(b/197600827): Add self._env in Module_info instead of mocking
    #                    os.environ directly.
    @mock.patch.dict('os.environ', {constants.ANDROID_BUILD_TOP:'/'})
    def test_unit_test_runner_is_overridden(self):
        original_find_method = lambda obj, test_id:(
            self.create_single_test_infos(obj, test_id, test_name=MODULE_NAME,
                                          runner=ATEST_TF_RUNNER))
        mod_info = self.create_single_test_module_info(MODULE_NAME,
                                                  is_unit_test=True)
        new_find_method = bazel_mode._decorate_find_method(
            mod_info, original_find_method)

        test_infos = new_find_method('finder_obj', 'test_id')

        self.assertEqual(len(test_infos), 1)
        self.assertEqual(test_infos[0].test_runner, BAZEL_RUNNER)

    # pylint: disable=protected-access
    # pylint: disable=missing-function-docstring
    @mock.patch.dict('os.environ', {constants.ANDROID_BUILD_TOP:'/'})
    def test_not_unit_test_runner_is_preserved(self):
        original_find_method = lambda obj, test_id:(
            self.create_single_test_infos(obj, test_id, test_name=MODULE_NAME,
                                          runner=ATEST_TF_RUNNER))
        mod_info = self.create_single_test_module_info(MODULE_NAME,
                                                  is_unit_test=False)
        new_find_method = bazel_mode._decorate_find_method(
            mod_info, original_find_method)

        test_infos = new_find_method('finder_obj', 'test_id')

        self.assertEqual(len(test_infos), 1)
        self.assertEqual(test_infos[0].test_runner, ATEST_TF_RUNNER)

    # pylint: disable=unused-argument
    def create_single_test_infos(self, obj, test_id, test_name=MODULE_NAME,
                                 runner=ATEST_TF_RUNNER):
        """Create list of test_info.TestInfo."""
        return [test_info.TestInfo(test_name, runner, MODULE_BUILD_TARGETS)]

    def create_single_test_module_info(self, module_name, is_unit_test=True):
        """Create module-info file with single module."""
        set_as_unit_test = 'true'
        if not is_unit_test:
            set_as_unit_test = 'false'
        unit_test_mod_info_content = ('{"%s": {"class": ["NATIVE_TESTS"],' +
                                      ' "is_unit_test": "%s" }}') % (
                                          module_name, set_as_unit_test)
        fake_temp_file_name = next(tempfile._get_candidate_names())
        self.fs.create_file(fake_temp_file_name,
                            contents=unit_test_mod_info_content)
        return module_info.ModuleInfo(module_file=fake_temp_file_name)



if __name__ == '__main__':
    unittest.main()
