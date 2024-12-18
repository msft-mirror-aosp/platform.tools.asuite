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
"""Update Utils."""


def combine_build_commands(commands):
  """Combines build commands so that m is called once."""
  m_command = ''
  result = []
  for cmd in commands:
    if cmd.startswith('m '):
      m_command += cmd[2:] + ' '
    else:
      result.append(cmd)
  if m_command:
    result.insert(0, 'm ' + m_command.strip())
  return result


def combine_update_commands(commands):
  """Combines update tasks so that a reboot/adevice update is called only once."""
  commands = remove_duplicates_maintain_order(commands)

  # if any command calls for a restart; just do that
  # deduplicate and remove
  if 'adevice update' in commands:
    commands = remove_commands_that_starts_with(commands, 'adevice update')
    commands = remove_commands_that_starts_with(
        commands, 'adb shell "am force-stop'
    )
    commands = ['adevice update'] + commands
  return commands


def remove_duplicates_maintain_order(commands):
  """Removes duplicates while maintaining order."""
  seen = set()
  result = []
  for item in commands:
    if item not in seen:
      seen.add(item)
      result.append(item)
  return result


def remove_commands_that_starts_with(commands, cmd_to_remove):
  """Removes commands that start with a command."""
  result = []
  for cmd in commands:
    if not cmd.startswith(cmd_to_remove):
      result.append(cmd)
  return result
