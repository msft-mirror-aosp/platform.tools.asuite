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

import json
from pathlib import Path
import subprocess
from typing import Callable
from atest_integration_test import AtestIntegrationTest, AtestTestCase
from atest_integration_test import run_tests


class CommandSuccessTests(AtestTestCase):
    """Test whether the atest commands run with success exit codes."""

    def test_csuite_harness_tests(self):
        """Test if csuite-harness-tests command runs successfully."""
        atest = self.create_atest_integration_test()
        if atest.in_build_env():
            subprocess.run(
                'atest-dev -b csuite-harness-tests'.split(),
                check=True,
                env=atest.get_env(),
                cwd=atest.get_repo_root(),
            )

        if atest.in_test_env():
            subprocess.run(
                (
                    'atest-dev -it csuite-harness-tests -s '
                    + atest.get_device_serial()
                ).split(),
                check=True,
                env=atest.get_env(),
                cwd=atest.get_repo_root(),
            )

    def test_csuite_cli_test(self):
        """Test if csuite_cli_test command runs successfully."""
        atest = self.create_atest_integration_test()
        if atest.in_build_env():
            subprocess.run(
                'atest-dev -b csuite_cli_test'.split(),
                check=True,
                env=atest.get_env(),
                cwd=atest.get_repo_root(),
            )

        if atest.in_test_env():
            subprocess.run(
                (
                    'atest-dev -it csuite_cli_test -s '
                    + atest.get_device_serial()
                ).split(),
                check=True,
                env=atest.get_env(),
                cwd=atest.get_repo_root(),
            )


class CommandVerificationTests(AtestTestCase):
    """Checks atest tradefed commands."""

    # A file generated by the atest runners which contains the commands used
    # to execute the running test.
    _runner_commands_json = (
        'tools/asuite/atest/test_data/runner_commands.json'
    )
    # A file containing the test commands expected to be generate for specific
    # tests.
    _test_commands_json = (
        'tools/asuite/atest/test_data/test_commands.json'
    )

    def test_animator_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'AnimatorTest'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_cts_animation_test_cases_animator_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'CtsAnimationTestCases:AnimatorTest'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_cts_sample_device_cases_shared_prefs_test(self):
        """Verify that the test's command runs correctly."""
        test_name = ('CtsSampleDeviceTestCases:SampleDeviceTest#'
                     'testSharedPreferences')
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_cts_sample_device_cases_android_sample_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'CtsSampleDeviceTestCases:android.sample.cts'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_cts_sample_device_cases_device_report_log_test(self):
        """Verify that the test's command runs correctly."""
        test_name = ('CtsSampleDeviceTestCases:android.sample.cts'
                     '.SampleDeviceReportLogTest')
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_cts_animation_cases_sample_device_cases_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'CtsAnimationTestCases CtsSampleDeviceTestCases'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_hello_world_tests_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'HelloWorldTests'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_mixed_managed_profile_ownr_pw_sufficient_test(self):
        """Verify that the test's command runs correctly."""
        test_name = ('MixedManagedProfileOwnerTest#'
                     'testPasswordSufficientInitially')
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_perinstance_camerahidl_config_injection_test(self):
        """Verify that the test's command runs correctly."""
        test_name = ('PerInstance/CameraHidlTest#'
                     'configureInjectionStreamsAvailableOutputs/0_internal_0')
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_quick_access_wallet_robo_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'QuickAccessWalletRoboTests'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_vts_hal_camera_provider_config_injection_test(self):
        """Verify that the test's command runs correctly."""
        test_name = ('VtsHalCameraProviderV2_4TargetTest:PerInstance/'
                     'CameraHidlTest#configureInjectionStreamsAvailableOutputs/'
                     '0_internal_0')
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_android_animation_cts_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'android.animation.cts'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_android_sample_cts_device_report_log_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'android.sample.cts.SampleDeviceReportLogTest'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_android_sample_cts_shared_prefs_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'android.sample.cts.SampleDeviceTest#testSharedPreferences'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_hello_world_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'hello_world_test'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_native_benchmark_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'native-benchmark'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    # TODO(b/319324510): enable this test.
    # def test_quick_access_wallet_plugin_service_test(self):
    #     """Verify that the test's command runs correctly."""
    #     test_name = 'packages/apps/QuickAccessWallet/tests/robolectric/
    #     src/com/android/systemui/plugin/globalactions/wallet/
    #     WalletPluginServiceTest.java'
    #     self._verify_atest_internal_command(
    #         test_name,
    #         # atest_internal_command : a set of strings that represent a
    #         # test runner command.
    #         lambda atest_internal_command, atest:
    #         self.assertTrue(
    #             self._get_expected_cmds_from_file(
    #                 atest, test_name, self._test_commands_json
    #             )
    #             .issubset(atest_internal_command),
    #             "The expected commands are not a subset of the runner
    #             commands:\n" + str(atest_internal_command)
    #         ),
    #     )

    def test_platform_native_example_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'platform_testing/tests/example/native'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_platform_android_example_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'platform_testing/tests/example/native/Android.bp'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_tf_core_config_native_benchmark_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'tools/tradefederation/core/res/config/native-benchmark.xml'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_quick_access_wallet_robo_host_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'QuickAccessWalletRoboTests'
        test_args = ["--host"]
        expected_cmd = [
            "--include-filter",
            "--log-level",
            "--log-level-display",
            "--no-early-device-release",
            "--no-enable-granular-attempts",
            "--prioritize-host-config",
            "--skip-host-arch-check",
            "--skip-loading-config-jar",
            "--template:map",
            "--template:map",
            "-n",
            "QuickAccessWalletRoboTests",
            "VERBOSE",
            "VERBOSE",
            "atest_tradefed.sh",
            "log_saver=template/log/atest_log_saver",
            "template/atest_local_min",
            "test=atest"
        ]
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                set(expected_cmd)
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
            test_args
        )

    # TODO(319324510): enable this test.
    # def test_quick_access_wallet_plugin_service_host_test(self):
    #     """Verify that the test's command runs correctly."""
    #     test_name = 'HOST=True packages/apps/QuickAccessWallet/tests/
    #     robolectric/src/com/android/systemui/plugin/globalactions/wallet/
    #     WalletPluginServiceTest.java'
    #     self._verify_atest_internal_command(
    #         test_name,
    #         # atest_internal_command : a set of strings that represent a
    #         # test runner command.
    #         lambda atest_internal_command, atest:
    #         self.assertTrue(
    #             self._get_expected_cmds_from_file(
    #                 atest, test_name, self._test_commands_json
    #             )
    #             .issubset(atest_internal_command),
    #             "The expected commands are not a subset of the runner
    #             commands:\n" + str(atest_internal_command)
    #         ),
    #     )

    def test_cts_wifi_aware_cases_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'CtsWifiAwareTestCases'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_pts_bot_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'pts-bot:PAN/GN/MISC/UUID/BV-01-C'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_tee_ui_utils_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'TeeUIUtilsTest'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_tee_ui_utils_intersect_convext_obj_test(
        self
    ):
        """Verify that the test's command runs correctly."""
        test_name = ('TeeUIUtilsTest#intersectTest,ConvexObjectConstruction,'
                     'ConvexObjectLineIntersection')
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_cts_activity_mgr_register_ui_change_test(
        self
    ):
        """Verify that the test's command runs correctly."""
        test_name = ('CtsSecurityTestCases:android.security.cts.'
                     'ActivityManagerTest#testActivityManager_'
                     'registerUidChangeObserver_allPermission')
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_cts_activity_mgr_register_ui_change_java_test(self):
        """Verify that the test's command runs correctly."""
        test_name = ('cts/tests/tests/security/src/android/security/cts/'
                     'ActivityManagerTest.java#testActivityManager_'
                     'registerUidChangeObserver_allPermission')
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_permission_memory_footprint_apps_size_kt_test(self):
        """Verify that the test's command runs correctly."""
        test_name = ('cts/tests/tests/security/src/android/security/cts/'
                     'PermissionMemoryFootprintTest.kt#'
                     'checkAppsCantIncreasePermissionSizeAfterCreating')
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_permission_memory_footprint_test(self):
        """Verify that the test's command runs correctly."""
        test_name = 'android.security.cts.PermissionMemoryFootprintTest'
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def test_permission_memory_footprint_apps_size_test(self):
        """Verify that the test's command runs correctly."""
        test_name = ('android.security.cts.PermissionMemoryFootprintTest#'
                     'checkAppsCantIncreasePermissionSizeAfterCreating')
        self._verify_atest_internal_command(
            test_name,
            # atest_internal_command : a set of strings that represent a
            # test runner command.
            lambda atest_internal_command, atest:
            self.assertTrue(
                self._get_expected_cmds_from_file(
                    atest, test_name, self._test_commands_json
                )
                .issubset(atest_internal_command),
                "The expected commands are not a subset of the runner "
                "commands:\n" + str(atest_internal_command)
            ),
        )

    def _get_expected_cmds_from_file(
            self,
            atest: AtestIntegrationTest,
            test_name: str,
            file: str
    ) -> set[str]:
        """Looks up the given test in the dictionary of expected commands and
        returns the corresponding command as a set of strings.

        Args:
            atest: an instance of AtestIntegrationTest.
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
        assertion_func: Callable[[str, AtestIntegrationTest], None],
        test_args : list[str] = None
    ) -> None:
        """Verifies the command by executing it and checking its output.

        Args:
          cmd_list: The atest command to execute.
          assertion_func: A function that takes the atest internal command
            as a set of strings and runs assertions on it.
          test_args: A list of additional args to add to the test command for
          the given test.
        """
        atest = self.create_atest_integration_test()
        cmd_split = test_name.split()
        cmd_list = ['atest-dev', '-g']
        if test_args:
            cmd_list.extend(test_args)
        cmd_list.extend(cmd_split)

        if atest.in_build_env():
            Path(atest.get_repo_root()).joinpath(
                self._runner_commands_json).unlink(
                missing_ok=True
            )
            subprocess.run(
                cmd_list,
                check=True,
                env=atest.get_env(),
                cwd=atest.get_repo_root(),
                encoding='utf-8',
            )
            atest.add_snapshot_paths(
                self._runner_commands_json, self._test_commands_json
            )

        if atest.in_test_env():
            with open(
                    Path(atest.get_repo_root()).joinpath(
                        self._runner_commands_json),
                    'r',
                    encoding='utf-8',
            ) as f:
                runner_cmds_dict = json.load(f)
            assertion_func(
                set(runner_cmds_dict[test_name].split()),
                atest
            )


if __name__ == '__main__':
    run_tests()
