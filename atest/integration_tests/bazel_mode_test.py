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

import os
import shutil
import string
import subprocess
import tempfile
import unittest

from pathlib import Path
from typing import Any, Dict


_ENV_BUILD_TOP = 'ANDROID_BUILD_TOP'


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

        exit_code = self.run_shell_command(
            f'atest -c -m --bazel-mode {module_name}')

        self.assertEqual(exit_code, 0)

    def test_failing_test_returns_nonzero_exit_code(self):
        module_name = 'failing_java_host_test'
        self.add_failing_test(module_name)

        exit_code = self.run_shell_command(
            f'atest -c -m --bazel-mode {module_name}')

        self.assertNotEqual(exit_code, 0)

    def setup_test_env(self) -> Dict[str, Any]:
        test_env = {
            'PATH': os.environ['PATH'],
            'HOME': os.environ['HOME'],
            'OUT_DIR': str(self.out_dir_path),
        }
        return test_env

    def run_shell_command(self, shell_command: str) -> int:
        completed_process = subprocess.run(
            '. build/envsetup.sh && '
            'lunch aosp_cf_x86_64_pc-userdebug && '
            f'{shell_command}',
            env=self.test_env,
            cwd=self.src_root_path,
            shell=True,
            check=False,
            stderr=subprocess.DEVNULL)
        return completed_process.returncode

    def add_passing_test(self, module_name: str):
        test_method_body = 'Assert.assertEquals("Pass", "Pass");'
        self.create_java_test_module_files(
            module_name=module_name, test_class_name='PassingHostTest',
            test_method_name='testPass', test_method_body=test_method_body)

    def add_failing_test(self, module_name: str):
        test_method_body = 'Assert.assertEquals("Pass", "Fail");'
        self.create_java_test_module_files(
            module_name=module_name, test_class_name='FailingHostTest',
            test_method_name='testFail', test_method_body=test_method_body)

    def create_java_test_module_files(
        self,
        module_name: str,
        test_class_name: str,
        test_method_name:str,
        test_method_body: str,
    ):
        test_dir = self.test_dir.joinpath(module_name)
        test_dir.mkdir(parents=True, exist_ok=True)
        src_file_name = f'{test_class_name}.java'

        with open(test_dir.joinpath('Android.bp'), "w",
                  encoding='utf8') as output:
            output.write(ANDROID_BP_TEMPLATE.substitute(
                module_name=module_name, src_file=src_file_name))

        with open(test_dir.joinpath(src_file_name), "w",
                  encoding='utf8') as output:
            output.write(JAVA_TEST_TEMPLATE.substitute(
                test_class_name=test_class_name,
                test_method_name=test_method_name,
                test_method_body=test_method_body))


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
