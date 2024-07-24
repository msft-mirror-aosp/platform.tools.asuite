#!/usr/bin/env python3
#
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

"""Unit tests for coverage."""

# pylint: disable=invalid-name

from pathlib import PosixPath
import unittest
from unittest import mock
from atest import atest_utils
from atest import constants
from atest import module_info
from atest.coverage import coverage
from atest.test_finders import test_info


class DeduceCodeUnderTestUnittests(unittest.TestCase):
  """Tests for _deduce_code_under_test."""

  def test_code_under_test_is_defined_return_modules_in_code_under_test(self):
    mod_info = create_module_info([
        module(
            name='test1',
            dependencies=['dep1', 'dep2'],
            code_under_test=['dep1'],
        ),
        module(name='dep1', dependencies=['dep1dep1', 'dep1dep2']),
        module(name='dep1dep1'),
        module(name='dep1dep2', dependencies=['dep1dep2dep']),
        module(name='dep1dep2dep'),
        module(name='dep2'),
    ])

    self.assertEqual(
        coverage._deduce_code_under_test([create_test_info('test1')], mod_info),
        {'dep1'},
    )

  def test_code_under_test_not_defined_return_all_modules_from_one_test(self):
    mod_info = create_module_info([
        module(name='test1', dependencies=['dep1', 'dep2']),
        module(name='dep1', dependencies=['dep1dep1', 'dep1dep2']),
        module(name='dep1dep1'),
        module(name='dep1dep2', dependencies=['dep1dep2dep']),
        module(name='dep1dep2dep'),
        module(name='dep2'),
        module(name='shouldnotappear'),
    ])

    self.assertEqual(
        coverage._deduce_code_under_test([create_test_info('test1')], mod_info),
        {
            'test1',
            'dep1',
            'dep2',
            'dep1dep1',
            'dep1dep2',
            'dep1dep2dep',
        },
    )

  def test_code_under_test_not_defined_return_all_modules_from_all_tests(self):
    mod_info = create_module_info([
        module(name='test1', dependencies=['testlib', 'test1dep']),
        module(name='test2', dependencies=['testlib', 'test2dep']),
        module(name='testlib', dependencies=['testlibdep']),
        module(name='testlibdep'),
        module(name='test1dep'),
        module(name='test2dep'),
        module(name='shouldnotappear'),
    ])

    self.assertEqual(
        coverage._deduce_code_under_test(
            [create_test_info('test1'), create_test_info('test2')], mod_info
        ),
        {'test1', 'test2', 'testlib', 'testlibdep', 'test1dep', 'test2dep'},
    )


class CollectJavaReportJarsUnittests(unittest.TestCase):
  """Test cases for _collect_java_report_jars."""

  @mock.patch.object(
      atest_utils,
      'get_build_out_dir',
      return_value=PosixPath('/out/soong/.intermediates'),
  )
  @mock.patch.object(
      PosixPath,
      'rglob',
      return_value=[
          '/out/soong/.intermediates/path/to/java_lib/variant-name/jacoco-report-classes/java_lib.jar'
      ],
  )
  def test_java_lib(self, _rglob, _get_build_out_dir):
    code_under_test = {'java_lib'}
    mod_info = create_module_info([
        module(name='java_lib', path='path/to'),
    ])

    self.assertEqual(
        coverage._collect_java_report_jars(code_under_test, mod_info, False),
        {
            'java_lib': [
                '/out/soong/.intermediates/path/to/java_lib/variant-name/jacoco-report-classes/java_lib.jar'
            ]
        },
    )

  def test_host_test_includes_installed(self):
    code_under_test = {'java_host_test'}
    mod_info = create_module_info([
        module(
            name='java_host_test',
            installed=[
                '/path/to/out/host/java_host_test.jar',
                '/path/to/out/host/java_host_test.config',
            ],
        ),
    ])

    self.assertEqual(
        coverage._collect_java_report_jars(code_under_test, mod_info, True),
        {'java_host_test': ['/path/to/out/host/java_host_test.jar']},
    )


class CollectNativeReportBinariesUnittests(unittest.TestCase):
  """Test cases for _collect_native_report_binaries."""

  @mock.patch.object(
      atest_utils,
      'get_build_out_dir',
      return_value=PosixPath('/out/soong/.intermediates'),
  )
  @mock.patch.object(PosixPath, 'glob')
  def test_native_binary(self, _glob, _get_build_out_dir):
    _glob.return_value = [
        PosixPath(
            '/out/soong/.intermediates/path/to/native_bin/variant-name-cov/unstripped/native_bin'
        )
    ]
    code_under_test = {'native_bin'}
    mod_info = create_module_info([
        module(name='native_bin', path='path/to'),
    ])

    self.assertEqual(
        coverage._collect_native_report_binaries(
            code_under_test, mod_info, False
        ),
        {
            '/out/soong/.intermediates/path/to/native_bin/variant-name-cov/unstripped/native_bin'
        },
    )

  @mock.patch.object(
      atest_utils,
      'get_build_out_dir',
      return_value=PosixPath('/out/soong/.intermediates'),
  )
  @mock.patch.object(PosixPath, 'glob')
  def test_skip_rsp_and_d_files(self, _glob, _get_build_out_dir):
    _glob.return_value = [
        PosixPath(
            '/out/soong/.intermediates/path/to/native_bin/variant-name-cov/unstripped/native_bin'
        ),
        PosixPath(
            '/out/soong/.intermediates/path/to/native_bin/variant-name-cov/unstripped/native_bin.rsp'
        ),
        PosixPath(
            '/out/soong/.intermediates/path/to/native_bin/variant-name-cov/unstripped/native_bin.d'
        ),
    ]
    code_under_test = {'native_bin'}
    mod_info = create_module_info([
        module(name='native_bin', path='path/to'),
    ])

    self.assertEqual(
        coverage._collect_native_report_binaries(
            code_under_test, mod_info, False
        ),
        {
            '/out/soong/.intermediates/path/to/native_bin/variant-name-cov/unstripped/native_bin'
        },
    )

  def test_host_test_includes_installed(self):
    code_under_test = {'native_host_test'}
    mod_info = create_module_info([
        module(
            name='native_host_test',
            installed=['/out/host/nativetests/native_host_test'],
            classes=[constants.MODULE_CLASS_NATIVE_TESTS],
        ),
    ])

    self.assertEqual(
        coverage._collect_native_report_binaries(
            code_under_test, mod_info, True
        ),
        {'/out/host/nativetests/native_host_test'},
    )


class GenerateCoverageReportUnittests(unittest.TestCase):
  """Tests for the code-under-test feature."""

  @mock.patch.object(coverage, '_collect_java_report_jars', return_value={})
  @mock.patch.object(
      coverage, '_collect_native_report_binaries', return_value=set()
  )
  def test_generate_report_for_code_under_test_passed_in_from_atest(
      self, _collect_native, _collect_java
  ):
    test_infos = [create_test_info('test')]
    mod_info = create_module_info([
        module(name='test', dependencies=['lib1', 'lib2']),
        module(name='lib1'),
        module(name='lib2', dependencies=['lib2dep']),
        module(name='lib2dep'),
    ])
    code_under_test = ['lib1', 'lib2']

    coverage.generate_coverage_report(
        '/tmp/results_dir', test_infos, mod_info, True, code_under_test
    )

    _collect_java.assert_called_with(code_under_test, mod_info, True)
    _collect_native.assert_called_with(code_under_test, mod_info, True)

  @mock.patch.object(coverage, '_collect_java_report_jars', return_value={})
  @mock.patch.object(
      coverage, '_collect_native_report_binaries', return_value=set()
  )
  def test_generate_report_for_modules_get_from_deduce_code_under_test(
      self, _collect_native, _collect_java
  ):
    test_infos = [create_test_info('test')]
    mod_info = create_module_info([
        module(name='test', dependencies=['lib1', 'lib2']),
        module(name='lib1'),
        module(name='lib2', dependencies=['lib2dep']),
        module(name='lib2dep'),
        module(name='not_a_dep'),
    ])

    coverage.generate_coverage_report(
        '/tmp/results_dir', test_infos, mod_info, False, []
    )

    expected_code_under_test = {'test', 'lib1', 'lib2', 'lib2dep'}
    _collect_java.assert_called_with(expected_code_under_test, mod_info, False)
    _collect_native.assert_called_with(
        expected_code_under_test, mod_info, False
    )


def create_module_info(modules=None):
  """Wrapper function for creating module_info.ModuleInfo."""
  name_to_module_info = {}
  modules = modules or []

  for m in modules:
    name_to_module_info[m['module_name']] = m

  return module_info.load_from_dict(name_to_module_info)


# pylint: disable=too-many-arguments
def module(
    name=None,
    path=None,
    installed=None,
    classes=None,
    auto_test_config=None,
    test_config=None,
    shared_libs=None,
    dependencies=None,
    runtime_dependencies=None,
    data=None,
    data_dependencies=None,
    compatibility_suites=None,
    host_dependencies=None,
    srcs=None,
    supported_variants=None,
    code_under_test=None,
):
  name = name or 'libhello'

  m = {}

  m['module_name'] = name
  m['class'] = classes or []
  m['path'] = [path or '']
  m['installed'] = installed or []
  m['is_unit_test'] = 'false'
  m['auto_test_config'] = auto_test_config or []
  m['test_config'] = test_config or []
  m['shared_libs'] = shared_libs or []
  m['runtime_dependencies'] = runtime_dependencies or []
  m['dependencies'] = dependencies or []
  m['data'] = data or []
  m['data_dependencies'] = data_dependencies or []
  m['compatibility_suites'] = compatibility_suites or []
  m['host_dependencies'] = host_dependencies or []
  m['srcs'] = srcs or []
  m['supported_variants'] = supported_variants or []
  m['code_under_test'] = code_under_test or []
  return m


def create_test_info(name='HelloWorldTest'):
  """Helper function for creating test_info.TestInfo."""
  return test_info.TestInfo(name, 'AtestTradefedRunner', set())


if __name__ == '__main__':
  unittest.main()
