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

"""Unittests for rollout_control."""

import os
import unittest
from unittest import mock

from atest import rollout_control


class RolloutControlledFeatureUnittests(unittest.TestCase):

  _FEATURE_NAME = 'test_feature'
  _ENV_CONTROL_FLAG = 'TEST_FEATURE'
  _TEST_USERNAME = 'username'
  _OWNER_USERNAME = 'owner_name'
  _MOCK_HASH_HEX = '32'
  # 0x32 is 50. 50 % 100 is 50.
  _MOCK_HASH_VALUE = int(_MOCK_HASH_HEX, 16) % 100

  def setUp(self) -> None:
    super().setUp()
    mock_sha256 = self.enterContext(
        mock.patch.object(rollout_control.hashlib, 'sha256', autospec=True)
    )
    self.mock_hash_obj = mock_sha256.return_value
    self.mock_hash_obj.hexdigest.return_value = self._MOCK_HASH_HEX

  def _create_feature(
      self,
      rollout_percentage: float,
      owners: list[str] | None = None,
      randomization_type: rollout_control._RandomizationType = rollout_control._RandomizationType.BY_USER,
  ) -> rollout_control.RolloutControlledFeature:
    return rollout_control.RolloutControlledFeature(
        name=self._FEATURE_NAME,
        rollout_percentage=rollout_percentage,
        env_control_flag=self._ENV_CONTROL_FLAG,
        owners=owners or [],
        randomization_type=randomization_type,
    )

  def _assert_enabled_with_env_flag(
      self, flag_value: str, rollout_percentage: float, expected_enabled: bool
  ) -> None:
    feature = self._create_feature(rollout_percentage=rollout_percentage)
    with mock.patch.dict(os.environ, {self._ENV_CONTROL_FLAG: flag_value}):
      self.assertEqual(feature.is_enabled(), expected_enabled)

  def test_is_enabled_username_hash_is_greater_than_rollout_percentage_returns_false(
      self,
  ):
    # 50 > 49. Returns False.
    feature = self._create_feature(rollout_percentage=self._MOCK_HASH_VALUE - 1)
    self.assertFalse(feature.is_enabled(self._TEST_USERNAME))

  def test_is_enabled_username_hash_is_equal_to_rollout_percentage_returns_false(
      self,
  ):
    # 50 == 50. Returns False.
    feature = self._create_feature(rollout_percentage=self._MOCK_HASH_VALUE)
    self.assertFalse(feature.is_enabled(self._TEST_USERNAME))

  def test_is_enabled_username_hash_is_less_than_rollout_percentage_returns_true(
      self,
  ):
    # 50 < 51. Returns True.
    feature = self._create_feature(rollout_percentage=self._MOCK_HASH_VALUE + 1)
    self.assertTrue(feature.is_enabled(self._TEST_USERNAME))

  def test_is_enabled_username_undetermined_returns_false(self):
    feature = self._create_feature(rollout_percentage=99)
    self.assertFalse(feature.is_enabled(''))

  def test_is_enabled_with_env_control_flag(self):
    """Tests that the environment control flag overrides the rollout percentage."""
    test_cases = [
        ('true', 0, True),
        ('1', 0, True),
        ('false', 100, False),
    ]
    for flag_value, percentage, expected in test_cases:
      with self.subTest(flag_value=flag_value, percentage=percentage):
        self._assert_enabled_with_env_flag(flag_value, percentage, expected)

  def test_is_enabled_is_owner_returns_true(self):
    feature = self._create_feature(
        rollout_percentage=0, owners=[self._OWNER_USERNAME]
    )

    self.assertFalse(feature.is_enabled(self._TEST_USERNAME))
    self.assertTrue(feature.is_enabled(self._OWNER_USERNAME))

  def test_randomized_daily_is_enabled(self):
    """Tests that the date is used in the hash for daily random feature."""
    feature = self._create_feature(
        rollout_percentage=self._MOCK_HASH_VALUE + 1,
        randomization_type=rollout_control._RandomizationType.BY_USER_DAILY,
    )

    with mock.patch.object(
        rollout_control.datetime, 'date', autospec=True
    ) as mock_date:
      mock_date.today.return_value.isoformat.return_value = '2024-01-01'
      self.assertTrue(feature.is_enabled(self._TEST_USERNAME))
      update_calls = [
          mock.call(
              f'{self._TEST_USERNAME} {self._FEATURE_NAME}'.encode('utf-8')
          ),
          mock.call(' 2024-01-01'.encode('utf-8')),
      ]
      self.mock_hash_obj.update.assert_has_calls(update_calls)

  def test_randomized_all_is_enabled(self):
    """Tests that the run_id is used in the hash for ALL random feature."""
    feature = self._create_feature(
        rollout_percentage=self._MOCK_HASH_VALUE + 1,
        randomization_type=rollout_control._RandomizationType.BY_RUN_ID,
    )

    with mock.patch.object(
        rollout_control.metrics, 'get_run_id', autospec=True
    ) as mock_get_run_id:
      mock_get_run_id.return_value = 'test_run_id'
      self.assertTrue(feature.is_enabled(self._TEST_USERNAME))
      update_calls = [
          mock.call(f'test_run_id {self._FEATURE_NAME}'.encode('utf-8')),
      ]
      self.mock_hash_obj.update.assert_has_calls(update_calls)


if __name__ == '__main__':
  unittest.main()
