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
import unittest
from .update import Core
from .update import get_aliases
from .update import SystemServer
from .update import SysUI
from .update import Update


class UpdateTest(unittest.TestCase):

  def test_get_aliases(self):
    aliases = get_aliases()
    self.assertIn('core', aliases)
    self.assertIn('systemserver', aliases)
    self.assertIn('sysui', aliases)

    self.assertIs(aliases['core'], Core)
    self.assertIs(aliases['systemserver'], SystemServer)
    self.assertIs(aliases['sysui'], SysUI)

  def test_gather_tasks_default(self):
    update = Update()
    tasks, fall_back_tasks = update.gather_tasks('')
    self.assertEqual(tasks, ['m sync', 'adevice update'])
    self.assertEqual(fall_back_tasks, ['m droid', 'flashall'])

  def test_gather_tasks_alias(self):
    update = Update()
    tasks, fall_back_tasks = update.gather_tasks('core')
    self.assertEqual(
        tasks, ['m framework framework-minus-apex', 'adevice update']
    )
    self.assertEqual(fall_back_tasks, [])


if __name__ == '__main__':
  unittest.main()
