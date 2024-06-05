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


# Keep it disabled until we can tell the capability of tmux.
_DISABLE_HYPER_LINK_FORMAT_BY_DEFAULT = True


_non_redirected_sys_stdout = sys.stdout


def print_feedback_message(
    is_internal_user=None, is_uploading_logs=None, use_hyper_link=None
):
  """Print the feedback message to console."""
  if is_internal_user is None:
    is_internal_user = metrics.is_internal_user()
  if is_uploading_logs is None:
    is_uploading_logs = log_uploader.is_uploading_logs()
  if use_hyper_link is None:
    use_hyper_link = (
        not _DISABLE_HYPER_LINK_FORMAT_BY_DEFAULT
        and getattr(_non_redirected_sys_stdout, 'isatty', lambda: False)()
    )

  if not is_internal_user:
    return

  if use_hyper_link:
    print_link = lambda text, target: print(
        f'\u001b]8;;{target}\u001b\\{text}\u001b]8;;\u001b\\'
    )
    if is_uploading_logs:
      print_link(
          'Click here to share feedback about this atest run.',
          f'http://go/atest-feedback/{metrics.get_run_id()}',
      )
    else:
      print_link(
          'Click here to share feedback about atest.',
          'http://go/atest-feedback-aosp',
      )
  else:
    if is_uploading_logs:
      print(
          'To share feedback about this run:\n'
          f'http://go/atest-feedback/{metrics.get_run_id()}'
      )
    else:
      print('To share feedback about atest: http://go/atest-feedback-aosp')
