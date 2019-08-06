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

"""Unittests for aidegen_metrics."""

import unittest
from unittest import mock

from aidegen import constant
from aidegen.lib import aidegen_metrics
from atest import atest_utils


try:
    from asuite.metrics import metrics
    from asuite.metrics import metrics_utils
except ImportError:
    metrics = None
    metrics_utils = None


class AidegenMetricsUnittests(unittest.TestCase):
    """Unit tests for aidegen_metrics.py."""

    @mock.patch.object(metrics, 'AtestStartEvent')
    @mock.patch.object(metrics_utils, 'get_start_time')
    @mock.patch.object(atest_utils, 'print_data_collection_notice')
    def test_starts_asuite_metrics(self, mock_print_data, mock_get_start_time,
                                   mock_start_event):
        """Test starts_asuite_metrics."""
        references = ['nothing']
        aidegen_metrics.starts_asuite_metrics(references)
        if not metrics:
            self.assertFalse(mock_print_data.called)
        else:
            self.assertTrue(mock_print_data.called)
            self.assertTrue(mock_get_start_time.called)
            self.assertTrue(mock_start_event.called)

    @mock.patch.object(metrics_utils, 'send_exit_event')
    def test_ends_asuite_metrics(self, mock_send_exit_event):
        """Test ends_asuite_metrics."""
        exit_code = constant.EXIT_CODE_NORMAL
        aidegen_metrics.ends_asuite_metrics(exit_code)
        if metrics_utils:
            self.assertTrue(mock_send_exit_event.called)


if __name__ == '__main__':
    unittest.main()
