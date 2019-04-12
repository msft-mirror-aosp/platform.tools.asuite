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

"""Unittests for metrics."""

from __future__ import print_function

import unittest
from unittest import mock

from aidegen.lib import metrics
from atest import atest_utils


class MetricsUnittests(unittest.TestCase):

    """Unit tests for metrics.py"""
    @mock.patch.object(atest_utils, 'is_external_run')
    @mock.patch.object(atest_utils, 'print_data_collection_notice')
    def test_log_usage(self, mock_notice, mock_external_check):
        """Test log_usage always run through the target test function."""
        metrics.log_usage()
        self.assertTrue(mock_notice.called)
        self.assertTrue(mock_external_check.called)


if __name__ == '__main__':
    unittest.main()
