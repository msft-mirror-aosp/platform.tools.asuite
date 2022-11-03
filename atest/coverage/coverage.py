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

import os
import re
import subprocess

from pathlib import Path

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
    }
    return env_vars


def tf_args(*value):
    """TradeFed command line arguments needed to collect code coverage.

    Returns:
        A list of the command line arguments to append.
    """
    return ('--coverage',
            '--coverage-toolchain', 'JACOCO',
            '--coverage-toolchain', 'CLANG',
            '--auto-collect', 'JAVA_COVERAGE',
            '--auto-collect', 'CLANG_COVERAGE',
            '--llvm-profdata-path', 'llvm-profdata')


def generate_coverage_report(results_dir: str,
                             test_infos: list[test_info.TestInfo],
                             mod_info: module_info.ModuleInfo):
    """Generates HTML code coverage reports based on the test info."""

    soong_intermediates = os.path.join(atest_utils.get_build_out_dir(),
                                       'soong/.intermediates')

    # Collect dependency and source file information for the tests and any
    # Mainline modules.
    dep_modules = _get_test_deps(test_infos, mod_info)
    src_paths = _get_all_src_paths(dep_modules, mod_info)

    # Collect JaCoCo class jars from the build for coverage report generation.
    jacoco_report_jars = {}
    for module in dep_modules:
        # Check if this has uninstrumented Java class files to report coverage.
        for path in mod_info.get_paths(module):
            report_jar = Path(
                os.path.join(
                    soong_intermediates, path, module,
                    f'android_common_cov/jacoco-report-classes/{module}.jar'))
            if os.path.exists(report_jar):
                jacoco_report_jars[module] = report_jar

    if jacoco_report_jars:
        _generate_java_coverage_report(jacoco_report_jars, src_paths,
                                       results_dir, mod_info)


def _get_test_deps(test_infos, mod_info):
    """Gets all dependencies of the TestInfo, including Mainline modules."""
    deps = set()

    for test_info in test_infos:
        # TestInfo.test_name may contain the Mainline modules in brackets, so
        # strip them out.
        deps.add(test_info.raw_test_name)
        deps |= mod_info.get_module_dependency(test_info.raw_test_name, deps)

        # Include dependencies of any Mainline modules specified as well.
        if not test_info.mainline_modules:
            continue

        for mainline_module in test_info.mainline_modules:
            deps.add(mainline_module)
            deps |= mod_info.get_module_dependency(mainline_module, deps)

    return deps


def _get_all_src_paths(modules, mod_info):
    """Gets the set of directories containing any source files from the modules.
    """
    src_paths = set()

    for module in modules:
        info = mod_info.get_module_info(module)
        if not info:
            continue
        src_paths.update(
            os.path.dirname(f) for f in info.get(constants.MODULE_SRCS, []))

    return src_paths


def _generate_java_coverage_report(report_jars, src_paths, results_dir,
                                   mod_info):
    build_top = os.environ.get(constants.ANDROID_BUILD_TOP)
    out_dir = os.path.join(results_dir, 'java_coverage')
    jacoco_files = atest_utils.find_files(results_dir, '*.ec')

    os.mkdir(out_dir)
    jacoco_lcov = mod_info.get_module_info('jacoco_to_lcov_converter')
    jacoco_lcov = os.path.join(build_top, jacoco_lcov['installed'][0])
    lcov_reports = []

    for name, report_jar in report_jars.items():
        dest = f'{out_dir}/{name}.info'
        cmd = [jacoco_lcov, '-o', dest, '-classfiles', str(report_jar)]
        for src_path in src_paths:
            cmd.append('-sourcepath')
            cmd.append(src_path)
        cmd.extend(jacoco_files)
        result = subprocess.check_call(cmd, stderr=subprocess.STDOUT)
        logging.debug(result.stdout)
        atest_utils.colorful_print(f'Coverage for {name} written to {dest}.',
                                   constants.GREEN)
        lcov_reports.append(dest)

    # Generate the HTML report.
    genhtml_cmd = ['genhtml', '-q', '-o', out_dir, '-p', build_top]
    genhtml_cmd.extend(lcov_reports)
    result = subprocess.check_call(genhtml_cmd, stderr=subprocess.STDOUT)
    logging.debug(result.stdout)
    atest_utils.colorful_print(
        f'Java code coverage report written to {out_dir}.', constants.GREEN)
    atest_utils.colorful_print(
        f'To open, Ctrl+Click on file://{out_dir}/index.html', constants.GREEN)
