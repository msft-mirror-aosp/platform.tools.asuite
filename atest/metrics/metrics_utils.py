# Copyright 2018, The Android Open Source Project
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

"""Utility functions for metrics."""

import sys
import time
import traceback

from atest.metrics import metrics
from atest.metrics import metrics_base


CONTENT_LICENSES_URL = 'https://source.android.com/setup/start/licenses'
CONTRIBUTOR_AGREEMENT_URL = {
    'INTERNAL': 'https://cla.developers.google.com/',
    'EXTERNAL': 'https://opensource.google.com/docs/cla/',
}
PRIVACY_POLICY_URL = 'https://policies.google.com/privacy'
TERMS_SERVICE_URL = 'https://policies.google.com/terms'


def static_var(varname, value):
  """Decorator to cache static variable."""

  def fun_var_decorate(func):
    """Set the static variable in a function."""
    setattr(func, varname, value)
    return func

  return fun_var_decorate


@static_var('start_time', [])
def get_start_time():
  """Get start time.

  Return:
      start_time: Start time in seconds. Return cached start_time if exists,
      time.time() otherwise.
  """
  if not get_start_time.start_time:
    get_start_time.start_time = time.time()
  return get_start_time.start_time


def convert_duration(diff_time_sec):
  """Compute duration from time difference.

  A Duration represents a signed, fixed-length span of time represented
  as a count of seconds and fractions of seconds at nanosecond
  resolution.

  Args:
      diff_time_sec: The time in seconds as a floating point number.

  Returns:
      A dict of Duration.
  """
  seconds = int(diff_time_sec)
  nanos = int((diff_time_sec - seconds) * 10**9)
  return {'seconds': seconds, 'nanos': nanos}


# pylint: disable=broad-except
def handle_exc_and_send_exit_event(exit_code):
  """handle exceptions and send exit event.

  Args:
      exit_code: An integer of exit code.
  """
  stacktrace = logs = ''
  try:
    exc_type, exc_msg, _ = sys.exc_info()
    stacktrace = traceback.format_exc()
    if exc_type:
      logs = '{etype}: {value}'.format(etype=exc_type.__name__, value=exc_msg)
  except Exception:
    pass
  send_exit_event(exit_code, stacktrace=stacktrace, logs=logs)


def send_exit_event(exit_code, stacktrace='', logs=''):
  """Log exit event and flush all events to clearcut.

  Args:
      exit_code: An integer of exit code.
      stacktrace: A string of stacktrace.
      logs: A string of logs.
  """
  clearcut = metrics.AtestExitEvent(
      duration=convert_duration(time.time() - get_start_time()),
      exit_code=exit_code,
      stacktrace=stacktrace,
      logs=str(logs),
  )
  # pylint: disable=no-member
  if clearcut:
    clearcut.flush_events()


def send_start_event(
    command_line, test_references, cwd, operating_system, source_root, hostname
):
  """Log start event of clearcut.

  Args:
      command_line: A string of the user input command.
      test_references: A string of the input tests.
      cwd: A string of current path.
      operating_system: A string of user's operating system.
      source_root: A string of the Android build source.
      hostname: A string of the host workstation name.
  """
  get_start_time()
  metrics.AtestStartEvent(
      command_line=command_line,
      test_references=test_references,
      cwd=cwd,
      os=operating_system,
      source_root=source_root,
      hostname=hostname,
  )


def print_data_collection_notice(colorful=True):
  """Print the data collection notice."""
  # Do not print notice for external users as we are not collecting any external
  # data.
  if metrics_base.get_user_type() == metrics_base.EXTERNAL_USER:
    return

  red = '31m'
  green = '32m'
  start = '\033[1;'
  end = '\033[0m'
  delimiter = '=' * 18
  notice = (
      'We collect usage statistics (including usernames) in accordance with our '
      'Content Licenses (%s), Contributor License Agreement (%s), Privacy '
      'Policy (%s) and Terms of Service (%s).'
  ) % (
      CONTENT_LICENSES_URL,
      CONTRIBUTOR_AGREEMENT_URL['INTERNAL'],
      PRIVACY_POLICY_URL,
      TERMS_SERVICE_URL,
  )
  if colorful:
    print(f'\n{delimiter}\n{start}{red}Notice:{end}')
    print(f'{start}{green} {notice}{end}\n{delimiter}\n')
  else:
    print(f'\n{delimiter}\nNotice:')
    print(f' {notice}\n{delimiter}\n')
