# Copyright 2024, The Android Open Source Project
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

"""Class that facilitates testing with ModuleInfo objects.

Contains methods to create module objects representing various types
of tests that can be run in Atest, as well as the corresponding ModuleInfo
object, for use in unit tests.
"""

import pathlib
import tempfile

from atest import constants
from atest import module_info
from atest.test_finders import test_info
from atest.test_finders.test_info import TestInfo
from atest.test_runners import atest_tf_test_runner
from pyfakefs import fake_filesystem_unittest


class ModuleInfoTest(fake_filesystem_unittest.TestCase):
  """Fixture for tests that require interacting with module-info."""

  def setUp(self):
    self.setUpPyfakefs()
    self.product_out_path = pathlib.Path('/src/out/product')
    self.product_out_path.mkdir(parents=True)

  def create_empty_module_info(self):
    """Creates an empty ModuleInfo object."""
    fake_temp_file = self.product_out_path.joinpath(
        next(tempfile._get_candidate_names())
    )
    self.fs.create_file(fake_temp_file, contents='{}')
    return module_info.load_from_file(module_file=fake_temp_file)

  def create_module_info(self, modules: list[dict] = None):
    """Creates a ModuleInfo object from the given list of modules."""
    mod_info = self.create_empty_module_info()
    modules = modules or []

    for m in modules:
      mod_info.name_to_module_info[m[constants.MODULE_INFO_ID]] = m

    return mod_info

  def assertContainsSubset(self, expected_subset, actual_set):
    """Checks whether actual iterable is a superset of expected iterable."""
    missing = set(expected_subset) - set(actual_set)
    if not missing:
      return

    self.fail(
        f'Missing elements {missing}\n'
        f'Expected: {expected_subset}\n'
        f'Actual: {actual_set}'
    )


def host_jar_module(name, installed):

  return module(
      name=name,
      supported_variants=['HOST'],
      installed=installed,
      auto_test_config=[],
      compatibility_suites=[],
  )


def device_driven_test_module(
    name,
    installed=None,
    compatibility_suites=None,
    host_deps=None,
    class_type=None,
    is_unit_test=None,
):

  name = name or 'hello_world_test'
  module_path = 'example_module/project'

  return test_module(
      name=name,
      supported_variants=['DEVICE'],
      compatibility_suites=compatibility_suites,
      installed=installed or [f'out/product/vsoc_x86/{name}/{name}.apk'],
      host_deps=host_deps,
      class_type=class_type or ['APP'],
      module_path=module_path,
      is_unit_test=is_unit_test,
  )


def device_driven_multi_config_test_module(
    name,
    installed=None,
    compatibility_suites=None,
    host_deps=None,
    class_type=None,
):

  module_path = 'example_module/project'
  return test_module(
      name=name,
      supported_variants=['DEVICE'],
      compatibility_suites=compatibility_suites,
      installed=installed or [f'out/product/vsoc_x86/{name}/{name}.apk'],
      auto_test_config=[False],
      test_configs=[
          f'{module_path}/configs/Config1.xml',
          f'{module_path}/configs/Config2.xml',
      ],
      host_deps=host_deps,
      class_type=class_type or ['APP'],
      module_path=module_path,
  )


def robolectric_test_module(name):
  name = name or 'hello_world_test'
  return test_module(
      name=name,
      supported_variants=['DEVICE'],
      installed=[f'out/host/linux-x86/{name}/{name}.jar'],
      compatibility_suites=['robolectric-tests'],
  )


def host_driven_device_test_module(name, libs=None):
  name = name or 'hello_world_test'
  return test_module(
      name=name,
      supported_variants=['HOST'],
      installed=[f'out/host/linux-x86/{name}/{name}.jar'],
      compatibility_suites=['null-suite'],
      libs=libs,
  )


def multi_variant_unit_test_module(name):

  name = name or 'hello_world_test'

  return test_module(
      name=name,
      supported_variants=['HOST', 'DEVICE'],
      installed=[
          f'out/host/linux-x86/{name}/{name}.cc',
          f'out/product/vsoc_x86/{name}/{name}.cc',
      ],
      compatibility_suites=['host-unit-tests'],
      is_unit_test='true',
  )


def test_module(
    name,
    supported_variants,
    installed,
    auto_test_config=[True],
    test_configs=[None],
    compatibility_suites=None,
    libs=None,
    host_deps=None,
    class_type=None,
    module_path=None,
    is_unit_test=None,
):
  """Creates a module object which with properties specific to a test module."""
  return module(
      name=name,
      supported_variants=supported_variants,
      installed=installed,
      auto_test_config=auto_test_config,
      test_configs=test_configs,
      compatibility_suites=compatibility_suites or ['null-suite'],
      libs=libs,
      host_deps=host_deps,
      class_type=class_type,
      module_path=[module_path],
      is_unit_test=is_unit_test,
  )


def module(
    name,
    supported_variants,
    installed,
    auto_test_config=None,
    test_configs=None,
    compatibility_suites=None,
    libs=None,
    host_deps=None,
    class_type=None,
    module_path=None,
    is_unit_test=None,
):
  """Creates a ModuleInfo object.

  This substitutes its creation from a module-info file for test purposes.
  """

  m = {}

  m[constants.MODULE_INFO_ID] = name
  m[constants.MODULE_NAME] = name
  m[constants.MODULE_SUPPORTED_VARIANTS] = supported_variants
  m[constants.MODULE_INSTALLED] = installed
  m[constants.MODULE_AUTO_TEST_CONFIG] = auto_test_config or []
  m[constants.MODULE_TEST_CONFIG] = test_configs or []
  m[constants.MODULE_COMPATIBILITY_SUITES] = compatibility_suites or []
  m[constants.MODULE_LIBS] = libs or []
  m[constants.MODULE_HOST_DEPS] = host_deps or []
  m[constants.MODULE_CLASS] = class_type or []
  m[constants.MODULE_PATH] = module_path or []
  m[constants.MODULE_IS_UNIT_TEST] = is_unit_test or 'false'

  return m
