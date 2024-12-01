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

"""Classes to help coordinate running tasks and displaying progress."""

import subprocess
import sys
import threading

from .errors import TaskError


class Task:
  """Defines a task to be run by the task_runner."""

  def __init__(self, cmd, fall_back_tasks=None):
    self.cmd = cmd
    self.fall_back_tasks = fall_back_tasks


class TaskResult:
  """Holds result and status code of a task."""

  def __init__(self, status_code, result=''):
    self.status_code = status_code
    self.result = result


class TaskRunner:
  """Runs a set of tasks and displays progress."""

  def __init__(self):
    self.tasks = {}
    self.task_queue = []

    self.running = False

    # UI
    self.quiet = False
    self.output = ''
    self.running_indicator_thread = None
    self.running_indicator_chars = ['→']
    # self.running_indicator_chars = ['◢', '◣', '◤', '◥']
    self.running_indicator_index = 0
    self.stop_event = threading.Event()

  def add_task(self, name, function, *args, fall_back_tasks=None, **kwargs):
    """Adds a task to the queue."""
    self.tasks[name] = {
        'status': 'pending',
        'function': function,
        'output': '',
        'args': args,
        'kwargs': kwargs,
        'fall_back_tasks': fall_back_tasks,
    }
    self.task_queue.append(name)

  def start(self):
    """Starts running all the tasks in the queue."""
    print('Running Plan:')
    self.running = True
    self._run_next_task()

  def run_task(self, name):
    """Run this task in the queue."""
    task = self.tasks[name]
    self.render_output()
    try:
      for line in task['function'](*task['args'], **task['kwargs']):
        if isinstance(line, TaskResult):
          result = line
          if result.status_code != 0:
            raise TaskError(f'status_code: {result.status_code}')
        else:
          self.tasks[name]['output'] += line
      self.tasks[name]['status'] = 'completed'
      if self.running:
        self._run_next_task()
    except TaskError as e:
      self.tasks[name]['status'] = 'failed'
      self.tasks[name]['output'] += f'Error: {e}\n'
      self.render_output()

      fall_back_tasks = self.tasks[name].get('fall_back_tasks', [])
      if fall_back_tasks:
        self.task_queue = []
        for t in fall_back_tasks:
          if isinstance(t, str):
            self.add_shell_command_task([t])
        self._run_next_task()
      else:
        if self.running:
          self.running = False

  def _run_next_task(self):
    """Runs the next task in the queue."""
    if self.task_queue and self.running:
      name = self.task_queue.pop(0)
      self.tasks[name]['status'] = 'running'
      threading.Thread(target=self.run_task, args=(name,)).start()
    elif self.running:
      self.running = False
      self.render_output()

      if self.quiet:
        return

      print('')
      print('Run Completed Successfully!')
      print('')

  def add_shell_command_task(self, command, fall_back_tasks=None):
    """Adds a shell command to the task queue."""
    self.add_task(
        command, run_shell_command, command, fall_back_tasks=fall_back_tasks
    )

  def render_output(self):
    """Prints the output of the tasks as well as a table showing the progres on the task queue."""
    if self.quiet:
      return

    # os.system('cls' if os.name == 'nt' else 'clear')
    print(f'{self.output}', end='')
    for name, command_data in self.tasks.items():
      print(f"{command_data['output']}", end='')

    for name, command_data in self.tasks.items():
      status_icon = '.'
      status_color = '\033[94m'  # Blue
      if command_data['status'] == 'completed':
        status_icon = '✓'
        status_color = '\033[32m'  # Green
      elif command_data['status'] == 'running':
        status_icon = self.running_indicator_chars[self.running_indicator_index]
        status_color = '\033[32m'  # Green
      elif command_data['status'] == 'failed':
        status_icon = '✗'
        status_color = '\033[91m'  # Red
      print(f'{status_color}{status_icon}\033[0m {name}\033[0m')
    print('-' * 20)


def run_shell_command(command, use_stdout=True):
  """Run a shell command and yield output."""
  last_line = ''

  if use_stdout:
    with subprocess.Popen(
        command,
        shell=True,
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
    ) as process:
      status_code = process.wait()
      yield TaskResult(status_code=status_code)
  else:
    with subprocess.Popen(
        command,
        shell=True,
        text=True,
    ) as process:
      status_code = process.wait()
      for line in iter(process.stdout.readline, ''):
        if line.strip() == last_line:
          continue
        last_line = line.strip()
        yield line
      process.stdout.flush()
      process.stdout.close()
    status_code = process.wait()
    yield TaskResult(status_code=status_code)
