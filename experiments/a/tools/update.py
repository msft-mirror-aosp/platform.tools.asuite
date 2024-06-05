#!/usr/bin/env python3
#
# Copyright 2024 - The Android Open Source Project
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
#

"""Update Tool."""

import inspect
import os
import sys

from core.errors import WorkflowError
from core.task_runner import TaskRunner


class Update:
  """Updates a device."""

  @classmethod
  def add_parser(cls, subparsers):
    """Parse update alias/arguments."""
    parser = subparsers.add_parser('update', help='Updates a device')
    parser.add_argument(
        'alias', nargs='?', default='default', type=str, help='alias'
    )

  def main(self, args):
    """Main entrypoint for Update."""
    alias = args.alias
    tasks, fall_back_tasks = self.gather_tasks(alias)
    self.run_tasks(tasks, fall_back_tasks)

  def gather_tasks(self, alias):
    """Gathers tasks to run based on alias."""
    tasks = []
    fall_back_tasks = []

    aliases = get_aliases()
    if alias in aliases:
      config = aliases[alias]()
      tasks += config.build()
      tasks += config.update()
    else:
      # default
      tasks = [
          'm sync',
          'adevice update',
      ]
      fall_back_tasks = [
          'm droid',
          'flashall',
      ]
    return (tasks, fall_back_tasks)

  def run_tasks(self, tasks, fall_back_tasks):
    """Runs tasks."""
    task_runner = TaskRunner()
    task_runner.quiet = False
    for task in tasks:
      if isinstance(task, str):
        task_runner.add_shell_command_task(task)
      else:
        task_runner.add_task(task)
    task_runner.fall_back_tasks = fall_back_tasks
    task_runner.start()


class Alias:
  """Base class for defining an alias."""

  def build(self):
    return []

  def update(self):
    return []


class Core(Alias):
  """Alias for Core."""

  def build(self):
    return ['m framework framework-minus-apex']

  def update(self):
    return [
        'adevice update',
    ]


class SystemServer(Alias):
  """Alias for SystemServer."""

  def update(self):
    return [
        'adevice update --restart=none',
        'adb kill systemserver',
    ]


class SysUI(Alias):
  """Alias for SystemUI."""

  def build(self):
    if is_nexus():
      raise WorkflowError(
          "Target 'sysui' is not allowed on Nexus Experience devices.\n"
          'Try sysuig (with g at the end) or sysuititan'
      )
    return ['m framework framework-minus-apex SystemUI']

  def update(self):
    target = 'com.android.systemui'
    return [
        'adevice update --restart=none',
        f'adb shell am force-stop {target}',
    ]


class SysUIG(Alias):
  """Alias for SystemUI for Google Devices."""

  def build(self):
    if not is_nexus():
      raise WorkflowError(
          "Target 'sysuig' is only allowed on Nexus Experience devices.\n"
          'Try sysui (no g at the end)'
      )
    return ['m framework framework-minus-apex SystemUIGoogle']

  def update(self):
    target = 'com.android.systemui'
    return [
        'adevice update --restart=none',
        f'adb shell am force-stop {target}',
    ]


class SysUITitan(Alias):
  """Alias for SystemUI Titan devices."""

  def build(self):
    if not is_nexus():
      raise WorkflowError(
          "Target 'sysuititan' is only allowed on Nexus Experience devices.\n"
          'Try sysui (no g at the end)'
      )
    return ['m framework framework-minus-apex SystemUITitan']

  def update(self):
    target = 'com.android.systemui'
    return [
        'adevice update --restart=none',
        f'adb shell am force-stop {target}',
    ]


class SysUIGo(Alias):
  """Alias for SystemUI."""

  def build(self):
    if not is_nexus():
      raise WorkflowError(
          "Target 'sysuigo' is only allowed on Nexus Experience devices.\n"
          'Try sysui (no go at the end)'
      )
    return ['m framework framework-minus-apex SystemUIGo']

  def update(self):
    target = 'com.android.systemui'
    return [
        'adevice update --restart=none',
        f'adb shell am force-stop {target}',
    ]


class CarSysUI(Alias):
  """Alias for CarSystemUI."""

  def build(self):
    return ['m framework framework-minus-apex CarSystemUI']

  def update(self):
    target = 'com.android.systemui'
    return [
        'adevice update --restart=none',
        f'adb shell am force-stop {target}',
    ]


class CarSysUIG(Alias):
  """Alias for CarSystemUI."""

  def build(self):
    return ['m framework framework-minus-apex AAECarSystemUI']

  def update(self):
    target = 'com.android.systemui'
    return [
        'adevice update --restart=none',
        f'adb shell am force-stop {target}',
    ]


# Utilities to get type of target
def is_nexus():
  target_product = os.getenv('TARGET_PRODUCT')
  return (
      target_product.startswith('.aosp')
      or 'wembley' in target_product
      or 'gms_humuhumu' in target_product
  )


def get_aliases():
  return {
      name.lower(): cls
      for name, cls in inspect.getmembers(
          sys.modules[__name__], inspect.isclass
      )
      if issubclass(cls, Alias) and cls != Alias
  }
