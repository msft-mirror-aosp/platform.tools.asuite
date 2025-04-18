#!/usr/bin/env python
#
# Copyright 2025, The Android Open Source Project
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

import argparse
import copy
from atest import atest_utils


def add_arguments(parser: argparse.ArgumentParser):
  """Adds perf-related arguments to the argument parser."""
  parser.add_argument(
      '--iter',
      type=int,
      help='(For performance tests) Perf iteration ...',  # TODO(jinghuanwen): add help message
  )

  parser.add_argument(  # TODO(jinghuanwen): update this option
      '--class',
      dest='class_name',
      help='(For performance tests) some class name.',
  )


def process_parsed_args(args: argparse.Namespace):
  """Processes perf-related arguments."""
  original_args = copy.deepcopy(args)

  if args.iter:
    module_name = args.tests[0]
    module_arg = f'{module_name}:{{com.android.tradefed.testtype.AndroidJUnitTest}}instrumentation-arg:iterations:={args.iter}'
    args.custom_args.append('--module-arg')
    args.custom_args.append(module_arg)
    print(
        f'Converting argument "--iter {args.iter}" to "--module-arg'
        f' {module_arg}"'
    )

  if args.class_name:  # TODO(jinghuanwen): update this option
    module_name = args.tests[0]
    args.custom_args.append('--module-arg')
    args.custom_args.append(
        f'{module_name}:{{com.android.tradefed.testtype.AndroidJUnitTest}}instrumentation-arg:class:={args.class_name}'
    )

  if str(original_args) != str(args):
    print(
        atest_utils.mark_magenta(
            'Perf arguments simplification experimental feature was triggered.'
            ' If you like the change please +1 to b/12345, or leave comments if'
            ' you have feedbacks.'
        )
    )
