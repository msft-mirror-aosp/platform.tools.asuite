# Copyright 2018, The Android Open Source Project
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

"""Test Finder Handler module."""

# pylint: disable=import-outside-toplevel
# pylint: disable=protected-access

from enum import Enum, unique
import logging
import re
import sys

from atest import atest_configs
from atest import atest_utils, constants
from atest.atest_enum import ExitCode
from atest.crystalball import perf_mode
from atest.test_finders import cache_finder
from atest.test_finders import module_finder
from atest.test_finders import suite_plan_finder
from atest.test_finders import test_finder_base
from atest.test_finders import test_finder_utils
from atest.test_finders import tf_integration_finder

# List of default test finder classes.
_TEST_FINDERS = {
    suite_plan_finder.SuitePlanFinder,
    tf_integration_finder.TFIntegrationFinder,
    module_finder.ModuleFinder,
    cache_finder.CacheFinder,
}


@unique
class FinderMethod(Enum):
  """An enum object for test finders.

  Explanation of FinderMethod:
  0. MODULE: LOCAL_MODULE or LOCAL_PACKAGE_NAME value in Android.mk/Android.bp.
  1. MAINLINE_MODULE: module[mod1.apk+mod2.apex] pattern in TEST_MAPPING files.
  2. CLASS: Names which the same with a ClassName.java/kt file.
  3. QUALIFIED_CLASS: String like "a.b.c.ClassName".
  4. MODULE_CLASS: Combo of MODULE and CLASS as "module:class".
  5. PACKAGE: Package in java file. Same as file path to java file.
  6. MODULE_PACKAGE: Combo of MODULE and PACKAGE as "module:package".
  7. MODULE_FILE_PATH: File path to dir of tests or test itself.
  8. INTEGRATION_FILE_PATH: File path to config xml in one of the 4 integration
                            config directories.
  9. INTEGRATION: xml file name in one of the 4 integration config directories.
  10. SUITE: Value of the "run-suite-tag" in xml config file in 4 config dirs.
             Same as value of "test-suite-tag" in AndroidTest.xml files.
  11. CC_CLASS: Test case in cc file.
  12. SUITE_PLAN: Suite name such as cts.
  13. SUITE_PLAN_FILE_PATH: File path to config xml in the suite config
                            directories.
  14. CACHE: A pseudo type that runs cache_finder without finding test in real.
  15: CONFIG: Find tests by the given AndroidTest.xml file path.
  """

  MODULE = (
      'MODULE',
      module_finder.ModuleFinder.find_test_by_module_name,
      module_finder.ModuleFinder,
  )
  MAINLINE_MODULE = (
      'MAINLINE_MODULE',
      module_finder.MainlineModuleFinder.find_test_by_module_name,
      module_finder.ModuleFinder,
  )
  CLASS = (
      'CLASS',
      module_finder.ModuleFinder.find_test_by_class_name,
      module_finder.ModuleFinder,
  )
  MODULE_CLASS = (
      'MODULE_CLASS',
      module_finder.ModuleFinder.find_test_by_module_and_class,
      module_finder.ModuleFinder,
  )
  QUALIFIED_CLASS = (
      'QUALIFIED_CLASS',
      module_finder.ModuleFinder.find_test_by_class_name,
      module_finder.ModuleFinder,
  )
  PACKAGE = (
      'PACKAGE',
      module_finder.ModuleFinder.find_test_by_package_name,
      module_finder.ModuleFinder,
  )
  MODULE_PACKAGE = (
      'MODULE_PACKAGE',
      module_finder.ModuleFinder.find_test_by_module_and_package,
      module_finder.ModuleFinder,
  )
  MODULE_FILE_PATH = (
      'MODULE_FILE_PATH',
      module_finder.ModuleFinder.find_test_by_path,
      module_finder.ModuleFinder,
  )
  INTEGRATION_FILE_PATH = (
      'INTEGRATION_FILE_PATH',
      tf_integration_finder.TFIntegrationFinder.find_int_test_by_path,
      tf_integration_finder.TFIntegrationFinder,
  )
  INTEGRATION = (
      'INTEGRATION',
      tf_integration_finder.TFIntegrationFinder.find_test_by_integration_name,
      tf_integration_finder.TFIntegrationFinder,
  )
  CC_CLASS = (
      'CC_CLASS',
      module_finder.ModuleFinder.find_test_by_cc_class_name,
      module_finder.ModuleFinder,
  )
  SUITE_PLAN = (
      'SUITE_PLAN',
      suite_plan_finder.SuitePlanFinder.find_test_by_suite_name,
      suite_plan_finder.SuitePlanFinder,
  )
  SUITE_PLAN_FILE_PATH = (
      'SUITE_PLAN_FILE_PATH',
      suite_plan_finder.SuitePlanFinder.find_test_by_suite_path,
      suite_plan_finder.SuitePlanFinder,
  )
  CACHE = (
      'CACHE',
      cache_finder.CacheFinder.find_test_by_cache,
      cache_finder.CacheFinder,
  )
  CONFIG = (
      'CONFIG',
      module_finder.ModuleFinder.find_test_by_config_name,
      module_finder.ModuleFinder,
  )
  CONFIG_JUNIT_CLASSES = (
      'CONFIG',
      module_finder.ModuleFinder.find_test_by_config_junit_classes,
      module_finder.ModuleFinder,
  )

  def __init__(self, name, method, finder_class):
    self._name = name
    self._method = method
    self._finder_class = finder_class

  def get_name(self):
    """Return finder's name."""
    return self._name

  def get_method(self):
    """Return finder's method."""
    return self._method

  def get_finder_class(self):
    """Return finder's class."""
    return self._finder_class


_FILE_PATH_FINDERS = (
    FinderMethod.CACHE,
    FinderMethod.MODULE_FILE_PATH,
    FinderMethod.INTEGRATION_FILE_PATH,
    FinderMethod.SUITE_PLAN_FILE_PATH,
)


def _get_finder_instance_dict(module_info):
  """Return dict of finder instances.

  Args:
      module_info: ModuleInfo for finder classes to use.

  Returns:
      Dict of finder instances keyed by their name.
  """
  return {
      finder.NAME: finder(module_info=module_info)
      for finder in _get_test_finders()
  }


def _get_test_finders():
  """Returns the test finders.

  If external test types are defined outside atest, they can be try-except
  imported into here.

  Returns:
      Set of test finder classes.
  """
  test_finders = _TEST_FINDERS.copy()
  # Example import of external test finder:
  try:
    from test_finders import example_finder

    test_finders.add(example_finder.ExampleFinder)
  except ImportError:
    pass
  return test_finders


_REF_MATCH_WITH_TRAILING_DOT = re.compile(r'[\w.-]+\.$')


def _validate_ref(ref: str):
  # Filter out trailing dot but keeping `.` and `..` in ref.
  if '..' not in ref and _REF_MATCH_WITH_TRAILING_DOT.match(ref):
    atest_utils.colorful_print(
        f'Found trailing dot({ref}). Please correct it and try again.',
        constants.RED,
    )
    sys.exit(ExitCode.INPUT_TEST_REFERENCE_ERROR)


# pylint: disable=too-many-branches
# pylint: disable=too-many-return-statements
def _get_test_reference_types(ref):
  """Determine type of test reference based on the content of string.

  Examples:
      The string 'SequentialRWTest' could be a reference to
      a Module or a Class name.

      The string 'cts/tests/filesystem' could be a Path, Integration
      or Suite reference.

  Args:
      ref: A string referencing a test.

  Returns:
      A list of possible REFERENCE_TYPEs (ints) for reference string.
  """
  _validate_ref(ref)
  if ref.startswith('.') or '..' in ref or ref.startswith('/'):
    return list(_FILE_PATH_FINDERS)
  if '/' in ref:
    if ':' in ref:
      return [
          FinderMethod.CACHE,
          FinderMethod.MODULE_FILE_PATH,
          FinderMethod.INTEGRATION_FILE_PATH,
          FinderMethod.INTEGRATION,
          FinderMethod.SUITE_PLAN_FILE_PATH,
          FinderMethod.MODULE_CLASS,
      ]
    return [
        FinderMethod.CACHE,
        FinderMethod.MODULE_FILE_PATH,
        FinderMethod.INTEGRATION_FILE_PATH,
        FinderMethod.INTEGRATION,
        FinderMethod.SUITE_PLAN_FILE_PATH,
        FinderMethod.CC_CLASS,
        # TODO: Uncomment in SUITE when it's supported
        # FinderMethod.SUITE
    ]
  if atest_utils.get_test_and_mainline_modules(ref):
    return [FinderMethod.CACHE, FinderMethod.MAINLINE_MODULE]

  has_dot = '.' in ref
  if has_dot:
    ref_end = ref.rsplit('.', 1)[-1]
    ref_end_is_upper = ref_end[0].isupper()
  # parse_test_reference() will return none empty dictionary if input test
  # reference match $module:$package_class.
  if test_finder_utils.parse_test_reference(ref):
    if has_dot:
      if ref_end_is_upper:
        # Possible types:
        # Module:fully.qualified.Class
        # Module:filly.qualifiled.(P|p)ackage (b/289515000)
        # Integration:fully.q.Class
        return [
            FinderMethod.CACHE,
            FinderMethod.MODULE_CLASS,
            FinderMethod.MODULE_PACKAGE,
            FinderMethod.INTEGRATION,
        ]
      # Module:some.package
      return [
          FinderMethod.CACHE,
          FinderMethod.MODULE_PACKAGE,
          FinderMethod.MODULE_CLASS,
      ]
    # Module:Class or IntegrationName:Class
    return [
        FinderMethod.CACHE,
        FinderMethod.MODULE_CLASS,
        FinderMethod.INTEGRATION,
    ]
  if has_dot:
    # The string of ref_end possibly includes specific mathods, e.g.
    # foo.java#method, so let ref_end be the first part of splitting '#'.
    ref_end = ref_end.split('#', 1)[0]
    if ref_end in ('java', 'kt', 'bp', 'mk', 'cc', 'cpp'):
      return [
          FinderMethod.CACHE,
          FinderMethod.MODULE,
          FinderMethod.MODULE_FILE_PATH,
      ]
    if ref_end == 'xml':
      return [
          FinderMethod.CACHE,
          FinderMethod.INTEGRATION_FILE_PATH,
          FinderMethod.SUITE_PLAN_FILE_PATH,
      ]
    # (b/207327349) ref_end_is_upper does not guarantee a classname anymore.
    return [
        FinderMethod.CACHE,
        FinderMethod.MODULE,
        FinderMethod.QUALIFIED_CLASS,
        FinderMethod.PACKAGE,
    ]

  if perf_mode.is_perf_test(args=atest_configs.GLOBAL_ARGS):
    return [
        FinderMethod.CACHE,
        FinderMethod.MODULE,
        FinderMethod.INTEGRATION,
        FinderMethod.CONFIG,
        FinderMethod.CONFIG_JUNIT_CLASSES,
        FinderMethod.SUITE_PLAN,
        FinderMethod.CLASS,
        FinderMethod.CC_CLASS,
    ]

  # Note: We assume that if you're referencing a file in your cwd,
  # that file must have a '.' in its name, i.e. foo.java, foo.xml.
  # If this ever becomes not the case, then we need to include path below.
  return [
      FinderMethod.CACHE,
      FinderMethod.MODULE,
      FinderMethod.INTEGRATION,
      # TODO: Uncomment in SUITE when it's supported
      # FinderMethod.SUITE,
      FinderMethod.CONFIG,
      FinderMethod.SUITE_PLAN,
      FinderMethod.CLASS,
      FinderMethod.CC_CLASS,
  ]


def _get_registered_find_methods(module_info):
  """Return list of registered find methods.

  This is used to return find methods that were not listed in the
  default find methods but just registered in the finder classes. These
  find methods will run before the default find methods.

  Args:
      module_info: ModuleInfo for finder classes to instantiate with.

  Returns:
      List of registered find methods.
  """
  find_methods = []
  finder_instance_dict = _get_finder_instance_dict(module_info)
  for finder in _get_test_finders():
    finder_instance = finder_instance_dict[finder.NAME]
    for find_method_info in finder_instance.get_all_find_methods():
      find_methods.append(
          test_finder_base.Finder(
              finder_instance, find_method_info.find_method, finder.NAME
          )
      )
  return find_methods


def _get_default_find_methods(module_info, test):
  """Default find methods to be used based on the given test name.

  Args:
      module_info: ModuleInfo for finder instances to use.
      test: String of test name to help determine which find methods to utilize.

  Returns:
      List of find methods to use.
  """
  finder_instance_dict = _get_finder_instance_dict(module_info)
  test_ref_types = _get_test_reference_types(test)
  logging.debug(
      'Resolved input to possible references: %s',
      ', '.join(t.get_name() for t in test_ref_types),
  )
  return [
      test_finder_base.Finder(
          finder_instance_dict[test_ref_type.get_finder_class().NAME],
          test_ref_type.get_method(),
          test_ref_type.get_name(),
      )
      for test_ref_type in test_ref_types
  ]


def get_find_methods_for_test(module_info, test):
  """Return a list of ordered find methods.

  Args:
    test: String of test name to get find methods for.

  Returns:
      List of ordered find methods.
  """
  registered_find_methods = _get_registered_find_methods(module_info)
  default_find_methods = _get_default_find_methods(module_info, test)
  return registered_find_methods + default_find_methods
