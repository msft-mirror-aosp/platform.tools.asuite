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

"""Command line utility for running Android workflows and productivity tools."""

import argparse
import logging
import os
import sys

from tools.update import Update

logger = logging.getLogger(__name__)
os.environ['PYTHONUNBUFFERED'] = '1'  # No latency for output.


tools_map = {
    'update': Update,
}


def run():
  """Entry point for tool."""
  parser = argparse.ArgumentParser(
      description='Run workflows to build update and test modules',
      formatter_class=argparse.RawDescriptionHelpFormatter,
  )
  parser.add_argument(
      '-q',
      '--quiet',
      action='store_true',
      help='Do not display progress updates',
  )
  subparsers = parser.add_subparsers(dest='name')
  for name in tools_map:
    tools_map[name].add_parser(subparsers)

  args = parser.parse_args()
  name = args.name.lower()

  # Tools
  if name in tools_map:
    tool = tools_map[name]()
    return tool.main(args)


if __name__ == '__main__':
  logging.basicConfig(
      level=logging.ERROR,
      handlers=[
          logging.FileHandler(f"{os.environ.get('OUT', '/tmp')}/a_tool.log"),
          logging.StreamHandler(sys.stderr),
      ],
  )
  run()
