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

import datetime
import enum
import functools
import getpass
import hashlib
import importlib.resources
import logging
import os
from atest import atest_enum
from atest import atest_utils
from atest.metrics import metrics

_ENABLED_VALUES = {'true', '1'}


@enum.unique
class _RandomizationType(enum.Enum):
  """The type of random selection for the feature rollout control."""

  # Deterministic by user, i.e. same user always gets the same enablement.
  BY_USER = enum.auto()
  # Deterministic by user and day, i.e. same user gets same enablement on the same day.
  BY_USER_DAILY = enum.auto()
  # Randomized based on the atest run_id, applicable to all features uniformly per run.
  BY_RUN_ID = enum.auto()


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
      feature_id: int | None = None,
      owners: list[str] | None = None,
      print_message: str | None = None,
      randomization_type: _RandomizationType = _RandomizationType.BY_USER,
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
        randomization_type: The type of random selection for the feature rollout
          control.
    """
    if rollout_percentage < 0 or rollout_percentage > 100:
      raise ValueError(
          f'Rollout percentage must be in [0, 100]. Got {rollout_percentage}'
          ' instead.'
      )
    if feature_id is not None and feature_id <= 0:
      raise ValueError(
          f'Feature ID must be a positive integer. Got {feature_id} instead.'
      )
    if owners is None:
      owners = _get_project_owners()
    self._name = name
    self._rollout_percentage = rollout_percentage
    self._env_control_flag = env_control_flag
    self._feature_id = feature_id
    self._owners = owners
    self._print_message = print_message
    self._randomization_type = randomization_type

  def _check_env_control_flag(self) -> bool | None:
    """Checks the environment variable to override the feature enablement.

    Returns:
        True if the feature is enabled, False if disabled, None if not set.
    """
    flag_value = os.getenv(self._env_control_flag)
    if flag_value is None:
      return None
    return flag_value.lower() in _ENABLED_VALUES

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
          'Unable to determine the username. Disabling the feature'
          f' {self._name}.'
      )
      return False

    if username in self._owners:
      return True

    hash_object = hashlib.sha256()

    if self._randomization_type == _RandomizationType.BY_RUN_ID:
      hash_object.update(f'{metrics.get_run_id()} {self._name}'.encode('utf-8'))
    else:
      hash_object.update(f'{username} {self._name}'.encode('utf-8'))
      if self._randomization_type == _RandomizationType.BY_USER_DAILY:
        hash_object.update(
            f' {datetime.date.today().isoformat()}'.encode('utf-8')
        )

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
        feature_result = (
            self._feature_id if override_flag_value else -self._feature_id
        )
        metrics.LocalDetectEvent(
            detect_type=atest_enum.DetectType.ROLLOUT_CONTROLLED_FEATURE_ID_OVERRIDE,
            result=feature_result,
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


rolling_tf_subprocess_output = RolloutControlledFeature(
    name='Rolling TradeFed subprocess output',
    rollout_percentage=100,
    env_control_flag='ROLLING_TF_SUBPROCESS_OUTPUT',
    feature_id=2,
    print_message='Rolling subprocess output feature is enabled.',
)

tf_preparer_incremental_setup = RolloutControlledFeature(
    name='TradeFed preparer incremental setup',
    rollout_percentage=100,
    env_control_flag='TF_PREPARER_INCREMENTAL_SETUP',
    feature_id=3,
)

atest_indexing_parallelization = RolloutControlledFeature(
    name='Atest indexing parallelization',
    rollout_percentage=5,
    env_control_flag='ATEST_INDEXING_PARALLEL',
    feature_id=4,
    randomization_type=_RandomizationType.BY_RUN_ID,
)

# TODO: b/462794425 - Tracking bug for AtestExecutionPlanSuiteRunner feature.
use_atest_execution_plan_suite_runner = RolloutControlledFeature(
    name=(
        'Use TF AtestExecutionPlanSuiteRunner when running TestExecutionPlans.'
    ),
    owners=['navil@google.com'],
    rollout_percentage=0,
    env_control_flag='USE_ATEST_EXECUTION_PLAN_SUITE_RUNNER',
    feature_id=5,
    print_message='Running tests using ExecutionPlanSuiteRunner.',
)
