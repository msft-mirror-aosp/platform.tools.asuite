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

import argparse

from core.errors import WorkflowError
from core.task_runner import Task
from core.task_runner import TaskRunner
from tools.update_aliases import get_aliases
from tools.update_utils import combine_build_commands
from tools.update_utils import combine_update_commands


class Update:
  """Updates a device."""

  def __init__(self, args):
    self.args = args

  @classmethod
  def add_parser(cls, subparsers):
    """Parse command line update arguments."""

    aliases = get_aliases()
    epilog = 'Aliases:\n'
    for alias in get_aliases().keys():
      name = alias
      build_commands = (';').join(aliases[name].build())
      update_commands = (';').join(aliases[name].update())
      epilog += f'  {name}:\n\t{build_commands}\n\t{update_commands}\n'

    parser = subparsers.add_parser(
        'update', epilog=epilog, formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument('alias', nargs='*', default=[], type=str)
    parser.add_argument(
        '--build-only',
        action='store_true',
        help='only build the specified targets, do not update the device.',
    )
    parser.add_argument(
        '--update-only',
        action='store_true',
        help=(
            'only update the device with prebuilt targets, do not build'
            ' targets.'
        ),
    )
    parser.add_argument(
        '--list-aliases',
        action='store_true',
        help='list aliases; used for autocomplete',
    )

  def main(self):
    """Main entrypoint for Update."""

    if self.args.list_aliases:
      print(' '.join(get_aliases().keys()))
      return

    tasks = self.gather_tasks()
    self.run_tasks(tasks)

  def gather_tasks(self):
    """Gathers tasks to run based on alias."""
    tasks = []
    build_tasks = []
    update_tasks = []

    requested_aliases = self.args.alias
    aliases = get_aliases()
    for a in requested_aliases:
      if a not in aliases:
        raise WorkflowError(f'unknown alias: {a}')
      config = aliases[a]
      build_tasks += config.build()
      update_tasks += config.update()

    # combine build tasks
    build_tasks = combine_build_commands(build_tasks)
    # combine update tasks
    update_tasks = combine_update_commands(update_tasks)

    if self.args.build_only:
      tasks = build_tasks
    elif self.args.update_only:
      tasks = update_tasks
    else:
      tasks = build_tasks + update_tasks

    if not tasks:
      # If no tasks run adevice update with a fall back to a full flash.
      tasks = [
          'm sync',
          Task(
              cmd='adevice update',
              fall_back_tasks=[
                  'm droid',
                  'flashall',
              ],
          ),
      ]
    return tasks

  def run_tasks(self, tasks):
    """Runs tasks."""
    task_runner = TaskRunner()
    task_runner.quiet = False
    for task in tasks:
      if isinstance(task, str):
        task_runner.add_shell_command_task(task)
      elif isinstance(task, Task):
        task_runner.add_shell_command_task(task.cmd, task.fall_back_tasks)
      else:
        task_runner.add_task(task)
    task_runner.start()
