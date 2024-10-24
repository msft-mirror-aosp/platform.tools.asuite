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

"""Unittests for event_handler."""


from importlib import reload
import unittest
from unittest import mock

from atest.test_runners import atest_tf_test_runner as atf_tr
from atest.test_runners import event_handler as e_h
from atest.test_runners import test_runner_base


class _Event:

  def __init__(self):
    self.events = []

  def get_events(self):
    return self.events

  def add_test_module_started(self, name):
    self.events.append((
        'TEST_MODULE_STARTED',
        {
            'moduleContextFileName': 'serial-util1146216{974}2772610436.ser',
            'moduleName': name,
        },
    ))
    return self

  def add_test_module_ended(self, data):
    self.events.append(('TEST_MODULE_ENDED', data))
    return self

  def add_test_run_started(self, name, count):
    self.events.append((
        'TEST_RUN_STARTED',
        {
            'testCount': count,
            'runName': name,
        },
    ))
    return self

  def add_test_run_failed(self, reason):
    self.events.append((
        'TEST_RUN_FAILED',
        {
            'reason': reason,
        },
    ))
    return self

  def add_test_run_ended(self, data):
    self.events.append(('TEST_RUN_ENDED', data))
    return self

  def add_test_started(self, start_time, class_name, test_name):
    self.events.append((
        'TEST_STARTED',
        {
            'start_time': start_time,
            'className': class_name,
            'testName': test_name,
        },
    ))
    return self

  def add_test_ignored(self, class_name, test_name, trace):
    self.events.append((
        'TEST_IGNORED',
        {
            'className': class_name,
            'testName': test_name,
            'trace': trace,
        },
    ))
    return self

  def add_test_ended(self, end_time, class_name, test_name, **kwargs):
    self.events.append((
        'TEST_ENDED',
        {
            'end_time': end_time,
            'className': class_name,
            'testName': test_name,
        }
        | kwargs,
    ))
    return self

  def add_test_failed(self, class_name, test_name, trace):
    self.events.append((
        'TEST_FAILED',
        {
            'className': class_name,
            'testName': test_name,
            'trace': trace,
        },
    ))
    return self

  def add_invocation_failed(self, reason):
    self.events.append((
        'INVOCATION_FAILED',
        {
            'cause': reason,
        },
    ))
    return self


class EventHandlerUnittests(unittest.TestCase):
  """Unit tests for event_handler.py"""

  def setUp(self):
    reload(e_h)
    self.mock_reporter = mock.Mock()
    self.fake_eh = e_h.EventHandler(
        self.mock_reporter, atf_tr.AtestTradefedTestRunner.NAME
    )

  def tearDown(self):
    mock.patch.stopall()

  def test_process_event_normal_results(self):
    """Test process_event method for normal test results."""
    events = (
        _Event()
        .add_test_module_started('someTestModule')
        .add_test_run_started('com.android.UnitTests', 2)
        .add_test_started(52, 'someClassName', 'someTestName')
        .add_test_ended(1048, 'someClassName', 'someTestName')
        .add_test_started(48, 'someClassName2', 'someTestName2')
        .add_test_failed('someClassName2', 'someTestName2', 'someTrace')
        .add_test_ended(9876450, 'someClassName2', 'someTestName2')
        .add_test_run_ended({})
        .add_test_module_ended({'foo': 'bar'})
        .get_events()
    )
    for name, data in events:
      self.fake_eh.process_event(name, data)
    call1 = mock.call(
        test_runner_base.TestResult(
            runner_name=atf_tr.AtestTradefedTestRunner.NAME,
            group_name='someTestModule',
            test_name='someClassName#someTestName',
            status=test_runner_base.PASSED_STATUS,
            details=None,
            test_count=1,
            test_time='(996ms)',
            runner_total=None,
            group_total=2,
            additional_info={},
            test_run_name='com.android.UnitTests',
        )
    )
    call2 = mock.call(
        test_runner_base.TestResult(
            runner_name=atf_tr.AtestTradefedTestRunner.NAME,
            group_name='someTestModule',
            test_name='someClassName2#someTestName2',
            status=test_runner_base.FAILED_STATUS,
            details='someTrace',
            test_count=2,
            test_time='(2h44m36.402s)',
            runner_total=None,
            group_total=2,
            additional_info={},
            test_run_name='com.android.UnitTests',
        )
    )
    self.mock_reporter.process_test_result.assert_has_calls([call1, call2])

  def test_process_event_run_failure(self):
    """Test process_event method run failure."""
    events = (
        _Event()
        .add_test_module_started('someTestModule')
        .add_test_run_started('com.android.UnitTests', 2)
        .add_test_started(10, 'someClassName', 'someTestName')
        .add_test_run_failed('someRunFailureReason')
        .get_events()
    )
    for name, data in events:
      self.fake_eh.process_event(name, data)
    call = mock.call(
        test_runner_base.TestResult(
            runner_name=atf_tr.AtestTradefedTestRunner.NAME,
            group_name='someTestModule',
            test_name='someClassName#someTestName',
            status=test_runner_base.ERROR_STATUS,
            details='someRunFailureReason',
            test_count=1,
            test_time='',
            runner_total=None,
            group_total=2,
            additional_info={},
            test_run_name='com.android.UnitTests',
        )
    )
    self.mock_reporter.process_test_result.assert_has_calls([call])

  def test_process_event_invocation_failure(self):
    """Test process_event method with invocation failure."""
    events = (
        _Event()
        .add_test_run_started('com.android.UnitTests', None)
        .add_invocation_failed('someInvocationFailureReason')
        .get_events()
    )
    for name, data in events:
      self.fake_eh.process_event(name, data)
    call = mock.call(
        test_runner_base.TestResult(
            runner_name=atf_tr.AtestTradefedTestRunner.NAME,
            group_name=None,
            test_name=None,
            status=test_runner_base.ERROR_STATUS,
            details='someInvocationFailureReason',
            test_count=0,
            test_time='',
            runner_total=None,
            group_total=None,
            additional_info={},
            test_run_name='com.android.UnitTests',
        )
    )
    self.mock_reporter.process_test_result.assert_has_calls([call])

  def test_process_event_missing_test_run_started_event(self):
    """Test process_event method for normal test results."""
    events = (
        _Event()
        .add_test_started(52, 'someClassName', 'someTestName')
        .add_test_ended(1048, 'someClassName', 'someTestName')
        .get_events()
    )
    for name, data in events:
      self.fake_eh.process_event(name, data)
    call = mock.call(
        test_runner_base.TestResult(
            runner_name=atf_tr.AtestTradefedTestRunner.NAME,
            group_name=None,
            test_name='someClassName#someTestName',
            status=test_runner_base.PASSED_STATUS,
            details=None,
            test_count=1,
            test_time='(996ms)',
            runner_total=None,
            group_total=None,
            additional_info={},
            test_run_name=None,
        )
    )
    self.mock_reporter.process_test_result.assert_has_calls([call])

  # pylint: disable=protected-access
  def test_process_event_test_run_end_without_test_end_throws(self):
    """Test process_event method with start/end event name not balanced."""
    events = (
        _Event()
        .add_test_module_started('someTestModule')
        .add_test_run_started('com.android.UnitTests', 2)
        .add_test_started(10, 'someClassName', 'someTestName')
        .add_test_ended(18, 'someClassName', 'someTestName')
        .add_test_started(19, 'someClassName', 'someTestName')
        .add_test_failed('someClassName2', 'someTestName2', 'someTrace')
        .get_events()
    )

    for name, data in events:
      self.fake_eh.process_event(name, data)
    call = mock.call(
        test_runner_base.TestResult(
            runner_name=atf_tr.AtestTradefedTestRunner.NAME,
            group_name='someTestModule',
            test_name='someClassName#someTestName',
            status=test_runner_base.PASSED_STATUS,
            details=None,
            test_count=1,
            test_time='(8ms)',
            runner_total=None,
            group_total=2,
            additional_info={},
            test_run_name='com.android.UnitTests',
        )
    )
    self.mock_reporter.process_test_result.assert_has_calls([call])
    # Event pair: TEST_STARTED -> TEST_RUN_ENDED
    # It should raise TradeFedExitError in _check_events_are_balanced()
    name = 'TEST_RUN_ENDED'
    data = {}
    self.assertRaises(
        e_h.EventHandleError,
        self.fake_eh._check_events_are_balanced,
        name,
        data,
        self.mock_reporter,
    )

  def test_process_event_module_end_without_test_run_end_no_throw(self):
    """Test process_event method with start/end event name not balanced."""
    events = (
        _Event()
        .add_test_module_started('someTestModule')
        .add_test_run_started('com.android.UnitTests', 2)
        .add_test_module_ended({'foo': 'bar'})
        .get_events()
    )
    for name, data in events[:-1]:
      self.fake_eh.process_event(name, data)

    self.fake_eh.process_event(*events[-1])

  def test_process_event_run_end_without_test_end_no_throw(self):
    """Test process_event method with start/end event name not balanced."""
    events = (
        _Event()
        .add_test_module_started('someTestModule')
        .add_test_run_started('com.android.UnitTests', 2)
        .add_test_started(10, 'someClassName', 'someTestName')
        .add_test_run_ended({})
        .get_events()
    )
    for name, data in events[:-1]:
      self.fake_eh.process_event(name, data)

    self.fake_eh.process_event(*events[-1])

  def test_process_event_ignore(self):
    """Test _process_event method for normal test results."""
    events = (
        _Event()
        .add_test_module_started('someTestModule')
        .add_test_run_started('com.android.UnitTests', 2)
        .add_test_started(8, 'someClassName', 'someTestName')
        .add_test_ended(18, 'someClassName', 'someTestName')
        .add_test_started(28, 'someClassName2', 'someTestName2')
        .add_test_ignored('someClassName2', 'someTestName2', 'someTrace')
        .add_test_ended(90, 'someClassName2', 'someTestName2')
        .add_test_run_ended({})
        .add_test_module_ended({'foo': 'bar'})
        .get_events()
    )
    for name, data in events:
      self.fake_eh.process_event(name, data)
    call1 = mock.call(
        test_runner_base.TestResult(
            runner_name=atf_tr.AtestTradefedTestRunner.NAME,
            group_name='someTestModule',
            test_name='someClassName#someTestName',
            status=test_runner_base.PASSED_STATUS,
            details=None,
            test_count=1,
            test_time='(10ms)',
            runner_total=None,
            group_total=2,
            additional_info={},
            test_run_name='com.android.UnitTests',
        )
    )
    call2 = mock.call(
        test_runner_base.TestResult(
            runner_name=atf_tr.AtestTradefedTestRunner.NAME,
            group_name='someTestModule',
            test_name='someClassName2#someTestName2',
            status=test_runner_base.IGNORED_STATUS,
            details=None,
            test_count=2,
            test_time='(62ms)',
            runner_total=None,
            group_total=2,
            additional_info={},
            test_run_name='com.android.UnitTests',
        )
    )
    self.mock_reporter.process_test_result.assert_has_calls([call1, call2])

  def test_process_event_with_additional_info(self):
    """Test process_event method with perf information."""
    events = (
        _Event()
        .add_test_module_started('someTestModule')
        .add_test_run_started('com.android.UnitTests', 2)
        .add_test_started(52, 'someClassName', 'someTestName')
        .add_test_ended(1048, 'someClassName', 'someTestName')
        .add_test_started(48, 'someClassName2', 'someTestName2')
        .add_test_failed('someClassName2', 'someTestName2', 'someTrace')
        .add_test_ended(
            9876450,
            'someClassName2',
            'someTestName2',
            cpu_time='1234.1234(ns)',
            real_time='5678.5678(ns)',
            iterations='6666',
        )
        .add_test_started(10, 'someClassName3', 'someTestName3')
        .add_test_ended(
            70,
            'someClassName3',
            'someTestName3',
            additional_info_min='102773',
            additional_info_mean='105973',
            additional_info_median='103778',
        )
        .add_test_run_ended({})
        .add_test_module_ended({'foo': 'bar'})
        .get_events()
    )
    for name, data in events:
      self.fake_eh.process_event(name, data)
    call1 = mock.call(
        test_runner_base.TestResult(
            runner_name=atf_tr.AtestTradefedTestRunner.NAME,
            group_name='someTestModule',
            test_name='someClassName#someTestName',
            status=test_runner_base.PASSED_STATUS,
            details=None,
            test_count=1,
            test_time='(996ms)',
            runner_total=None,
            group_total=2,
            additional_info={},
            test_run_name='com.android.UnitTests',
        )
    )

    test_additional_info = {
        'cpu_time': '1234.1234(ns)',
        'real_time': '5678.5678(ns)',
        'iterations': '6666',
    }
    call2 = mock.call(
        test_runner_base.TestResult(
            runner_name=atf_tr.AtestTradefedTestRunner.NAME,
            group_name='someTestModule',
            test_name='someClassName2#someTestName2',
            status=test_runner_base.FAILED_STATUS,
            details='someTrace',
            test_count=2,
            test_time='(2h44m36.402s)',
            runner_total=None,
            group_total=2,
            additional_info=test_additional_info,
            test_run_name='com.android.UnitTests',
        )
    )

    test_additional_info2 = {
        'additional_info_min': '102773',
        'additional_info_mean': '105973',
        'additional_info_median': '103778',
    }
    call3 = mock.call(
        test_runner_base.TestResult(
            runner_name=atf_tr.AtestTradefedTestRunner.NAME,
            group_name='someTestModule',
            test_name='someClassName3#someTestName3',
            status=test_runner_base.PASSED_STATUS,
            details=None,
            test_count=3,
            test_time='(60ms)',
            runner_total=None,
            group_total=2,
            additional_info=test_additional_info2,
            test_run_name='com.android.UnitTests',
        )
    )
    self.mock_reporter.process_test_result.assert_has_calls(
        [call1, call2, call3]
    )


if __name__ == '__main__':
  unittest.main()
