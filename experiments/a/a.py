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
      description='A runs tools and workflows for local Android development',
      formatter_class=argparse.RawDescriptionHelpFormatter,
  )
  subparsers = parser.add_subparsers(dest='tool')
  for _, tool_class in tools_map.items():
    tool_class.add_parser(subparsers)

  args = parser.parse_args()

  # Tool
  if not args.tool:
    print('Error: Please specify a tool (eg. update)')
    parser.print_help()
    return 1
  tool_name = args.tool.lower()
  tool = tools_map[tool_name](args)
  return tool.main()


if __name__ == '__main__':
  logging.basicConfig(
      level=logging.ERROR,
      handlers=[
          logging.FileHandler(f"{os.environ.get('OUT', '/tmp')}/a_tool.log"),
          logging.StreamHandler(sys.stderr),
      ],
  )
  run()
