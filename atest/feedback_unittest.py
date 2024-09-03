# Copyright (C) 2024 The Android Open Source Project
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
from unittest.mock import patch
from atest import feedback
from atest.metrics import metrics


class FeedbackTest(unittest.TestCase):

  @patch('builtins.print')
  def test_get_buganizer_url_internal_user_prints_feedback(self, mock_print):
    feedback.print_feedback_message(
        is_internal_user=True, is_uploading_logs=True
    )

    mock_print.assert_called_once()

  @patch('builtins.print')
  def test_get_buganizer_url_external_user_no_prints(self, mock_print):
    feedback.print_feedback_message(
        is_internal_user=False, is_uploading_logs=True
    )

    mock_print.assert_not_called()

  @patch('builtins.print')
  def test_get_buganizer_url_is_uploading_logs_use_contains_run_id(
      self, mock_print
  ):
    feedback.print_feedback_message(
        is_internal_user=True, is_uploading_logs=True
    )

    mock_print.assert_called_once()
    self.assertIn(metrics.get_run_id(), mock_print.call_args[0][0])

  @patch('builtins.print')
  def test_get_buganizer_url_is_not_uploading_logs_does_use_contains_run_id(
      self, mock_print
  ):
    feedback.print_feedback_message(
        is_internal_user=True, is_uploading_logs=False
    )

    mock_print.assert_called_once()
    self.assertNotIn(metrics.get_run_id(), mock_print.call_args[0][0])
