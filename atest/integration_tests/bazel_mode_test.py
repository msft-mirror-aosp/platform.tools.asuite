#!/usr/bin/env python3
#
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

"""Integration tests for the Atest Bazel mode feature."""

# pylint: disable=invalid-name
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring

import dataclasses
import os
import shutil
import string
import subprocess
import tempfile
import unittest

from pathlib import Path
from typing import Any, Dict, Tuple


_ENV_BUILD_TOP = 'ANDROID_BUILD_TOP'
_PASSING_CLASS_NAME = 'PassingHostTest'
_FAILING_CLASS_NAME = 'FailingHostTest'
_PASSING_METHOD_NAME = 'testPass'
_FAILING_METHOD_NAME = 'testFAIL'


@dataclasses.dataclass(frozen=True)
class TestSource:
    class_name: str
    src_body: str


class BazelModeTest(unittest.TestCase):

    def setUp(self):
        self.src_root_path = Path(os.environ['ANDROID_BUILD_TOP'])
        self.test_dir = self.src_root_path.joinpath('atest_bazel_mode_test')
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.out_dir_path = Path(tempfile.mkdtemp())
        self.test_env = self.setup_test_env()

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        shutil.rmtree(self.out_dir_path)

    def test_passing_test_returns_zero_exit_code(self):
        module_name = 'passing_java_host_test'
        self.add_passing_test(module_name)

        completed_process = self.run_shell_command(
            f'atest -c -m --bazel-mode {module_name}')

        self.assertEqual(completed_process.returncode, 0)

    def test_failing_test_returns_nonzero_exit_code(self):
        module_name = 'failing_java_host_test'
        self.add_failing_test(module_name)

        completed_process = self.run_shell_command(
            f'atest -c -m --bazel-mode {module_name}')

        self.assertNotEqual(completed_process.returncode, 0)

    def test_passing_test_is_cached_when_rerun(self):
        module_name = 'passing_java_host_test'
        self.add_passing_test(module_name)

        completed_process = self.run_shell_command(
            f'atest -c -m --bazel-mode {module_name} && '
            f'atest --bazel-mode {module_name}')

        self.assert_in_stdout(f':{module_name}_host (cached) PASSED',
                              completed_process)

    def test_cached_test_reruns_when_modified(self):
        module_name = 'passing_java_host_test'
        java_test_file, _ = self.write_java_test_module(
            module_name, passing_java_test_source())
        self.run_shell_command(
            f'atest -c -m --bazel-mode {module_name}')

        java_test_file.write_text(
            failing_java_test_source(
                test_class_name=_PASSING_CLASS_NAME).src_body)
        completed_process = self.run_shell_command(
            f'atest --bazel-mode {module_name}')

        self.assert_in_stdout(f':{module_name}_host FAILED',
                              completed_process)

    def test_only_supported_test_run_with_bazel(self):
        module_name = 'passing_java_host_test'
        unsupported_module_name = 'unsupported_passing_java_test'
        self.add_passing_test(module_name)
        self.add_unsupported_passing_test(unsupported_module_name)

        completed_process = self.run_shell_command(
            f'atest -c -m --host --bazel-mode {module_name} '
            f'{unsupported_module_name}')

        self.assert_in_stdout(f':{module_name}_host PASSED',
                              completed_process)
        self.assert_in_stdout(
            f'{_PASSING_CLASS_NAME}#{_PASSING_METHOD_NAME}: PASSED',
            completed_process)

    def setup_test_env(self) -> Dict[str, Any]:
        test_env = {
            'PATH': os.environ['PATH'],
            'HOME': os.environ['HOME'],
            'OUT_DIR': str(self.out_dir_path),
        }
        return test_env

    def run_shell_command(
        self,
        shell_command: str,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            '. build/envsetup.sh && '
            'lunch aosp_cf_x86_64_pc-userdebug && '
            f'{shell_command}',
            env=self.test_env,
            cwd=self.src_root_path,
            shell=True,
            check=False,
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE)

    def add_passing_test(self, module_name: str):
        self.write_java_test_module(
            module_name, passing_java_test_source())

    def add_failing_test(self, module_name: str):
        self.write_java_test_module(
            module_name, failing_java_test_source())

    def add_unsupported_passing_test(self, module_name: str):
        self.write_java_test_module(
            module_name, passing_java_test_source(), is_unit_test='false')

    def write_java_test_module(
        self,
        module_name: str,
        test_src: TestSource,
        is_unit_test: str='true',
    ) -> Tuple[Path, Path]:
        test_dir = self.test_dir.joinpath(module_name)
        test_dir.mkdir(parents=True, exist_ok=True)

        src_file_name = f'{test_src.class_name}.java'
        src_file_path = test_dir.joinpath(f'{src_file_name}')
        src_file_path.write_text(test_src.src_body, encoding='utf8')

        bp_file_path = test_dir.joinpath('Android.bp')
        bp_file_path.write_text(
            android_bp_source(module_name=module_name,
                              src_file=str(src_file_name),
                              is_unit_test=is_unit_test),
            encoding='utf8')
        return (src_file_path, bp_file_path)

    def assert_in_stdout(
        self,
        message: str,
        completed_process: subprocess.CompletedProcess,
    ):
        self.assertIn(message, completed_process.stdout.decode())


def passing_java_test_source() -> TestSource:
    return java_test_source(
        test_class_name=_PASSING_CLASS_NAME,
        test_method_name=_PASSING_METHOD_NAME,
        test_method_body='Assert.assertEquals("Pass", "Pass");')


def failing_java_test_source(test_class_name=_FAILING_CLASS_NAME) -> TestSource:
    return java_test_source(
        test_class_name=test_class_name,
        test_method_name=_FAILING_METHOD_NAME,
        test_method_body='Assert.assertEquals("Pass", "Fail");')


def java_test_source(
    test_class_name: str,
    test_method_name: str,
    test_method_body: str,
) -> TestSource:
    return TestSource(test_class_name, JAVA_TEST_TEMPLATE.substitute(
        test_class_name=test_class_name,
        test_method_name=test_method_name,
        test_method_body=test_method_body))


def android_bp_source(
    module_name: str,
    src_file: str,
    is_unit_test: str = 'true',
):
    return ANDROID_BP_TEMPLATE.substitute(
        module_name=module_name, src_file=src_file,
        is_unit_test=is_unit_test)


ANDROID_BP_TEMPLATE = string.Template("""\
package {
    default_applicable_licenses: ["Android-Apache-2.0"],
}

java_test_host {
    name: "${module_name}",
    test_suites: ["general-tests"],
    srcs: ["${src_file}"],
    static_libs: [
        "junit",
    ],
    test_options: {
        unit_test: ${is_unit_test},
    },
}
""")


JAVA_TEST_TEMPLATE = string.Template("""\
package android.android;

import org.junit.Assert;
import org.junit.Test;
import org.junit.runners.JUnit4;
import org.junit.runner.RunWith;

@RunWith(JUnit4.class)
public final class ${test_class_name} {

    @Test
    public void ${test_method_name}() {
        ${test_method_body}
    }
}
""")


if __name__ == '__main__':
    unittest.main(verbosity=2)
