#!/usr/bin/env python3
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

"""Unittests for smart_test_filter."""

# pylint: disable=invalid-name

import pathlib
import unittest
from atest import constants
from atest.test_finders.smart_test_finder import smart_test_filter
from pyfakefs import fake_filesystem_unittest


_FAKE_LOOKUP_TABLE_CONTENT = """branch,target,test_name,test_id,postsubmit_pass_rate,test_run_duration_ms_past7days
some_branch,some_target,TestA,a_id,0.99,10000
some_branch2,some_target2,TestFlakyTest,b_id,0.90,500
some_branch3,some_target3,TestRunTimeNotFound,c_id,0.99,-1
some_branch4,some_target4,TestD,d_id,0.99,40000
some_branch6,some_target6,TestF,f_id,0.99,500
some_branch7,some_target7,TestG,g_id,0.98,5
some_branch5,some_target5,TestNotSelectedDueToTimeLimit,e_id,0.99,20000
some_branch8,some_target8,TestNotSelectedDueToTimeLimit2,h_id,0.98,5
some_branch2,some_target2,TestWithoutModule,j_id,0.99,500
some_branch2,some_target2,TestWithoutTestClass,k_id,0.99,500
some_branch9,some_target9,TestWithOptedOutTests,l_id,1,2"""


# pylint: disable=protected-access
class SmartTestFilterUnittests(fake_filesystem_unittest.TestCase):
  """Unit tests for smart_test_filter.py."""

  def setUp(self):
    super().setUp()
    self.setUpPyfakefs()

    self.fake_lookup_table_path = str(
        pathlib.Path(constants.SMART_TEST_SELECTION_ROOT_PATH)
        / 'lookup_tables/tests_with_runtime_and_pass_rate.csv'
    )
    self.fs.create_file(
        self.fake_lookup_table_path,
        contents=_FAKE_LOOKUP_TABLE_CONTENT,
    )

  def test_get_selected_test_classes(self):
    candidate_tests = [
        # TestA is selected and ranked first, because it has the highest
        # relevance score.
        smart_test_filter.TestClassInfo(
            test_id='a_id',
            atp_test_name='TestA',
            branch='some_branch',
            target='some_target',
            module='TestAModule',
            test_class='testAClass',
            score=1,
        ),
        # This test is not selected because of no history in the lookup table.
        smart_test_filter.TestClassInfo(
            test_id='id_not_found',
            atp_test_name='SomeTest',
            branch='some_branch',
            target='some_target',
            module='SomeTestModule',
            test_class='testSomeClass',
            score=0.98,
        ),
        # This test is not selected because the module name is missing.
        smart_test_filter.TestClassInfo(
            test_id='g_id',
            atp_test_name='TestWithoutModule',
            branch='some_branch2',
            target='some_target2',
            test_class='testClass',
            score=1.0,
        ),
        # This test is not selected because the test class name is missing.
        smart_test_filter.TestClassInfo(
            test_id='h_id',
            atp_test_name='TestWithoutTestClass',
            branch='some_branch2',
            target='some_target2',
            module='TestWithoutTestClass',
            score=0.99,
        ),
        # This test is not selected because the passing rate of this test class
        # was only 0.90, less than the threshold 0.95.
        smart_test_filter.TestClassInfo(
            test_id='b_id',
            atp_test_name='TestFlakyTest',
            branch='some_branch2',
            target='some_target2',
            module='SomeTestModule',
            test_class='testSomeClass',
            score=0.99,
        ),
        # This test is not selected because the execution time history of this
        # test is missing.
        smart_test_filter.TestClassInfo(
            test_id='c_id',
            atp_test_name='TestRunTimeNotFound',
            branch='some_branch3',
            target='some_target3',
            module='SomeTestModule',
            test_class='testSomeClass',
            score=0.995,
        ),
        # TestD is selected and ranked right after TestA, because it has the
        # second highest relevance score.
        smart_test_filter.TestClassInfo(
            test_id='d_id',
            atp_test_name='TestD',
            branch='some_branch4',
            target='some_target4',
            module='TestDModule',
            test_class='testDClass',
            score=0.98,
        ),
        # After TestA, TestD, TestF and TestG are selected, selecting this test
        # would result in exceeding the estimated execution time (in this test,
        # the user specified the time limit to be one minute), so this test is
        # not selected.
        smart_test_filter.TestClassInfo(
            test_id='e_id',
            atp_test_name='TestNotSelectedDueToTimeLimit',
            branch='some_branch5',
            target='some_target5',
            module='TestEModule',
            test_class='testEClass',
            score=0.95,
        ),
        # TestF is selected and ranked right after TestD, because it has the
        # third highest relevance score.
        smart_test_filter.TestClassInfo(
            test_id='f_id',
            atp_test_name='TestF',
            branch='some_branch6',
            target='some_target6',
            module='testFModule',
            test_class='testFClass',
            score=0.96,
        ),
        # TestG is selected and ranked right after TestF, because it has the
        # fourth highest relevance score of all valid tests.
        smart_test_filter.TestClassInfo(
            test_id='g_id',
            atp_test_name='TestG',
            branch='some_branch7',
            target='some_target7',
            module='TestGModule',
            test_class='testGClass',
            score=0.97,
        ),
        # When the decision of not selecting TestNotSelectedDueToTimeLimit was
        # made, we no longer look into the details of other tests with even
        # lower relevant scores, so this test is not selected.
        smart_test_filter.TestClassInfo(
            test_id='h_id',
            atp_test_name='TestNotSelectedDueToTimeLimit2',
            branch='some_branch8',
            target='some_target8',
            module='SomeTestModule',
            test_class='testSomeClass',
            score=0.949,
        ),
        # This test is not selected because the test module is in the opted-out
        # list.
        smart_test_filter.TestClassInfo(
            test_id='l_id',
            atp_test_name='TestWithOptedOutTests',
            branch='some_branch9',
            target='some_target9',
            module='aconfig.test.cpp',
            test_class='testGClass',
            score=1,
        ),
    ]
    expected_selected_tests = [
        smart_test_filter.TestClassInfo(
            test_id='a_id',
            atp_test_name='TestA',
            branch='some_branch',
            target='some_target',
            module='TestAModule',
            test_class='testAClass',
            score=1,
        ),
        smart_test_filter.TestClassInfo(
            test_id='d_id',
            atp_test_name='TestD',
            branch='some_branch4',
            target='some_target4',
            module='TestDModule',
            test_class='testDClass',
            score=0.98,
        ),
        smart_test_filter.TestClassInfo(
            test_id='g_id',
            atp_test_name='TestG',
            branch='some_branch7',
            target='some_target7',
            module='TestGModule',
            test_class='testGClass',
            score=0.97,
        ),
        smart_test_filter.TestClassInfo(
            test_id='f_id',
            atp_test_name='TestF',
            branch='some_branch6',
            target='some_target6',
            module='testFModule',
            test_class='testFClass',
            score=0.96,
        ),
    ]

    actual_selected_tests = smart_test_filter.get_selected_test_classes(
        candidate_tests,
        time_limit_min=1,
    )

    # Since this function guarantees order, so directly use `assertEqual`
    # instead of `assertCountEqual`.
    self.assertEqual(actual_selected_tests, expected_selected_tests)


if __name__ == '__main__':
  unittest.main()
