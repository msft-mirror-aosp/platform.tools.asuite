#!/usr/bin/env python3
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

import unittest
from unittest import mock
from atest import rollout_control


class RolloutControlledFeatureUnittests(unittest.TestCase):

  def test_is_enabled_username_hash_is_greater_than_rollout_percentage_returns_false(
      self,
  ):
    sut = rollout_control.RolloutControlledFeature(
        name='test_feature',
        rollout_percentage=66,
        env_control_flag='TEST_FEATURE',
    )

    self.assertFalse(sut.is_enabled('username'))

  def test_is_enabled_username_hash_is_equal_to_rollout_percentage_returns_false(
      self,
  ):
    sut = rollout_control.RolloutControlledFeature(
        name='test_feature',
        rollout_percentage=67,
        env_control_flag='TEST_FEATURE',
    )

    self.assertFalse(sut.is_enabled('username'))

  def test_is_enabled_username_hash_is_less_or_equal_than_rollout_percentage_returns_true(
      self,
  ):
    sut = rollout_control.RolloutControlledFeature(
        name='test_feature',
        rollout_percentage=68,
        env_control_flag='TEST_FEATURE',
    )

    self.assertTrue(sut.is_enabled('username'))

  def test_is_enabled_username_undetermined_returns_false(self):
    sut = rollout_control.RolloutControlledFeature(
        name='test_feature',
        rollout_percentage=99,
        env_control_flag='TEST_FEATURE',
    )

    self.assertFalse(sut.is_enabled(''))

  def test_is_enabled_flag_set_to_true_returns_true(self):
    sut = rollout_control.RolloutControlledFeature(
        name='test_feature',
        rollout_percentage=0,
        env_control_flag='TEST_FEATURE',
    )

    with mock.patch.dict('os.environ', {'TEST_FEATURE': 'true'}):
      self.assertTrue(sut.is_enabled())

  def test_is_enabled_flag_set_to_1_returns_true(self):
    sut = rollout_control.RolloutControlledFeature(
        name='test_feature',
        rollout_percentage=0,
        env_control_flag='TEST_FEATURE',
    )

    with mock.patch.dict('os.environ', {'TEST_FEATURE': '1'}):
      self.assertTrue(sut.is_enabled())

  def test_is_enabled_flag_set_to_false_returns_false(self):
    sut = rollout_control.RolloutControlledFeature(
        name='test_feature',
        rollout_percentage=100,
        env_control_flag='TEST_FEATURE',
    )

    with mock.patch.dict('os.environ', {'TEST_FEATURE': 'false'}):
      self.assertFalse(sut.is_enabled())

  def test_is_enabled_is_owner_returns_true(self):
    sut = rollout_control.RolloutControlledFeature(
        name='test_feature',
        rollout_percentage=0,
        env_control_flag='TEST_FEATURE',
        owners=['owner_name'],
    )

    self.assertFalse(sut.is_enabled('name'))
    self.assertTrue(sut.is_enabled('owner_name'))
