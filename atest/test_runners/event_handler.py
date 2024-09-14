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

"""Atest test event handler class."""

from __future__ import print_function

from collections import deque
from datetime import timedelta
import logging
import time

from atest import atest_execution_info
from atest import atest_utils
from atest import result_reporter
from atest.test_runners import test_runner_base


EVENT_NAMES = {
    'module_started': 'TEST_MODULE_STARTED',
    'module_ended': 'TEST_MODULE_ENDED',
    'run_started': 'TEST_RUN_STARTED',
    'run_ended': 'TEST_RUN_ENDED',
    # Next three are test-level events
    'test_started': 'TEST_STARTED',
    'test_failed': 'TEST_FAILED',
    'test_ended': 'TEST_ENDED',
    'invocation_ended': 'INVOCATION_ENDED',
    # Last two failures are runner-level, not test-level.
    # Invocation failure is broader than run failure.
    'run_failed': 'TEST_RUN_FAILED',
    'invocation_failed': 'INVOCATION_FAILED',
    'test_ignored': 'TEST_IGNORED',
    'test_assumption_failure': 'TEST_ASSUMPTION_FAILURE',
    'log_association': 'LOG_ASSOCIATION',
}

EVENT_PAIRS = {
    EVENT_NAMES['module_started']: EVENT_NAMES['module_ended'],
    EVENT_NAMES['run_started']: EVENT_NAMES['run_ended'],
    EVENT_NAMES['test_started']: EVENT_NAMES['test_ended'],
}
START_EVENTS = list(EVENT_PAIRS.keys())
END_EVENTS = list(EVENT_PAIRS.values())
TEST_NAME_TEMPLATE = '%s#%s'

# time in millisecond.
ONE_SECOND = 1000
ONE_MINUTE = 60000
ONE_HOUR = 3600000

CONNECTION_STATE = {
    'current_test': None,
    'test_run_name': None,
    'last_failed': None,
    'last_ignored': None,
    'last_assumption_failed': None,
    'current_group': None,
    'current_group_total': None,
    'test_count': 0,
    'test_start_time': None,
}


class EventHandleError(Exception):
  """Raised when handle event error."""


class EventHandler:
  """Test Event handle class."""

  def __init__(self, reporter, name):
    self.reporter = reporter
    self.runner_name = name
    self.state = CONNECTION_STATE.copy()
    self.event_stack = deque()
    self.log_associations = []
    self.run_num = 0

  def _module_started(self, event_data):
    if atest_execution_info.PREPARE_END_TIME is None:
      atest_execution_info.PREPARE_END_TIME = time.time()
    self.state['current_group'] = event_data['moduleName']
    self.state['last_failed'] = None
    self.state['current_test'] = None

  def _run_started(self, event_data):
    # Technically there can be more than one run per module.
    self.run_num = event_data.get('runAttempt', 0)
    self.state['test_run_name'] = event_data.setdefault('runName', '')
    self.state['current_group_total'] = event_data['testCount']
    self.state['test_count'] = 0
    self.state['last_failed'] = None
    self.state['current_test'] = None

  def _test_started(self, event_data):
    name = TEST_NAME_TEMPLATE % (
        event_data['className'],
        event_data['testName'],
    )
    self.state['current_test'] = name
    self.state['test_count'] += 1
    self.state['test_start_time'] = event_data['start_time']

  def _test_failed(self, event_data):
    self.state['last_failed'] = {
        'name': TEST_NAME_TEMPLATE % (
            event_data['className'],
            event_data['testName'],
        ),
        'trace': event_data['trace'],
    }

  def _test_ignored(self, event_data):
    name = TEST_NAME_TEMPLATE % (
        event_data['className'],
        event_data['testName'],
    )
    self.state['last_ignored'] = name

  def _test_assumption_failure(self, event_data):
    name = TEST_NAME_TEMPLATE % (
        event_data['className'],
        event_data['testName'],
    )
    self.state['last_assumption_failed'] = name

  def _run_failed(self, event_data):
    # Module and Test Run probably started, but failure occurred.
    self.reporter.process_test_result(
        test_runner_base.TestResult(
            runner_name=self.runner_name,
            group_name=self.state['current_group'],
            test_name=self.state['current_test'],
            status=test_runner_base.ERROR_STATUS,
            details=event_data['reason'],
            test_count=self.state['test_count'],
            test_time='',
            runner_total=None,
            group_total=self.state['current_group_total'],
            additional_info={},
            test_run_name=self.state['test_run_name'],
        )
    )

  def _invocation_failed(self, event_data):
    # Broadest possible failure. May not even start the module/test run.
    self.reporter.process_test_result(
        test_runner_base.TestResult(
            runner_name=self.runner_name,
            group_name=self.state['current_group'],
            test_name=self.state['current_test'],
            status=test_runner_base.ERROR_STATUS,
            details=event_data['cause'],
            test_count=self.state['test_count'],
            test_time='',
            runner_total=None,
            group_total=self.state['current_group_total'],
            additional_info={},
            test_run_name=self.state['test_run_name'],
        )
    )

  def _invocation_ended(self, event_data):
    self.reporter.device_count = event_data.get('device_count', None)

  # pylint: disable=unused-argument
  def _run_ended(self, event_data):
    # Renew ResultReport if is module level(reporter.silent=False)
    if not self.reporter.silent:
      self.reporter.set_current_iteration_summary(self.run_num)
      self.reporter = result_reporter.ResultReporter(silent=False)

  def _module_ended(self, event_data):
    pass

  def _test_ended(self, event_data):
    name = TEST_NAME_TEMPLATE % (
        event_data['className'],
        event_data['testName'],
    )
    test_time = ''
    if self.state['test_start_time']:
      test_time = self._calc_duration(
          event_data['end_time'] - self.state['test_start_time']
      )
    if self.state['last_failed'] and name == self.state['last_failed']['name']:
      status = test_runner_base.FAILED_STATUS
      trace = self.state['last_failed']['trace']
      self.state['last_failed'] = None
    elif (
        self.state['last_assumption_failed']
        and name == self.state['last_assumption_failed']
    ):
      status = test_runner_base.ASSUMPTION_FAILED
      self.state['last_assumption_failed'] = None
      trace = None
    elif self.state['last_ignored'] and name == self.state['last_ignored']:
      status = test_runner_base.IGNORED_STATUS
      self.state['last_ignored'] = None
      trace = None
    else:
      status = test_runner_base.PASSED_STATUS
      trace = None

    default_event_keys = ['className', 'end_time', 'testName']
    additional_info = {}
    for event_key in event_data.keys():
      if event_key not in default_event_keys:
        additional_info[event_key] = event_data.get(event_key, None)

    self.reporter.process_test_result(
        test_runner_base.TestResult(
            runner_name=self.runner_name,
            group_name=self.state['current_group'],
            test_name=name,
            status=status,
            details=trace,
            test_count=self.state['test_count'],
            test_time=test_time,
            runner_total=None,
            additional_info=additional_info,
            group_total=self.state['current_group_total'],
            test_run_name=self.state['test_run_name'],
        )
    )

  def _log_association(self, event_data):
    event_data.setdefault('time', time.time())
    self.log_associations.append(event_data)

  switch_handler = {
      EVENT_NAMES['module_started']: _module_started,
      EVENT_NAMES['run_started']: _run_started,
      EVENT_NAMES['test_started']: _test_started,
      EVENT_NAMES['test_failed']: _test_failed,
      EVENT_NAMES['test_ignored']: _test_ignored,
      EVENT_NAMES['test_assumption_failure']: _test_assumption_failure,
      EVENT_NAMES['run_failed']: _run_failed,
      EVENT_NAMES['invocation_failed']: _invocation_failed,
      EVENT_NAMES['invocation_ended']: _invocation_ended,
      EVENT_NAMES['test_ended']: _test_ended,
      EVENT_NAMES['run_ended']: _run_ended,
      EVENT_NAMES['module_ended']: _module_ended,
      EVENT_NAMES['log_association']: _log_association,
  }

  def process_event(self, event_name, event_data):
    """Process the events of the test run and call reporter with results.

    Args:
        event_name: A string of the event name.
        event_data: A dict of event data.
    """
    logging.debug('Processing %s %s', event_name, event_data)
    if event_name in START_EVENTS:
      self.event_stack.append(event_name)
    elif event_name in END_EVENTS:
      self._check_events_are_balanced(event_name, self.reporter, event_data)
    if event_name in self.switch_handler:
      self.switch_handler[event_name](self, event_data)
    else:
      # TODO(b/128875503): Implement the mechanism to inform not handled
      # TF event.
      logging.debug('Event[%s] is not processable.', event_name)

  def _check_events_are_balanced(
      self, end_event_name, reporter, end_event_data
  ):
    """Check whether the Start events and End events are balanced.

    When imbalance events are detected, and we understand the case of imbalance,
    the events will handled without throwing error; otherwise EventHandleError
    will raise.

    Args:
        end_event_name: A string of the event name.
        reporter: A ResultReporter instance.
        end_event_data: A dict of event data.

    Raises:
        EventHandleError if we can't handle the imbalance of START/END events.
    """
    start_event = self.event_stack.pop() if self.event_stack else None

    def _handle_crashed_test(message):
      atest_utils.print_and_log_error(message)

      self.reporter.process_test_result(
          test_runner_base.TestResult(
              runner_name=self.runner_name,
              group_name=self.state['current_group'],
              test_name=self.state['current_test'],
              status=test_runner_base.ERROR_STATUS,
              details=message,
              test_count=self.state['test_count'],
              test_time='',
              runner_total=None,
              group_total=self.state['current_group_total'],
              additional_info={},
              test_run_name=self.state['test_run_name'],
          )
      )

    if not start_event or EVENT_PAIRS[start_event] != end_event_name:
      # Here bubble up the failed trace in the situation having
      # TEST_FAILED but never receiving TEST_ENDED.
      if self.state['last_failed'] and (
          start_event == EVENT_NAMES['test_started']
      ):
        self.reporter.process_test_result(
            test_runner_base.TestResult(
                runner_name=self.runner_name,
                group_name=self.state['current_group'],
                test_name=self.state['last_failed']['name'],
                status=test_runner_base.FAILED_STATUS,
                details=self.state['last_failed']['trace'],
                test_count=self.state['test_count'],
                test_time='',
                runner_total=None,
                group_total=self.state['current_group_total'],
                additional_info={},
                test_run_name=self.state['test_run_name'],
            )
        )
        # Even though we have proceessed the test result here, we still consider
        # this case unhandled as we don't have a full understanding about the cause.
        # So we don't return here.
        raise EventHandleError(
            'Error: Test failed without receiving a test end event'
        )
      elif (
          end_event_name == EVENT_NAMES['module_ended']
          and start_event == EVENT_NAMES['run_started']
      ):
        _handle_crashed_test(
            'Test run started but did not end. This often happens when the test'
            ' binary/app such as android instrumentation app process died.'
            ' Test count might be inaccurate.'
        )
        return
      elif (
          end_event_name == EVENT_NAMES['run_ended']
          and start_event == EVENT_NAMES['test_started']
      ):
        _handle_crashed_test(
            'Test started but did not end. This often happens when the test'
            ' binary/app such as android instrumentation app process died.'
            ' Test count might be inaccurate.'
        )
        return
      else:
        raise EventHandleError(
            'Error: Saw %s Start event and %s End event. These should be equal!'
            % (start_event, end_event_name)
        )

  @staticmethod
  def _calc_duration(duration):
    """Convert duration from ms to 3h2m43.034s.

    Args:
        duration: millisecond

    Returns:
        string in h:m:s, m:s, s or millis, depends on the duration.
    """
    delta = timedelta(milliseconds=duration)
    timestamp = str(delta).split(':')  # hh:mm:microsec

    if duration < ONE_SECOND:
      return '({}ms)'.format(duration)
    if duration < ONE_MINUTE:
      return '({:.3f}s)'.format(float(timestamp[2]))
    if duration < ONE_HOUR:
      return '({0}m{1:.3f}s)'.format(timestamp[1], float(timestamp[2]))
    return '({0}h{1}m{2:.3f}s)'.format(
        timestamp[0], timestamp[1], float(timestamp[2])
    )
