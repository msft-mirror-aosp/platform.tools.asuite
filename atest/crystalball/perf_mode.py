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
from atest.test_finders import test_info

PERF_TEST_TEMPLATE = 'template/performance-tests-base'
PERF_MODE_ARG_NAME = '--perf'


def add_arguments(parser: argparse.ArgumentParser):
  """Adds perf-related arguments to the argument parser.

  Args:
    parser: An argparse.ArgumentParser object.
  """
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
  """Processes perf-related arguments.

  Args:
    args: The arguments parsed by argparse.
  """
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
    print(  # TODO(jinghuanwen): update or remove this message
        atest_utils.mark_magenta(
            'Perf arguments simplification experimental feature was triggered.'
            ' If you like the change please +1 to b/12345, or leave comments if'
            ' you have feedbacks.'
        )
    )


def add_global_arguments(parser: argparse.ArgumentParser):
  """Adds perf-related arguments to the global argument parser.

  Args:
    parser: An argparse.ArgumentParser object.
  """

  parser.add_argument(
      PERF_MODE_ARG_NAME,
      action='store_true',
      help=(
          '(For performance tests) Enable performance test mode. This option'
          ' enables some performance-related arguments and logic in atest.'
      ),
  )

  parser.add_argument(
      '--aggregate-metric-filter',
      action='append',
      help=(
          '(For performance tests) Regular expression that will be used for'
          ' filtering the aggregated metrics.'
      ),
  )

  parser.add_argument(
      '--perf-itr-metrics',
      action='store_true',
      help='(For performance tests) Print individual performance metric.',
  )


def is_perf_test(
    args: argparse.Namespace = None, test_infos: list[test_info.TestInfo] = None
):
  """Check if it is a performance test.

  Args:
    args: The arguments parsed by argparse.
    test_infos: The list of TestInfo objects.

  Returns:
    True if it is a performance test, False otherwise or not enough information
    to determine.
  """
  if args and getattr(args, PERF_MODE_ARG_NAME.replace('-', ''), False):
    return True

  if test_infos:
    return any(
        'performance-tests' in info.compatibility_suites for info in test_infos
    )

  return False


def set_default_argument_values(args: argparse.Namespace):
  """Sets default values for perf-related arguments.

  Args:
    args: The arguments parsed by argparse.
  """
  if not args.disable_upload_result:
    args.request_upload_result = True
