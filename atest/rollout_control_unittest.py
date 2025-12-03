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

  _FEATURE_NAME = 'test_feature'
  _ENV_CONTROL_FLAG = 'TEST_FEATURE'
  _TEST_USERNAME = 'username'
  _OWNER_USERNAME = 'owner_name'
  _MOCK_HASH_HEX = '32'
  _MOCK_HASH_VALUE = int(_MOCK_HASH_HEX, 16) % 100

  def setUp(self) -> None:
    super().setUp()
    patcher = mock.patch('atest.rollout_control.hashlib.sha256', autospec=True)
    self.mock_sha256 = patcher.start()
    self.addCleanup(patcher.stop)
    # Set the hash to a known value.
    # 0x32 is 50. 50 % 100 is 50.
    self.mock_sha256.return_value.hexdigest.return_value = self._MOCK_HASH_HEX

  def _create_feature(
      self, rollout_percentage: float, owners: list[str] | None = None
  ) -> rollout_control.RolloutControlledFeature:
    return rollout_control.RolloutControlledFeature(
        name=self._FEATURE_NAME,
        rollout_percentage=rollout_percentage,
        env_control_flag=self._ENV_CONTROL_FLAG,
        owners=owners or [],
    )

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

  def _assert_enabled_with_env_flag(
      self, flag_value: str, rollout_percentage: float, expected_enabled: bool
  ) -> None:
    feature = self._create_feature(rollout_percentage=rollout_percentage)
    with mock.patch.dict('os.environ', {self._ENV_CONTROL_FLAG: flag_value}):
      self.assertEqual(feature.is_enabled(), expected_enabled)

  def test_is_enabled_flag_set_to_true_returns_true(self):
    self._assert_enabled_with_env_flag('true', 0, True)

  def test_is_enabled_flag_set_to_1_returns_true(self):
    self._assert_enabled_with_env_flag('1', 0, True)

  def test_is_enabled_flag_set_to_false_returns_false(self):
    self._assert_enabled_with_env_flag('false', 100, False)

  def test_is_enabled_is_owner_returns_true(self):
    feature = self._create_feature(
        rollout_percentage=0, owners=[self._OWNER_USERNAME]
    )

    self.assertFalse(feature.is_enabled(self._TEST_USERNAME))
    self.assertTrue(feature.is_enabled(self._OWNER_USERNAME))


if __name__ == '__main__':
  unittest.main()
