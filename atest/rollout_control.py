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

"""Rollout control for Atest features."""

import functools
import getpass
import hashlib
import logging
import os
from atest import atest_enum
from atest.metrics import metrics


class RolloutControlledFeature:
  """Base class for Atest features under rollout control."""

  def __init__(
      self,
      name: str,
      rollout_percentage: float,
      env_control_flag: str,
      feature_id: int = None,
  ):
    """Initializes the object.

    Args:
        name: The name of the feature.
        rollout_percentage: The percentage of users to enable the feature for.
          The value should be in [0, 100].
        env_control_flag: The environment variable name to override the feature
          enablement. When set, 'true' or '1' means enable, other values means
          disable.
        feature_id: The ID of the feature that is controlled by rollout control
          for metric collection purpose. Must be a positive integer.
    """
    if rollout_percentage < 0 or rollout_percentage > 100:
      raise ValueError(
          'Rollout percentage must be in [0, 100]. Got %s instead.'
          % rollout_percentage
      )
    if feature_id is not None and feature_id <= 0:
      raise ValueError(
          'Feature ID must be a positive integer. Got %s instead.' % feature_id
      )
    self._name = name
    self._rollout_percentage = rollout_percentage
    self._env_control_flag = env_control_flag
    self._feature_id = feature_id

  def _check_env_control_flag(self) -> bool | None:
    """Checks the environment variable to override the feature enablement.

    Returns:
        True if the feature is enabled, False if disabled, None if not set.
    """
    if self._env_control_flag not in os.environ:
      return None
    return os.environ[self._env_control_flag] in ('TRUE', 'True', 'true', '1')

  @functools.cache
  def is_enabled(self, username: str | None = None) -> bool:
    """Checks whether the current feature is enabled for the user.

    Args:
        username: The username to check the feature enablement for. If not
          provided, the current user's username will be used.

    Returns:
        True if the feature is enabled for the user, False otherwise.
    """
    override_flag_value = self._check_env_control_flag()
    if override_flag_value is not None:
      logging.debug(
          'Feature %s is %s by env variable %s.',
          self._name,
          'enabled' if override_flag_value else 'disabled',
          self._env_control_flag,
      )
      if self._feature_id:
        metrics.LocalDetectEvent(
            detect_type=atest_enum.DetectType.ROLLOUT_CONTROLLED_FEATURE_ID_OVERRIDE,
            result=self._feature_id
            if override_flag_value
            else -self._feature_id,
        )
      return override_flag_value

    if self._rollout_percentage == 0:
      return False
    if self._rollout_percentage == 100:
      return True

    if username is None:
      username = getpass.getuser()

    if not username:
      logging.debug(
          'Unable to determine the username. Disabling the feature %s.',
          self._name,
      )
      return False

    hash_object = hashlib.sha256()
    hash_object.update((username + ' ' + self._name).encode('utf-8'))

    is_enabled = (
        int(hash_object.hexdigest(), 16) % 100 < self._rollout_percentage
    )

    logging.debug(
        'Feature %s is %s for user %s.',
        self._name,
        'enabled' if is_enabled else 'disabled',
        username,
    )

    if self._feature_id:
      metrics.LocalDetectEvent(
          detect_type=atest_enum.DetectType.ROLLOUT_CONTROLLED_FEATURE_ID,
          result=self._feature_id if is_enabled else -self._feature_id,
      )

    return is_enabled


disable_bazel_mode_by_default = RolloutControlledFeature(
    name='disable_bazel_mode_by_default',
    rollout_percentage=0,
    env_control_flag='DISABLE_BAZEL_MODE_BY_DEFAULT',
    feature_id=1,
)

rolling_tf_subprocess_output = RolloutControlledFeature(
    name='rolling_tf_subprocess_output',
    rollout_percentage=0,
    env_control_flag='ROLLING_TF_SUBPROCESS_OUTPUT',
    feature_id=2,
)
