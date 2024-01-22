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

"""A collection of integration test cases for atest."""

# pylint: disable=too-many-lines

import json
from pathlib import Path
from typing import Callable

from atest_integration_test import AtestTestCase, SplitBuildTestScript
from atest_integration_test import StepInput, StepOutput, main


class CommandVerificationTests(AtestTestCase):
    """Checks atest tradefed commands."""

    def test_animator_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'AnimatorTest'
        expected_cmd = [
            '--atest-include-filter',
            '--enable-parameterized-modules',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--log-level',
            '--log-level-display',
            '--module',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            '--test-arg',
            'CtsAnimationTestCases',
            'CtsAnimationTestCases:android.animation.cts.AnimatorTest',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            (
                'com.android.tradefed.testtype.AndroidJUnitTest:exclude'
                '-annotation:android.platform.test.annotations.AppModeInstant'
            ),
            'instant_app',
            'log_saver=template/log/atest_log_saver',
            'multi_abi',
            'secondary_user',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_cts_animation_test_cases_animator_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'CtsAnimationTestCases:AnimatorTest'
        expected_cmd = [
            '--atest-include-filter',
            '--enable-parameterized-modules',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--log-level',
            '--log-level-display',
            '--module',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            '--test-arg',
            'CtsAnimationTestCases',
            'CtsAnimationTestCases:android.animation.cts.AnimatorTest',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            (
                'com.android.tradefed.testtype.AndroidJUnitTest:exclude'
                '-annotation:android.platform.test.annotations.AppModeInstant'
            ),
            'instant_app',
            'log_saver=template/log/atest_log_saver',
            'multi_abi',
            'secondary_user',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_cts_sample_device_cases_shared_prefs_test(self):
        """Verify that the test's command runs correctly."""
        test_name = (
            'CtsSampleDeviceTestCases:SampleDeviceTest#testSharedPreferences'
        )
        expected_cmd = [
            '--atest-include-filter',
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            '--test-arg',
            'CtsSampleDeviceTestCases',
            (
                'CtsSampleDeviceTestCases:android.sample.cts.SampleDeviceTest'
                '#testSharedPreferences'
            ),
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            (
                'com.android.tradefed.testtype.AndroidJUnitTest:exclude'
                '-annotation:android.platform.test.annotations.AppModeInstant'
            ),
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_cts_sample_device_cases_android_sample_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'CtsSampleDeviceTestCases:android.sample.cts'
        expected_cmd = [
            '--atest-include-filter',
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            '--test-arg',
            'CtsSampleDeviceTestCases',
            'CtsSampleDeviceTestCases:android.sample.cts',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            (
                'com.android.tradefed.testtype.AndroidJUnitTest:exclude'
                '-annotation:android.platform.test.annotations.AppModeInstant'
            ),
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_cts_sample_device_cases_device_report_log_test(self):
        """Verify that the test's command runs correctly."""
        test_name = (
            'CtsSampleDeviceTestCases:android.sample.cts'
            '.SampleDeviceReportLogTest'
        )
        expected_cmd = [
            '--atest-include-filter',
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            '--test-arg',
            'CtsSampleDeviceTestCases',
            (
                'CtsSampleDeviceTestCases:android.sample.cts'
                '.SampleDeviceReportLogTest'
            ),
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            (
                'com.android.tradefed.testtype.AndroidJUnitTest:exclude'
                '-annotation:android.platform.test.annotations.AppModeInstant'
            ),
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_cts_animation_cases_sample_device_cases_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'CtsAnimationTestCases CtsSampleDeviceTestCases'
        expected_cmd = [
            '--include-filter',
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            '--test-arg',
            'CtsAnimationTestCases',
            'CtsSampleDeviceTestCases',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            (
                'com.android.tradefed.testtype.AndroidJUnitTest:exclude'
                '-annotation:android.platform.test.annotations.AppModeInstant'
            ),
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_hello_world_tests_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'HelloWorldTests'
        expected_cmd = [
            '--include-filter',
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'HelloWorldTests',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'hallo-welt',
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_mixed_managed_profile_ownr_pw_sufficient_test(self):
        """Verify that the test's command runs correctly."""
        test_name = (
            'MixedManagedProfileOwnerTest#testPasswordSufficientInitially'
        )
        expected_cmd = [
            '--atest-include-filter',
            '--enable-parameterized-modules',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--log-level',
            '--log-level-display',
            '--module',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'CtsDevicePolicyManagerTestCases',
            (
                'CtsDevicePolicyManagerTestCases:com.android.cts.devicepolicy'
                '.MixedManagedProfileOwnerTest#testPasswordSufficientInitially'
            ),
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'instant_app',
            'log_saver=template/log/atest_log_saver',
            'multi_abi',
            'secondary_user',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_perinstance_camerahidl_config_injection_test(self):
        """Verify that the test's command runs correctly."""
        test_name = (
            'PerInstance/CameraHidlTest#'
            'configureInjectionStreamsAvailableOutputs/0_internal_0'
        )
        expected_cmd = [
            '--atest-include-filter',
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'VERBOSE',
            'VERBOSE',
            'VtsHalCameraProviderV2_4TargetTest',
            (
                'VtsHalCameraProviderV2_4TargetTest:PerInstance/CameraHidlTest'
                '.configureInjectionStreamsAvailableOutputs/0_internal_0'
            ),
            'atest_tradefed.sh',
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_quick_access_wallet_robo_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'QuickAccessWalletRoboTests'
        expected_cmd = [
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'QuickAccessWalletRoboTests',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_vts_hal_camera_provider_config_injection_test(self):
        """Verify that the test's command runs correctly."""
        test_name = (
            'VtsHalCameraProviderV2_4TargetTest:PerInstance/'
            'CameraHidlTest#configureInjectionStreamsAvailableOutputs/'
            '0_internal_0'
        )
        expected_cmd = [
            '--atest-include-filter',
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'VERBOSE',
            'VERBOSE',
            'VtsHalCameraProviderV2_4TargetTest',
            (
                'VtsHalCameraProviderV2_4TargetTest:PerInstance/CameraHidlTest'
                '.configureInjectionStreamsAvailableOutputs/0_internal_0'
            ),
            'atest_tradefed.sh',
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_android_animation_cts_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'android.animation.cts'
        expected_cmd = [
            '--atest-include-filter',
            '--enable-parameterized-modules',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--log-level',
            '--log-level-display',
            '--module',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            '--test-arg',
            'CtsAnimationTestCases',
            'CtsAnimationTestCases:android.animation.cts',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            (
                'com.android.tradefed.testtype.AndroidJUnitTest:exclude'
                '-annotation:android.platform.test.annotations.AppModeInstant'
            ),
            'instant_app',
            'log_saver=template/log/atest_log_saver',
            'multi_abi',
            'secondary_user',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_android_sample_cts_device_report_log_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'android.sample.cts.SampleDeviceReportLogTest'
        expected_cmd = [
            '--atest-include-filter',
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            '--test-arg',
            'CtsSampleDeviceTestCases',
            (
                'CtsSampleDeviceTestCases:android.sample.cts'
                '.SampleDeviceReportLogTest'
            ),
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            (
                'com.android.tradefed.testtype.AndroidJUnitTest:exclude'
                '-annotation:android.platform.test.annotations.AppModeInstant'
            ),
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_android_sample_cts_shared_prefs_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'android.sample.cts.SampleDeviceTest#testSharedPreferences'
        expected_cmd = [
            '--atest-include-filter',
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            '--test-arg',
            'CtsSampleDeviceTestCases',
            (
                'CtsSampleDeviceTestCases:android.sample.cts.SampleDeviceTest'
                '#testSharedPreferences'
            ),
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            (
                'com.android.tradefed.testtype.AndroidJUnitTest:exclude'
                '-annotation:android.platform.test.annotations.AppModeInstant'
            ),
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_hello_world_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'hello_world_test'
        expected_cmd = [
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'hello_world_test',
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_native_benchmark_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'native-benchmark'
        expected_cmd = [
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--template:map',
            '--template:map',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'log_saver=template/log/atest_log_saver',
            'native-benchmark',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_platform_native_example_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'platform_testing/tests/example/native'
        expected_cmd = [
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'hello_world_test',
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_platform_android_example_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'platform_testing/tests/example/native/Android.bp'
        expected_cmd = [
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'hello_world_test',
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_tf_core_config_native_benchmark_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'tools/tradefederation/core/res/config/native-benchmark.xml'
        expected_cmd = [
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--template:map',
            '--template:map',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'log_saver=template/log/atest_log_saver',
            'native-benchmark',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_quick_access_wallet_robo_host_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'QuickAccessWalletRoboTests'
        test_args = ['--host']
        expected_cmd = [
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--prioritize-host-config',
            '--skip-host-arch-check',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            '-n',
            'QuickAccessWalletRoboTests',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
            test_args,
        )

    def test_cts_wifi_aware_cases_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'CtsWifiAwareTestCases'
        expected_cmd = [
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--multi-device-count',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--replicate-parent-setup',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            '2',
            'CtsWifiAwareTestCases',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'log_saver=template/log/atest_log_saver',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_pts_bot_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'pts-bot:PAN/GN/MISC/UUID/BV-01-C'
        expected_cmd = [
            '--atest-include-filter',
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'log_saver=template/log/atest_log_saver',
            'pts-bot',
            'pts-bot:PAN/GN/MISC/UUID/BV-01-C',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_tee_ui_utils_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'TeeUIUtilsTest'
        expected_cmd = [
            '--atest-include-filter',
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'log_saver=template/log/atest_log_saver',
            'teeui_unit_tests',
            'teeui_unit_tests:TeeUIUtilsTest.*',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_tee_ui_utils_intersect_convext_obj_test(self):
        """Verify that the test's command runs correctly."""
        test_name = (
            'TeeUIUtilsTest#intersectTest,ConvexObjectConstruction,'
            'ConvexObjectLineIntersection'
        )
        expected_cmd = [
            '--atest-include-filter',
            '--include-filter',
            '--log-level',
            '--log-level-display',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'log_saver=template/log/atest_log_saver',
            'teeui_unit_tests',
            (
                'teeui_unit_tests:TeeUIUtilsTest.ConvexObjectConstruction'
                ':TeeUIUtilsTest.ConvexObjectLineIntersection:TeeUIUtilsTest'
                '.intersectTest'
            ),
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_cts_activity_mgr_register_ui_change_test(self):
        """Verify that the test's command runs correctly."""
        test_name = (
            'CtsSecurityTestCases:android.security.cts.'
            'ActivityManagerTest#testActivityManager_'
            'registerUidChangeObserver_allPermission'
        )
        expected_cmd = [
            '--atest-include-filter',
            '--enable-parameterized-modules',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--log-level',
            '--log-level-display',
            '--module',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'CtsSecurityTestCases',
            (
                'CtsSecurityTestCases:android.security.cts.ActivityManagerTest'
                '#testActivityManager_registerUidChangeObserver_allPermission'
            ),
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'instant_app',
            'log_saver=template/log/atest_log_saver',
            'multi_abi',
            'secondary_user',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_cts_activity_mgr_register_ui_change_java_test(self):
        """Verify that the test's command runs correctly."""
        test_name = (
            'cts/tests/tests/security/src/android/security/cts/'
            'ActivityManagerTest.java#testActivityManager_'
            'registerUidChangeObserver_allPermission'
        )
        expected_cmd = [
            '--atest-include-filter',
            '--enable-parameterized-modules',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--log-level',
            '--log-level-display',
            '--module',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'CtsSecurityTestCases',
            (
                'CtsSecurityTestCases:android.security.cts.ActivityManagerTest'
                '#testActivityManager_registerUidChangeObserver_allPermission'
            ),
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'instant_app',
            'log_saver=template/log/atest_log_saver',
            'multi_abi',
            'secondary_user',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_permission_memory_footprint_apps_size_kt_test(self):
        """Verify that the test's command runs correctly."""
        test_name = (
            'cts/tests/tests/security/src/android/security/cts/'
            'PermissionMemoryFootprintTest.kt#'
            'checkAppsCantIncreasePermissionSizeAfterCreating'
        )
        expected_cmd = [
            '--atest-include-filter',
            '--enable-parameterized-modules',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--log-level',
            '--log-level-display',
            '--module',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'CtsSecurityTestCases',
            (
                'CtsSecurityTestCases:android.security.cts'
                '.PermissionMemoryFootprintTest'
                '#checkAppsCantIncreasePermissionSizeAfterCreating'
            ),
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'instant_app',
            'log_saver=template/log/atest_log_saver',
            'multi_abi',
            'secondary_user',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_permission_memory_footprint_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'android.security.cts.PermissionMemoryFootprintTest'
        expected_cmd = [
            '--atest-include-filter',
            '--enable-parameterized-modules',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--log-level',
            '--log-level-display',
            '--module',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'CtsSecurityTestCases',
            (
                'CtsSecurityTestCases:android.security.cts'
                '.PermissionMemoryFootprintTest'
            ),
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'instant_app',
            'log_saver=template/log/atest_log_saver',
            'multi_abi',
            'secondary_user',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def test_permission_memory_footprint_apps_size_test(self):
        """Verify that the test's command runs correctly."""
        test_name = (
            'android.security.cts.PermissionMemoryFootprintTest#'
            'checkAppsCantIncreasePermissionSizeAfterCreating'
        )
        expected_cmd = [
            '--atest-include-filter',
            '--enable-parameterized-modules',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--exclude-module-parameters',
            '--log-level',
            '--log-level-display',
            '--module',
            '--no-early-device-release',
            '--no-enable-granular-attempts',
            '--skip-loading-config-jar',
            '--template:map',
            '--template:map',
            'CtsSecurityTestCases',
            (
                'CtsSecurityTestCases:android.security.cts'
                '.PermissionMemoryFootprintTest'
                '#checkAppsCantIncreasePermissionSizeAfterCreating'
            ),
            'VERBOSE',
            'VERBOSE',
            'atest_tradefed.sh',
            'instant_app',
            'log_saver=template/log/atest_log_saver',
            'multi_abi',
            'secondary_user',
            'template/atest_local_min',
            'test=atest',
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command: self.assertTrue(
                set(expected_cmd).issubset(atest_internal_command),
                'The expected commands are not a subset of the runner '
                'commands:\n'
                + str(atest_internal_command),
            ),
        )

    def _get_expected_cmds_from_file(
        self, atest: SplitBuildTestScript, test_name: str, file: str
    ) -> set[str]:
        """Looks up the given test in the dictionary of expected commands and

        returns the corresponding command as a set of strings.

        Args:
            atest: an instance of SplitBuildTestScript.
            test_name: the name of the test to look up in the expected commands
              dictionary.
            file: a file containing a dictionary of expected tests commands.

        Returns:
            A set of strings representing the expected commands to run for the
            given test.
        """
        with open(
            Path(atest.get_repo_root()).joinpath(file),
            'r',
            encoding='utf-8',
        ) as f:
            dict_from_json = json.load(f)
        return set(dict_from_json[test_name])

    def _verify_atest_internal_command(
        self,
        test_name: str,
        assertion_func: Callable[str, None],
        test_args: list[str] = None,
    ) -> None:
        """Verifies the command by executing it and checking its output.

        Args:
          cmd_list: The atest command to execute.
          assertion_func: A function that takes the atest internal command as a
            set of strings and runs assertions on it.
          test_args: A list of additional args to add to the test command for
            the given test.
        """
        script = self.create_atest_script()

        def build_step(step_in: StepInput) -> StepOutput:
            # Path to json file created by the atest -g flag
            runner_commands_json_path = Path(step_in.get_repo_root()).joinpath(
                'tools/asuite/atest/test_data/runner_commands.json'
            )
            runner_commands_json_path.unlink(missing_ok=True)

            cmd_combined = (
                test_name + ' -g ' + ' '.join(test_args if test_args else [])
            )
            self.run_atest_dev(cmd_combined, step_in).check_returncode()

            with open(runner_commands_json_path, 'r', encoding='utf-8') as f:
                runner_cmds_dict = json.load(f)

            step_out = self.create_step_output()
            step_out.set_snapshot_include_paths([])
            step_out.add_snapshot_obj('runner_cmds_dict', runner_cmds_dict)
            return step_out

        def test_step(step_in: StepInput) -> None:
            runner_cmds_dict = step_in.get_obj('runner_cmds_dict')
            assertion_func(set(runner_cmds_dict[test_name].split()))

        script.add_build_step(build_step)
        script.add_test_step(test_step)
        script.run()


if __name__ == '__main__':
    main()