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

"""Module to assist users providing feedback."""

import sys
from atest.logstorage import log_uploader
from atest.metrics import metrics


_non_redirected_sys_stdout = sys.stdout


def print_feedback_message(is_internal_user=None, is_uploading_logs=None):
  """Print the feedback message to console."""
  if is_internal_user is None:
    is_internal_user = metrics.is_internal_user()
  if is_uploading_logs is None:
    is_uploading_logs = log_uploader.is_uploading_logs()

  if not is_internal_user:
    return

  prefix = 'To report an issue/concern: '
  if is_uploading_logs:
    print(f'{prefix}http://go/from-atest-runid/{metrics.get_run_id()}')
  else:
    print(f'{prefix}http://go/new-atest-issue')
