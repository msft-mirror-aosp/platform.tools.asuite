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
import argparse
import unittest
from .update import Core
from .update import get_aliases
from .update import SystemServer
from .update import SysUI
from .update import Update


class UpdateTest(unittest.TestCase):

  def setUp(self):
    super().setUp()
    args = argparse.Namespace()
    args.build_only = False
    args.update_only = False
    args.alias = []
    self.args = args

  def test_get_aliases(self):
    aliases = get_aliases()
    self.assertIn('core', aliases)
    self.assertIn('systemserver', aliases)
    self.assertIn('sysui', aliases)

    self.assertIs(aliases['core'].__class__, Core)
    self.assertIs(aliases['systemserver'].__class__, SystemServer)
    self.assertIs(aliases['sysui'].__class__, SysUI)

    # Test that definitions from json are found
    self.assertIn('wifi', aliases)
    self.assertIn('sdk_sandbox', aliases)

  def test_gather_tasks_default(self):
    update = Update(self.args)
    tasks = update.gather_tasks()
    self.assertEqual(tasks[0], 'm sync')
    self.assertEqual(tasks[1].cmd, 'adevice update')
    self.assertEqual(tasks[1].fall_back_tasks, ['m droid', 'flashall'])

  def test_gather_tasks_alias(self):

    self.args.alias = ['core']
    update = Update(self.args)

    tasks = update.gather_tasks()
    self.assertEqual(
        tasks, ['m framework framework-minus-apex', 'adevice update']
    )

  def test_gather_tasks_build_only(self):
    self.args.alias = ['core']
    self.args.build_only = True

    update = Update(self.args)
    tasks = update.gather_tasks()
    self.assertEqual(tasks, ['m framework framework-minus-apex'])

  def test_gather_tasks_update_only(self):
    self.args.alias = ['core']
    self.args.update_only = True

    update = Update(self.args)
    tasks = update.gather_tasks()
    self.assertEqual(tasks, ['adevice update'])


if __name__ == '__main__':
  unittest.main()
