#!/usr/bin/env python3
#
# Copyright 2023, The Android Open Source Project
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

"""Tool used to compute the test filter for cc tests.

This tool reuses the ATest's logic to compute the test filter.

Usage:
    ./cc_test_filter_generator.py --out <path to output file> \
      --class-file <path to cc file> \
      --class-file <path to cc file> \
      --class-method-reference ClassA#method1,method2 \
      --class-method-reference ClassB#method3 \
      --class-method-reference ClassC
"""

import argparse
from collections import defaultdict, deque
import enum
import os

from tools.asuite.atest import constants_default
from tools.asuite.atest.test_finders import test_filter_utils


@enum.unique
class CCCommentType(enum.Enum):
  BLOCK_COMMENT = '/*'
  LINE_COMMENT = '//'
  NO_COMMENT = 'no comment'


def trim_comments(content):
  """Replace comments with single spaces.

  Each character in the comment should be replaced by a space.

  There are two kinds of comments:
      1. Block comments begin with /* and continue until the next */. Block
      comments do not nest:
          /* this is /* one comment */ text outside comment

      2. Line comments begin with // and continue to the end of the current
      line. Line comments do not nest either, but it does not matter, because
      they would end in the same place anyway.

  It is safe to put line comments inside block comments, or vice versa:

      /* block comment
         // contains line comment
         yet more comment
       */ outside comment

      // line comment /* contains block comment */
  """
  trimmed_lines = []
  lines = deque(content.splitlines())

  while lines:
    line = lines.popleft()
    comment_type, index = _get_comment_type(line)

    if comment_type == CCCommentType.NO_COMMENT:
      trimmed_lines.append(line.rstrip())
    elif comment_type == CCCommentType.LINE_COMMENT:
      trimmed_line = line[:index]
      trimmed_lines.append(trimmed_line.rstrip())
      continue
    else:
      code_lines = []
      code_line, comment_ended = _handle_block_comment_line(line[index + 2 :])

      # Replace each character in the comment by a single space including
      # '/*' and '*/'.
      code_line = f'{line[:index]}  {code_line}'
      code_lines.append(code_line)
      while not comment_ended and lines:
        code_line, comment_ended = _handle_block_comment_line(lines.popleft())
        code_lines.append(code_line)

      # Add the code lines back into unprocessed lines to handle the case
      # like /* x */ code /* x */.
      while code_lines:
        lines.appendleft(code_lines.pop())

  return '\n'.join(trimmed_lines).strip('\n')


def _handle_block_comment_line(line):
  if not line:
    return '', False

  head, sep, tail = line.partition('*/')
  if sep:
    return ' ' * (len(head) + len(sep)) + tail, True

  return ' ' * len(line), False


def _get_comment_type(line):
  line_comment_idx = line.find(CCCommentType.LINE_COMMENT.value)
  block_comment_idx = line.find(CCCommentType.BLOCK_COMMENT.value)

  if line_comment_idx == -1 and block_comment_idx == -1:
    return CCCommentType.NO_COMMENT, -1

  if line_comment_idx != -1 and (
      block_comment_idx == -1 or line_comment_idx < block_comment_idx
  ):
    return CCCommentType.LINE_COMMENT, line_comment_idx

  return CCCommentType.BLOCK_COMMENT, block_comment_idx


def _parse_class_method_reference(class_method_reference):
  class_name, separator, methods_str = class_method_reference.partition('#')

  if not separator:
    if ',' in class_name:
      raise ValueError(
          'Test methods must follow their class name separated by a `#`, '
          'for example, class#method1,method2'
      )
    return class_name, []

  return class_name, methods_str.split(',')


def _get_test_filters(args):
  class_to_methods = defaultdict(set)
  for class_method_reference in args.class_method_reference:
    class_name, methods = _parse_class_method_reference(class_method_reference)
    class_to_methods[class_name].update(methods)

  class_info = {}
  for class_file in args.class_file:
    if not constants_default.CC_EXT_RE.match(class_file):
      continue

    if not os.path.isfile(class_file):
      continue

    with open(class_file, 'r', encoding='utf-8') as f:
      info, _ = test_filter_utils.get_cc_class_info(trim_comments(f.read()))

    class_info.update(info)

  test_filters = []
  for cls, methods in class_to_methods.items():
    if cls not in class_info:
      raise ValueError(f'Class, {cls}, not found in the source files!')

    test_filters.append(
        test_filter_utils.get_cc_filter(class_info, cls, methods)
    )

  return test_filters


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--out', required=True, help='Write output to <file>')
  parser.add_argument(
      '--class-file',
      action='append',
      default=[],
      help='Get the class information from the <file>',
  )
  parser.add_argument(
      '--class-method-reference',
      action='append',
      default=[],
      help='Compute the cc test filter to match this class and methods',
  )
  args = parser.parse_args()

  test_filters = []
  if args.class_method_reference and args.class_file:
    test_filters = _get_test_filters(args)

  with open(args.out, 'w', encoding='utf-8') as f:
    f.write(':'.join(test_filters))


if __name__ == '__main__':
  main()
