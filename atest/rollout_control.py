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
import importlib.resources
import logging
import os
from atest import atest_enum
from atest import atest_utils
from atest.metrics import metrics


@functools.cache
def _get_project_owners() -> list[str]:
  """Returns the owners of the feature."""
  owners = []
  try:
    with importlib.resources.as_file(
        importlib.resources.files('atest').joinpath('OWNERS')
    ) as version_file_path:
      owners.extend(version_file_path.read_text(encoding='utf-8').splitlines())
  except (ModuleNotFoundError, FileNotFoundError) as e:
    logging.error(e)
  try:
    with importlib.resources.as_file(
        importlib.resources.files('atest').joinpath('OWNERS_ADTE_TEAM')
    ) as version_file_path:
      owners.extend(version_file_path.read_text(encoding='utf-8').splitlines())
  except (ModuleNotFoundError, FileNotFoundError) as e:
    logging.error(e)
  return [line.split('@')[0] for line in owners if '@google.com' in line]


class RolloutControlledFeature:
  """Base class for Atest features under rollout control."""

  def __init__(
      self,
      name: str,
      rollout_percentage: float,
      env_control_flag: str,
      feature_id: int = None,
      owners: list[str] | None = None,
      print_message: str | None = None,
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
        owners: The owners of the feature. If not provided, the owners of the
          feature will be read from OWNERS file.
        print_message: The message to print to the console when the feature is
          enabled for the user.
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
    if owners is None:
      owners = _get_project_owners()
    self._name = name
    self._rollout_percentage = rollout_percentage
    self._env_control_flag = env_control_flag
    self._feature_id = feature_id
    self._owners = owners
    self._print_message = print_message

  def _check_env_control_flag(self) -> bool | None:
    """Checks the environment variable to override the feature enablement.

    Returns:
        True if the feature is enabled, False if disabled, None if not set.
    """
    if self._env_control_flag not in os.environ:
      return None
    return os.environ[self._env_control_flag] in ('TRUE', 'True', 'true', '1')

  def _is_enabled_for_user(self, username: str | None) -> bool:
    """Checks whether the feature is enabled for the user.

    Args:
        username: The username to check the feature enablement for. If not
          provided, the current user's username will be used.

    Returns:
        True if the feature is enabled for the user, False otherwise.
    """
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

    if username in self._owners:
      return True

    hash_object = hashlib.sha256()
    hash_object.update((username + ' ' + self._name).encode('utf-8'))
    return int(hash_object.hexdigest(), 16) % 100 < self._rollout_percentage

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

    is_enabled = self._is_enabled_for_user(username)

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

    if is_enabled and self._print_message:
      print(atest_utils.mark_magenta(self._print_message))

    return is_enabled


deprecate_bazel_mode = RolloutControlledFeature(
    name='Deprecate Bazel Mode',
    rollout_percentage=100,
    env_control_flag='DEPRECATE_BAZEL_MODE',
    feature_id=1,
)

rolling_tf_subprocess_output = RolloutControlledFeature(
    name='Rolling TradeFed subprocess output',
    rollout_percentage=100,
    env_control_flag='ROLLING_TF_SUBPROCESS_OUTPUT',
    feature_id=2,
    print_message=(
        atest_utils.mark_magenta(
            'Rolling subprocess output feature is enabled: http://b/380460196.'
        )
    ),
)

tf_preparer_incremental_setup = RolloutControlledFeature(
    name='TradeFed preparer incremental setup',
    rollout_percentage=100,
    env_control_flag='TF_PREPARER_INCREMENTAL_SETUP',
    feature_id=3,
    print_message=(
        atest_utils.mark_magenta(
            'You are one of the first users selected to receive the'
            ' "Incremental setup for TradeFed preparers" feature. If you are'
            ' happy with it, please +1 on http://b/381900378. If you'
            ' experienced any issues, please comment on the same bug.'
        )
    ),
)
