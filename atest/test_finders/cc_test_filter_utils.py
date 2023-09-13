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

import logging
import re
import shutil
import subprocess
import tempfile

from contextlib import contextmanager


# Gtest Types
GTEST_REGULAR = 'regular native test'
GTEST_TYPED = 'typed test'
GTEST_TYPED_PARAM = 'typed-parameterized test'
GTEST_PARAM = 'value-parameterized test'


# Macros that used in GTest. Detailed explanation can be found in
# $ANDROID_BUILD_TOP/external/googletest/googletest/samples/sample*_unittest.cc
# 1. Traditional Tests:
#   TEST(class, method)
#   TEST_F(class, method)
# 2. Type Tests:
#   TYPED_TEST_SUITE(class, types)
#     TYPED_TEST(class, method)
# 3. Value-parameterized Tests:
#   TEST_P(class, method)
#     INSTANTIATE_TEST_SUITE_P(Prefix, class, param_generator, name_generator)
# 4. Type-parameterized Tests:
#   TYPED_TEST_SUITE_P(class)
#     TYPED_TEST_P(class, method)
#       REGISTER_TYPED_TEST_SUITE_P(class, method)
#         INSTANTIATE_TYPED_TEST_SUITE_P(Prefix, class, Types)
# Macros with (class, method) pattern.
CC_CLASS_METHOD_RE = re.compile(
    r'^\s*(TYPED_TEST(?:|_P)|TEST(?:|_F|_P))\s*\(\s*'
    r'(?P<class_name>\w+),\s*(?P<method_name>\w+)\)\s*\{', re.M)
# Macros with (prefix, class, ...) pattern.
# Note: Since v1.08, the INSTANTIATE_TEST_CASE_P was replaced with
#   INSTANTIATE_TEST_SUITE_P. However, Atest does not intend to change the
#   behavior of a test, so we still search *_CASE_* macros.
CC_PARAM_CLASS_RE = re.compile(
    r'^\s*INSTANTIATE_(?:|TYPED_)TEST_(?:SUITE|CASE)_P\s*\(\s*'
    r'(?P<instantiate>\w+),\s*(?P<class>\w+)\s*,', re.M)
# Type/Type-parameterized Test macros:
TYPE_CC_CLASS_RE = re.compile(
    r'^\s*TYPED_TEST_SUITE(?:|_P)\(\s*(?P<class_name>\w+)', re.M)


def get_cc_class_info(class_file_content):
    """Get the class info of the given cc class file content.

    The class info dict will be like:
        {'classA': {
            'methods': {'m1', 'm2'}, 'prefixes': {'pfx1'}, 'typed': True},
         'classB': {
            'methods': {'m3', 'm4'}, 'prefixes': set(), 'typed': False},
         'classC': {
            'methods': {'m5', 'm6'}, 'prefixes': set(), 'typed': True},
         'classD': {
            'methods': {'m7', 'm8'}, 'prefixes': {'pfx3'}, 'typed': False}}
    According to the class info, we can tell that:
        classA is a typed-parameterized test. (TYPED_TEST_SUITE_P)
        classB is a regular gtest.            (TEST_F|TEST)
        classC is a typed test.               (TYPED_TEST_SUITE)
        classD is a value-parameterized test. (TEST_P)

    Args:
        class_file_content: Content of the cc class file.

    Returns:
        A tuple of a dict of class info and a list of classes that have no test.
    """
    # ('TYPED_TEST', 'PrimeTableTest', 'ReturnsTrueForPrimes')
    method_matches = re.findall(CC_CLASS_METHOD_RE, class_file_content)
    # ('OnTheFlyAndPreCalculated', 'PrimeTableTest2')
    prefix_matches = re.findall(CC_PARAM_CLASS_RE, class_file_content)
    # 'PrimeTableTest'
    typed_matches = re.findall(TYPE_CC_CLASS_RE, class_file_content)

    classes = {cls[1] for cls in method_matches}
    class_info = {}
    for cls in classes:
        class_info.setdefault(cls, {'methods': set(),
                                    'prefixes': set(),
                                    'typed': False})

    no_test_classes = []

    logging.debug('Probing TestCase.TestName pattern:')
    for match in method_matches:
        if class_info.get(match[1]):
            logging.debug('  Found %s.%s', match[1], match[2])
            class_info[match[1]]['methods'].add(match[2])
        else:
            no_test_classes.append(match[1])

    # Parameterized test.
    logging.debug('Probing InstantiationName/TestCase pattern:')
    for match in prefix_matches:
        if class_info.get(match[1]):
            logging.debug('  Found %s/%s', match[0], match[1])
            class_info[match[1]]['prefixes'].add(match[0])
        else:
            no_test_classes.append(match[1])

    # Typed test
    logging.debug('Probing typed test names:')
    for match in typed_matches:
        if class_info.get(match):
            logging.debug('  Found %s', match)
            class_info[match]['typed'] = True
        else:
            no_test_classes.append(match[1])

    return class_info, no_test_classes


def get_cc_class_type(class_info, classname):
    """Tell the type of the given class.

    Args:
        class_info: A dict of class info.
        classname: A string of class name.

    Returns:
        String of the gtest type to prompt. The output will be one of:
        1. 'regular test'             (GTEST_REGULAR)
        2. 'typed test'               (GTEST_TYPED)
        3. 'value-parameterized test' (GTEST_PARAM)
        4. 'typed-parameterized test' (GTEST_TYPED_PARAM)
    """
    if class_info.get(classname).get('prefixes'):
        if class_info.get(classname).get('typed'):
            return GTEST_TYPED_PARAM
        return GTEST_PARAM
    if class_info.get(classname).get('typed'):
        return GTEST_TYPED
    return GTEST_REGULAR


def get_cc_filter(class_info, class_name, methods):
    """Get the cc filter.

    Args:
        class_info: a dict of class info.
        class_name: class name of the cc test.
        methods: a list of method names.

    Returns:
        A formatted string for cc filter.
        For a Type/Typed-parameterized test, it will be:
          "class1/*.method1:class1/*.method2" or "class1/*.*"
        For a parameterized test, it will be:
          "*/class1.*" or "prefix/class1.*"
        For the rest the pattern will be:
          "class1.method1:class1.method2" or "class1.*"
    """
    #Strip prefix from class_name.
    _class_name = class_name
    if '/' in class_name:
        _class_name = str(class_name).split('/')[-1]
    type_str = get_cc_class_type(class_info, _class_name)
    logging.debug('%s is a "%s".', _class_name, type_str)
    # When found parameterized tests, recompose the class name
    # in */$(ClassName) if the prefix is not given.
    if type_str in (GTEST_TYPED_PARAM, GTEST_PARAM):
        if not '/' in class_name:
            class_name = '*/%s' % class_name
    if type_str in (GTEST_TYPED, GTEST_TYPED_PARAM):
        if methods:
            sorted_methods = sorted(list(methods))
            return ":".join(["%s/*.%s" % (class_name, x) for x in sorted_methods])
        return "%s/*.*" % class_name
    if methods:
        sorted_methods = sorted(list(methods))
        return ":".join(["%s.%s" % (class_name, x) for x in sorted_methods])
    return "%s.*" % class_name
