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

"""Base test module for Atest integration tests."""

import unittest

import split_build_test_script

# Exporting for test modules' reference
AtestIntegrationTest = split_build_test_script.AtestIntegrationTest


class AtestTestCase(unittest.TestCase):
    """Base test case for build-test environment split integration tests."""

    injected_config = None

    # Default include list of repo paths for taking snapshot
    _default_include_paths = [
        'out/host/linux-x86',
        'out/target/product/*/module-info*',
        'out/target/product/*/testcases',
        'out/target/product/*/all_modules.txt',
        'out/soong/module_bp*',
        'tools/asuite/atest/test_runners/roboleaf_launched.txt',
        '.repo/manifest.xml',
        'build/soong/soong_ui.bash',
        'build/bazel_common_rules/rules/python/stubs',
        'build/bazel/bin',
        'external/bazelbuild-rules_java',
        'tools/asuite/atest/bazel/resources/bazel.sh',
        'prebuilts/bazel/linux-x86_64',
        'prebuilts/build-tools/path/linux-x86/python3',
        'prebuilts/build-tools/linux-x86/bin/py3-cmd',
        'prebuilts/build-tools',
    ]

    # Default exclude list of repo paths for taking snapshot
    _default_exclude_paths = [
        'out/host/linux-x86/bin/go',
        'out/host/linux-x86/bin/soong_build',
        'out/host/linux-x86/obj',
    ]

    # Default exclude list of repo paths for restoring snapshot
    _default_restore_exclude_paths = ['out/atest_bazel_workspace']

    # Default list of environment variables to take and restore in snapshots
    _default_env_keys = [
        split_build_test_script.ANDROID_BUILD_TOP_KEY,
        'ANDROID_HOST_OUT',
        'ANDROID_PRODUCT_OUT',
        'ANDROID_HOST_OUT_TESTCASES',
        'ANDROID_TARGET_OUT_TESTCASES',
        'OUT',
        'PATH',
        'HOST_OUT_TESTCASES',
        'ANDROID_JAVA_HOME',
        'JAVA_HOME',
    ]

    def create_atest_integration_test(self):
        """Create an instance of atest integration test utility."""
        atest = AtestIntegrationTest(self.id(), self.injected_config)
        atest.add_snapshot_include_paths(*self._default_include_paths)
        atest.add_snapshot_exclude_paths(*self._default_exclude_paths)
        atest.add_snapshot_restore_exclude_paths(
            *self._default_restore_exclude_paths
        )
        atest.add_env_keys(*self._default_env_keys)
        return atest


def main():
    """Main method to run the integration tests."""
    split_build_test_script.main(make_before_build=['atest'])
