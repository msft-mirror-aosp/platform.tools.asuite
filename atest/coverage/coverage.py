# Copyright 2022, The Android Open Source Project
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
"""Code coverage instrumentation and collection functionality."""

import logging
import os
from pathlib import Path
import subprocess
from typing import List, Set

from atest import atest_utils
from atest import constants
from atest import module_info
from atest.test_finders import test_info


def build_env_vars():
  """Environment variables for building with code coverage instrumentation.

  Returns:
      A dict with the environment variables to set.
  """
  env_vars = {
      'CLANG_COVERAGE': 'true',
      'NATIVE_COVERAGE_PATHS': '*',
      'EMMA_INSTRUMENT': 'true',
      'EMMA_INSTRUMENT_FRAMEWORK': 'true',
      'LLVM_PROFILE_FILE': '/dev/null',
  }
  return env_vars


def tf_args(mod_info):
  """TradeFed command line arguments needed to collect code coverage.

  Returns:
      A list of the command line arguments to append.
  """
  build_top = Path(os.environ.get(constants.ANDROID_BUILD_TOP))
  clang_version = _get_clang_version(build_top)
  llvm_profdata = build_top.joinpath(
      f'prebuilts/clang/host/linux-x86/{clang_version}'
  )
  jacocoagent_paths = mod_info.get_installed_paths('jacocoagent')
  return (
      '--coverage',
      '--coverage-toolchain',
      'JACOCO',
      '--coverage-toolchain',
      'CLANG',
      '--auto-collect',
      'JAVA_COVERAGE',
      '--auto-collect',
      'CLANG_COVERAGE',
      '--llvm-profdata-path',
      str(llvm_profdata),
      '--jacocoagent-path',
      str(jacocoagent_paths[0]),
  )


def _get_clang_version(build_top):
  """Finds out current toolchain version."""
  version_output = subprocess.check_output(
      f'{build_top}/build/soong/scripts/get_clang_version.py', text=True
  )
  return version_output.strip()


def build_modules():
  """Build modules needed for coverage report generation."""
  return ('jacoco_to_lcov_converter', 'jacocoagent')


def generate_coverage_report(
    results_dir: str,
    test_infos: List[test_info.TestInfo],
    mod_info: module_info.ModuleInfo,
    is_host_enabled: bool,
    code_under_test: Set[str],
):
  """Generates HTML code coverage reports based on the test info.

  Args:
    results_dir: The directory containing the test results
    test_infos: The TestInfo objects for this invocation
    mod_info: The ModuleInfo object containing all build module information
    is_host_enabled: True if --host was specified
    code_under_test: The set of modules to include in the coverage report
  """
  if not code_under_test:
    # No code-under-test was specified on the command line. Deduce the values
    # from module-info or from the test.
    code_under_test = _deduce_code_under_test(test_infos, mod_info)

  logging.debug(f'Code-under-test: {code_under_test}')

  # Collect coverage metadata files from the build for coverage report generation.
  jacoco_report_jars = _collect_java_report_jars(
      code_under_test, mod_info, is_host_enabled
  )
  unstripped_native_binaries = _collect_native_report_binaries(
      code_under_test, mod_info, is_host_enabled
  )

  if jacoco_report_jars:
    _generate_java_coverage_report(
        jacoco_report_jars,
        _get_all_src_paths(code_under_test, mod_info),
        results_dir,
        mod_info,
    )

  if unstripped_native_binaries:
    _generate_native_coverage_report(unstripped_native_binaries, results_dir)


def _deduce_code_under_test(
    test_infos: List[test_info.TestInfo],
    mod_info: module_info.ModuleInfo,
) -> Set[str]:
  """Deduces the code-under-test from the test info and module info.
  If the test info contains code-under-test information, that is used.
  Otherwise, the dependencies of the test are used.

  Args:
    test_infos: The TestInfo objects for this invocation
    mod_info: The ModuleInfo object containing all build module information

  Returns:
    The set of modules to include in the coverage report
  """
  code_under_test = set()

  for test_info in test_infos:
    code_under_test.update(
        mod_info.get_code_under_test(test_info.raw_test_name)
    )

  if code_under_test:
    return code_under_test

  # No code-under-test was specified in ModuleInfo, default to using dependency
  # information of the test.
  for test_info in test_infos:
    code_under_test.update(_get_test_deps(test_info, mod_info))

  return code_under_test


def _get_test_deps(test_info, mod_info):
  """Gets all dependencies of the TestInfo, including Mainline modules."""
  deps = set()

  deps.add(test_info.raw_test_name)
  deps |= _get_transitive_module_deps(
      mod_info.get_module_info(test_info.raw_test_name), mod_info, deps
  )

  # Include dependencies of any Mainline modules specified as well.
  for mainline_module in test_info.mainline_modules:
    deps.add(mainline_module)
    deps |= _get_transitive_module_deps(
        mod_info.get_module_info(mainline_module), mod_info, deps
    )

  return deps


def _get_transitive_module_deps(
    info, mod_info: module_info.ModuleInfo, seen: Set[str]
) -> Set[str]:
  """Gets all dependencies of the module, including .impl versions."""
  deps = set()

  for dep in info.get(constants.MODULE_DEPENDENCIES, []):
    if dep in seen:
      continue

    seen.add(dep)

    dep_info = mod_info.get_module_info(dep)

    # Mainline modules sometimes depend on `java_sdk_library` modules that
    # generate synthetic build modules ending in `.impl` which do not appear
    # in the ModuleInfo. Strip this suffix to prevent incomplete dependency
    # information when generating coverage reports.
    # TODO(olivernguyen): Reconcile this with
    # ModuleInfo.get_module_dependency(...).
    if not dep_info:
      dep = dep.removesuffix('.impl')
      dep_info = mod_info.get_module_info(dep)

    if not dep_info:
      continue

    deps.add(dep)
    deps |= _get_transitive_module_deps(dep_info, mod_info, seen)

  return deps


def _collect_java_report_jars(code_under_test, mod_info, is_host_enabled):
  soong_intermediates = atest_utils.get_build_out_dir('soong/.intermediates')
  report_jars = {}

  for module in code_under_test:
    for path in mod_info.get_paths(module):
      if not path:
        continue
      module_dir = soong_intermediates.joinpath(path, module)
      # Check for uninstrumented Java class files to report coverage.
      classfiles = list(module_dir.rglob('jacoco-report-classes/*.jar'))
      if classfiles:
        report_jars[module] = classfiles

    # Host tests use the test itself to generate the coverage report.
    info = mod_info.get_module_info(module)
    if not info:
      continue
    if is_host_enabled or not mod_info.requires_device(info):
      installed = mod_info.get_installed_paths(module)
      installed_jars = [str(f) for f in installed if f.suffix == '.jar']
      if installed_jars:
        report_jars[module] = installed_jars

  return report_jars


def _collect_native_report_binaries(code_under_test, mod_info, is_host_enabled):
  soong_intermediates = atest_utils.get_build_out_dir('soong/.intermediates')
  report_binaries = set()

  for module in code_under_test:
    for path in mod_info.get_paths(module):
      if not path:
        continue
      module_dir = soong_intermediates.joinpath(path, module)
      # Check for unstripped binaries to report coverage.
      report_binaries.update(_find_native_binaries(module_dir))

    # Host tests use the test itself to generate the coverage report.
    info = mod_info.get_module_info(module)
    if not info:
      continue
    if constants.MODULE_CLASS_NATIVE_TESTS not in info.get(
        constants.MODULE_CLASS, []
    ):
      continue
    if is_host_enabled or not mod_info.requires_device(info):
      report_binaries.update(
          str(f) for f in mod_info.get_installed_paths(module)
      )

  return report_binaries


def _find_native_binaries(module_dir):
  files = module_dir.glob('*cov*/**/unstripped/*')

  # Exclude .rsp files. These are files containing the command line used to
  # generate the unstripped binaries, but are stored in the same directory as
  # the actual output binary.
  # Exclude .d and .d.raw files. These are Rust dependency files and are also
  # stored in the unstripped directory.
  return [
      str(file)
      for file in files
      if '.rsp' not in file.suffixes and '.d' not in file.suffixes
  ]


def _get_all_src_paths(modules, mod_info):
  """Gets the set of directories containing any source files from the modules."""
  src_paths = set()

  for module in modules:
    info = mod_info.get_module_info(module)
    if not info:
      continue

    # Do not report coverage for test modules.
    if mod_info.is_testable_module(info):
      continue

    src_paths.update(
        os.path.dirname(f) for f in info.get(constants.MODULE_SRCS, [])
    )

  src_paths = {p for p in src_paths if not _is_generated_code(p)}
  return src_paths


def _is_generated_code(path):
  return 'soong/.intermediates' in path


def _generate_java_coverage_report(
    report_jars, src_paths, results_dir, mod_info
):
  build_top = os.environ.get(constants.ANDROID_BUILD_TOP)
  out_dir = os.path.join(results_dir, 'java_coverage')
  jacoco_files = atest_utils.find_files(results_dir, '*.ec')

  os.mkdir(out_dir)
  jacoco_lcov = mod_info.get_module_info('jacoco_to_lcov_converter')
  jacoco_lcov = os.path.join(build_top, jacoco_lcov['installed'][0])
  lcov_reports = []

  for name, classfiles in report_jars.items():
    dest = f'{out_dir}/{name}.info'
    cmd = [jacoco_lcov, '-o', dest]
    for classfile in classfiles:
      cmd.append('-classfiles')
      cmd.append(str(classfile))
    for src_path in src_paths:
      cmd.append('-sourcepath')
      cmd.append(src_path)
    cmd.extend(jacoco_files)
    try:
      subprocess.run(
          cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
      )
    except subprocess.CalledProcessError as err:
      atest_utils.colorful_print(
          f'Failed to generate coverage for {name}:', constants.RED
      )
      logging.exception(err.stdout)
    atest_utils.colorful_print(
        f'Coverage for {name} written to {dest}.', constants.GREEN
    )
    lcov_reports.append(dest)

  _generate_lcov_report(out_dir, lcov_reports, build_top)


def _generate_native_coverage_report(unstripped_native_binaries, results_dir):
  build_top = os.environ.get(constants.ANDROID_BUILD_TOP)
  out_dir = os.path.join(results_dir, 'native_coverage')
  profdata_files = atest_utils.find_files(results_dir, '*.profdata')

  os.mkdir(out_dir)
  cmd = [
      'llvm-cov',
      'show',
      '-format=html',
      f'-output-dir={out_dir}',
      f'-path-equivalence=/proc/self/cwd,{build_top}',
  ]
  for profdata in profdata_files:
    cmd.append('--instr-profile')
    cmd.append(profdata)
  for binary in unstripped_native_binaries:
    cmd.append(f'--object={str(binary)}')

  try:
    subprocess.run(
        cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    atest_utils.colorful_print(
        f'Native coverage written to {out_dir}.', constants.GREEN
    )
  except subprocess.CalledProcessError as err:
    atest_utils.colorful_print(
        'Failed to generate native code coverage.', constants.RED
    )
    logging.exception(err.stdout)


def _generate_lcov_report(out_dir, reports, root_dir=None):
  cmd = ['genhtml', '-q', '-o', out_dir, '--ignore-errors', 'unmapped,range']
  if root_dir:
    cmd.extend(['-p', root_dir])
  cmd.extend(reports)
  try:
    subprocess.run(
        cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    atest_utils.colorful_print(
        f'Code coverage report written to {out_dir}.', constants.GREEN
    )
    atest_utils.colorful_print(
        f'To open, Ctrl+Click on file://{out_dir}/index.html', constants.GREEN
    )
  except subprocess.CalledProcessError as err:
    atest_utils.colorful_print(
        'Failed to generate HTML coverage report.', constants.RED
    )
    logging.exception(err.stdout)
  except FileNotFoundError:
    atest_utils.colorful_print('genhtml is not on the $PATH.', constants.RED)
    atest_utils.colorful_print(
        'Run `sudo apt-get install lcov -y` to install this tool.',
        constants.RED,
    )
