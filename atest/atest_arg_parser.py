#!/usr/bin/env python
#
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

"""Atest Argument Parser class for atest."""

# TODO: (@jimtang) Unsuppress too-many-lines Pylint warning.
# pylint: disable=too-many-lines

import argparse
import pydoc

from atest import bazel_mode
from atest import constants
from atest.atest_utils import BuildOutputMode


def output_mode_msg() -> str:
  """Generate helper strings for BuildOutputMode."""
  msg = []
  for _, value in BuildOutputMode.__members__.items():
    if value == BuildOutputMode.STREAMED:
      msg.append(
          f'\t\t{BuildOutputMode.STREAMED.value}: '
          'full output like what "m" does. (default)'
      )
    elif value == BuildOutputMode.LOGGED:
      msg.append(
          f'\t\t{BuildOutputMode.LOGGED.value}: '
          'print build output to a log file.'
      )
    else:
      raise RuntimeError('Found unknown attribute!')
  return '\n'.join(msg)


def _positive_int(value):
  """Verify value by whether or not a positive integer.

  Args:
      value: A string of a command-line argument.

  Returns:
      int of value, if it is a positive integer.
      Otherwise, raise argparse.ArgumentTypeError.
  """
  err_msg = "invalid positive int value: '%s'" % value
  try:
    converted_value = int(value)
    if converted_value < 1:
      raise argparse.ArgumentTypeError(err_msg)
    return converted_value
  except ValueError as value_err:
    raise argparse.ArgumentTypeError(err_msg) from value_err


class AtestArgParser(argparse.ArgumentParser):
  """Atest wrapper of ArgumentParser."""

  def __init__(self):
    """Initialise an ArgumentParser instance."""
    super().__init__(
        description=HELP_DESC,
        add_help=True,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

  # pylint: disable=too-many-statements
  def add_atest_args(self):
    """A function that does ArgumentParser.add_argument()"""
    self.add_argument('tests', nargs='*', help='Tests to build and/or run.')

    self.add_argument(
        '--minimal-build',
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            'Build required dependencies only. Use --no-minimal-build to'
            ' disable it.'
        ),
    )
    self.add_argument(
        '--update-device',
        action='store_true',
        help=(
            'Build and deploy your changes to the device. By default, ATest'
            ' will build `sync` and use `adevice` to update the device.'
        ),
    )

    # Options that to do with testing.
    self.add_argument(
        '-a',
        '--all-abi',
        action='store_true',
        help='Set to run tests for all abis.',
    )
    self.add_argument(
        '-b',
        '--build',
        action='append_const',
        dest='steps',
        const=constants.BUILD_STEP,
        help='Run a build.',
    )
    self.add_argument(
        '--bazel-mode',
        default=True,
        action='store_true',
        help='Run tests using Bazel.',
    )
    self.add_argument(
        '--no-bazel-mode',
        dest='bazel_mode',
        action='store_false',
        help='Run tests using Bazel.',
    )
    self.add_argument(
        '--bazel-arg',
        nargs='*',
        action='append',
        help=(
            'Forward a flag to Bazel for tests executed with Bazel; see'
            ' --bazel-mode.'
        ),
    )
    bazel_mode.add_parser_arguments(self, dest='bazel_mode_features')

    self.add_argument(
        '-d',
        '--disable-teardown',
        action='store_true',
        help='Disable test teardown and cleanup.',
    )
    self.add_argument(
        '--experimental-coverage',
        action='store_true',
        help=(
            'Instrument tests with code coverage and generate a code coverage'
            ' report.'
        ),
    )

    self.add_argument(
        '--group-test',
        default=True,
        action='store_true',
        help=(
            'Group the tests by module name for running the test, if you want'
            ' to run the test using the same input order, use --no-group-test.'
        ),
    )
    self.add_argument(
        '--no-group-test',
        dest='group_test',
        action='store_false',
        help=(
            'Group the tests by module name for running the test, if you want'
            ' to run the test using the same input order, use --no-group-test.'
        ),
    )

    # Options for host and device-only:
    # A group of options for testing mapping tests. They are mutually
    # exclusive in a command line.
    hgroup = self.add_mutually_exclusive_group()
    hgroup.add_argument(
        '--host',
        action='store_true',
        help=(
            'Run the test completely on the host without a device. (Note:'
            ' running a host test that requires a device without --host will'
            ' fail.)'
        ),
    )
    hgroup.add_argument(
        '--device-only',
        action='store_true',
        help=(
            'Only run tests that require a device. (Note: only workable with'
            ' --test-mapping.)'
        ),
    )
    self.add_argument(
        '-i',
        '--install',
        action='append_const',
        dest='steps',
        const=constants.INSTALL_STEP,
        help='Install an APK.',
    )
    self.add_argument(
        '-m',
        constants.REBUILD_MODULE_INFO_FLAG,
        action='store_true',
        help=(
            'Forces a rebuild of the module-info.json file. This may be'
            ' necessary following a repo sync or when writing a new test.'
        ),
    )
    self.add_argument(
        '--sharding',
        nargs='?',
        const=2,
        type=_positive_int,
        default=0,
        help='Option to specify sharding count. (default: 2)',
    )
    self.add_argument(
        '--sqlite-module-cache',
        action=argparse.BooleanOptionalAction,
        default=True,
        help='Use SQLite database as cache instead of JSON.',
    )
    self.add_argument(
        '-t',
        '--test',
        action='append_const',
        dest='steps',
        const=constants.TEST_STEP,
        help=(
            'Run the tests. WARNING: Many test configs force cleanup of device'
            ' after test run. In this case, "-d" must be used in previous test'
            ' run to disable cleanup for "-t" to work. Otherwise, device will'
            ' need to be setup again with "-i".'
        ),
    )
    self.add_argument(
        '--use-modules-in',
        help=(
            'Force include MODULES-IN-* as build targets. Hint: This may solve'
            ' missing test dependencies issue.'
        ),
        action='store_true',
    )
    self.add_argument(
        '-w',
        '--wait-for-debugger',
        action='store_true',
        help=(
            'Wait for debugger prior to execution (Instrumentation tests only).'
        ),
    )

    # Options for request/disable upload results. They are mutually
    # exclusive in a command line.
    ugroup = self.add_mutually_exclusive_group()
    ugroup.add_argument(
        '--request-upload-result',
        action='store_true',
        help=(
            'Request permission to upload test result. This option only needs'
            ' to set once and takes effect until --disable-upload-result is'
            ' set.'
        ),
    )
    ugroup.add_argument(
        '--disable-upload-result',
        action='store_true',
        help=(
            'Turn off the upload of test result. This option only needs to set'
            ' once and takes effect until --request-upload-result is set'
        ),
    )

    mgroup = self.add_mutually_exclusive_group()
    # Options related to Test Mapping
    mgroup.add_argument(
        '-p',
        '--test-mapping',
        action='store_true',
        help='Run tests defined in TEST_MAPPING files.',
    )
    self.add_argument(
        '--include-subdirs',
        action='store_true',
        help='Search TEST_MAPPING files in subdirs as well.',
    )
    # TODO(146980564): Remove enable-file-patterns when support
    # file-patterns in TEST_MAPPING by default.
    self.add_argument(
        '--enable-file-patterns',
        action='store_true',
        help='Enable FILE_PATTERNS in TEST_MAPPING.',
    )

    # Options related to Host Unit Test.
    mgroup.add_argument(
        '--host-unit-test-only',
        action='store_true',
        help='Run all host unit tests under the current directory.',
    )

    # Options for information queries and dry-runs:
    # A group of options for dry-runs. They are mutually exclusive
    # in a command line.
    group = self.add_mutually_exclusive_group()
    group.add_argument(
        '--collect-tests-only',
        action='store_true',
        help=(
            'Collect a list test cases of the instrumentation tests without'
            ' testing them in real.'
        ),
    )
    group.add_argument(
        '--dry-run',
        action='store_true',
        help=(
            'Dry run atest without building, installing and running tests in'
            ' real.'
        ),
    )
    self.add_argument('--info', action='store_true', help='Deprecated')
    self.add_argument(
        '-L', '--list-modules', help='List testable modules of the given suite.'
    )
    self.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Display DEBUG level logging.',
    )
    self.add_argument(
        '-V', '--version', action='store_true', help='Display version string.'
    )
    self.add_argument(
        '--build-output',
        default=BuildOutputMode.STREAMED,
        choices=BuildOutputMode,
        type=BuildOutputMode,
        help=(
            'Specifies the desired build output mode. Valid values are:'
            f' {output_mode_msg()}'
        ),
    )

    # Options that to do with acloud/AVDs.
    agroup = self.add_mutually_exclusive_group()
    agroup.add_argument(
        '--acloud-create',
        nargs=argparse.REMAINDER,
        type=str,
        help='(For testing with AVDs) Create AVD(s) via acloud command.',
    )
    agroup.add_argument(
        '--start-avd',
        action='store_true',
        help=(
            '(For testing with AVDs) Automatically create an AVD and run tests'
            ' on the virtual device.'
        ),
    )
    agroup.add_argument(
        '-s', '--serial', action='append', help='The device to run the test on.'
    )

    # Options to enable selection menu when multiple test configs belong to
    # same test module.
    self.add_argument(
        '--test-config-select',
        action='store_true',
        help=(
            'If multiple test config belong to same test module pop out a'
            ' selection menu on console.'
        ),
    )

    # Options related to module parameterization
    self.add_argument(
        '--instant',
        action='store_true',
        help=(
            '(For module parameterization) Run the instant_app version of the'
            " module if the module supports it. Note: Nothing's going to run if"
            " it's not an Instant App test and '--instant' is passed."
        ),
    )
    self.add_argument(
        '--user-type',
        help=(
            '(For module parameterization) Run test with specific user type,'
            ' e.g. atest <test> --user-type secondary_user'
        ),
    )
    self.add_argument(
        '--annotation-filter',
        action='append',
        help=(
            '(For module parameterization) Accept keyword that will be'
            ' translated to fully qualifiedannotation class name.'
        ),
    )

    # Option for dry-run command mapping result and cleaning cache.
    self.add_argument(
        '-c',
        '--clear-cache',
        action='store_true',
        help=(
            'Wipe out the test_infos cache of the test and start a new search.'
        ),
    )
    self.add_argument(
        '-g',
        '--generate-runner-cmd',
        action='store_true',
        help='Generate the runner command(s) of given tests.',
    )
    # Options for Tradefed debug mode.
    self.add_argument(
        '-D',
        '--tf-debug',
        nargs='?',
        const=10888,
        type=_positive_int,
        default=0,
        help=(
            'Enable tradefed debug mode with a specified port. (default: 10888)'
        ),
    )
    # Options for Tradefed customization related.
    self.add_argument(
        '--tf-template',
        action='append',
        help=(
            'Add extra tradefed template for ATest suite, e.g. atest <test>'
            ' --tf-template <template_key>=<template_path>'
        ),
    )
    self.add_argument(
        '--test-filter',
        nargs='?',
        help='Run tests which are specified using this option.',
    )
    self.add_argument(
        '--test-timeout',
        nargs='?',
        type=int,
        help=(
            'Customize test timeout. E.g. 60000(in milliseconds) represents 1'
            ' minute timeout. For no timeout, set to 0.'
        ),
    )

    # A group of options for rerun strategy. They are mutually exclusive
    # in a command line.
    group = self.add_mutually_exclusive_group()
    # Option for rerun tests for the specified number iterations.
    group.add_argument(
        '--iterations',
        nargs='?',
        type=_positive_int,
        const=10,
        default=0,
        metavar='MAX_ITERATIONS',
        help=(
            '(For iteration testing) Loop-run tests until the max iteration is'
            ' reached. (default: 10)'
        ),
    )
    group.add_argument(
        '--rerun-until-failure',
        nargs='?',
        type=_positive_int,
        # For Integer.MAX_VALUE == (2**31 - 1) and not possible to give a larger
        # integer to Tradefed, 2147483647 will be plentiful (~68 years).
        const=2147483647,
        default=0,
        metavar='MAX_ITERATIONS',
        help=(
            '(For iteration testing) Rerun all tests until a failure occurs or'
            ' the max iteration is reached. (default: forever!)'
        ),
    )
    group.add_argument(
        '--retry-any-failure',
        nargs='?',
        type=_positive_int,
        const=10,
        default=0,
        metavar='MAX_ITERATIONS',
        help=(
            '(For iteration testing) Rerun failed tests until passed or the max'
            ' iteration is reached. (default: 10)'
        ),
    )

    # A group of options for history. They are mutually exclusive
    # in a command line.
    history_group = self.add_mutually_exclusive_group()
    # History related options.
    history_group.add_argument(
        '--latest-result', action='store_true', help='Print latest test result.'
    )
    history_group.add_argument(
        '--history',
        nargs='?',
        const='99999',
        help=(
            'Show test results in chronological order(with specified number or'
            ' all by default).'
        ),
    )

    # Options for disabling collecting data for metrics.
    self.add_argument(
        constants.NO_METRICS_ARG,
        action='store_true',
        help='(For metrics) Do not send metrics.',
    )

    # Option to filter the output of aggregate metrics content.
    self.add_argument(
        '--aggregate-metric-filter',
        action='append',
        help=(
            '(For performance testing) Regular expression that will be used for'
            ' filtering the aggregated metrics.'
        ),
    )

    # Option that allows building and running without regarding device
    # availability even the given test is a device/host-driven test.
    self.add_argument(
        '--no-checking-device',
        action='store_true',
        help='Do NOT check device availability. (even it is a device test)',
    )

    # Option for customize build process number.
    self.add_argument(
        '-j',
        '--build-j',
        nargs='?',
        type=int,
        help='Build run process number at once.',
    )

    # This arg actually doesn't consume anything, it's primarily used for
    # the help description and creating custom_args in the NameSpace object.
    self.add_argument(
        '--',
        dest='custom_args',
        nargs='*',
        help=(
            'Specify custom args for the test runners. '
            'Everything after -- will be consumed as '
            'custom args.'
        ),
    )

  def get_args(self):
    """This method is to get args from actions and return optional args.

    Returns:
        A list of optional arguments.
    """
    argument_list = []
    # The output of _get_optional_actions(): [['-t', '--test']]
    # return an argument list: ['-t', '--test']
    for arg in self._get_optional_actions():
      argument_list.extend(arg.option_strings)
    return argument_list


HELP_DESC = """NAME
        atest - A command line tool that allows users to build, install, and run Android tests locally, greatly speeding test re-runs without requiring knowledge of Trade Federation test harness command line options.


SYNOPSIS
        atest [OPTION]... [TEST_TARGET]... -- [CUSTOM_ARGS]...


OPTIONS
        Below arguments are catagorised by features and purposes. Arguments marked with implicit default will apply even the user does not pass it explicitly.

        *NOTE* Atest reads ~/.atest/config that supports all optional arguments to help users reduce repeating options they often use.
        E.g. Assume "--all-abi" and "--verbose" are frequently used and have been defined line-by-line in ~/.atest/config, issuing

            atest hello_world_test -v -- --test-arg xxx

        is equivalent to

            atest hello_world_test -v --all-abi --verbose -- --test-arg xxx

        If only need to run tests for a specific abi, please use:
            atest <test> -- --abi arm64-v8a   # ARM 64-bit
            atest <test> -- --abi armeabi-v7a # ARM 32-bit

        Also, to avoid confusing Atest from testing TEST_MAPPING file and implicit test names from ~/.atest/config, any test names defined in the config file
        will be ignored without any hints.


EXAMPLES
    - - - - - - - - -
    IDENTIFYING TESTS
    - - - - - - - - -

    The positional argument <tests> should be a reference to one or more of the tests you'd like to run. Multiple tests can be run in one command by separating test references with spaces.

    Usage template: atest <reference_to_test_1> <reference_to_test_2>

    A <reference_to_test> can be satisfied by the test's MODULE NAME, MODULE:CLASS, CLASS NAME, TF INTEGRATION TEST, FILE PATH or PACKAGE NAME. Explanations and examples of each follow.


    < MODULE NAME >

        Identifying a test by its module name will run the entire module. Input the name as it appears in the LOCAL_MODULE or LOCAL_PACKAGE_NAME variables in that test's Android.mk or Android.bp file.

        Note: Use < TF INTEGRATION TEST > to run non-module tests integrated directly into TradeFed.

        Examples:
            atest FrameworksServicesTests
            atest CtsJankDeviceTestCases


    < MODULE:CLASS >

        Identifying a test by its class name will run just the tests in that class and not the whole module. MODULE:CLASS is the preferred way to run a single class. MODULE is the same as described above. CLASS is the name of the test class in the .java file. It can either be the fully qualified class name or just the basic name.

        Examples:
            atest FrameworksServicesTests:ScreenDecorWindowTests
            atest FrameworksServicesTests:com.android.server.wm.ScreenDecorWindowTests
            atest CtsJankDeviceTestCases:CtsDeviceJankUi


    < CLASS NAME >

        A single class can also be run by referencing the class name without the module name.

        Examples:
            atest ScreenDecorWindowTests
            atest CtsDeviceJankUi

        However, this will take more time than the equivalent MODULE:CLASS reference, so we suggest using a MODULE:CLASS reference whenever possible. Examples below are ordered by performance from the fastest to the slowest:

        Examples:
            atest FrameworksServicesTests:com.android.server.wm.ScreenDecorWindowTests
            atest FrameworksServicesTests:ScreenDecorWindowTests
            atest ScreenDecorWindowTests

    < TF INTEGRATION TEST >

        To run tests that are integrated directly into TradeFed (non-modules), input the name as it appears in the output of the "tradefed.sh list configs" cmd.

        Examples:
           atest example/reboot
           atest native-benchmark


    < FILE PATH >

        Both module-based tests and integration-based tests can be run by inputting the path to their test file or dir as appropriate. A single class can also be run by inputting the path to the class's java file.

        Both relative and absolute paths are supported.

        Example - 2 ways to run the `CtsJankDeviceTestCases` module via path:
        1. run module from android <repo root>:
            atest cts/tests/jank/jank

        2. from <android root>/cts/tests/jank:
            atest .

        Example - run a specific class within CtsJankDeviceTestCases module from <android repo> root via path:
           atest cts/tests/jank/src/android/jank/cts/ui/CtsDeviceJankUi.java

        Example - run an integration test from <android repo> root via path:
           atest tools/tradefederation/contrib/res/config/example/reboot.xml


    < PACKAGE NAME >

        Atest supports searching tests from package name as well.

        Examples:
           atest com.android.server.wm
           atest android.jank.cts


    - - - - - - - - - - - - - - - - - - - - - - - - - -
    SPECIFYING INDIVIDUAL STEPS: BUILD, INSTALL OR RUN
    - - - - - - - - - - - - - - - - - - - - - - - - - -

    The -b, -i and -t options allow you to specify which steps you want to run. If none of those options are given, then all steps are run. If any of these options are provided then only the listed steps are run.

    Note: -i alone is not currently support and can only be included with -t.
    Both -b and -t can be run alone.

    Examples:
        atest -b <test>    (just build targets)
        atest -t <test>    (run tests only)
        atest -it <test>   (install apk and run tests)
        atest -bt <test>   (build targets, run tests, but skip installing apk)


    Atest now has the ability to force a test to skip its cleanup/teardown step. Many tests, e.g. CTS, cleanup the device after the test is run, so trying to rerun your test with -t will fail without having the --disable-teardown parameter. Use -d before -t to skip the test clean up step and test iteratively.

        atest -d <test>    (disable installing apk and cleanning up device)
        atest -t <test>

    Note that -t disables both setup/install and teardown/cleanup of the device. So you can continue to rerun your test with just

        atest -t <test>

    as many times as you want.


    - - - - - - - - - - - - -
    RUNNING SPECIFIC METHODS
    - - - - - - - - - - - - -

    It is possible to run only specific methods within a test class. To run only specific methods, identify the class in any of the ways supported for identifying a class (MODULE:CLASS, FILE PATH, etc) and then append the name of the method or method using the following template:

      <reference_to_class>#<method1>

    Multiple methods can be specified with commas:

      <reference_to_class>#<method1>,<method2>,<method3>...

    Examples:
      atest com.android.server.wm.ScreenDecorWindowTests#testMultipleDecors

      atest FrameworksServicesTests:ScreenDecorWindowTests#testFlagChange,testRemoval


    - - - - - - - - - - - - -
    RUNNING MULTIPLE CLASSES
    - - - - - - - - - - - - -

    To run multiple classes, deliminate them with spaces just like you would when running multiple tests.  Atest will handle building and running classes in the most efficient way possible, so specifying a subset of classes in a module will improve performance over running the whole module.


    Examples:
    - two classes in same module:
      atest FrameworksServicesTests:ScreenDecorWindowTests FrameworksServicesTests:DimmerTests

    - two classes, different modules:
      atest FrameworksServicesTests:ScreenDecorWindowTests CtsJankDeviceTestCases:CtsDeviceJankUi


    - - - - - - - - - - -
    RUNNING NATIVE TESTS
    - - - - - - - - - - -

    Atest can run native test.

    Example:
    - Input tests:
      atest -a libinput_tests inputflinger_tests

    Use -a|--all-abi to run the tests for all available device architectures, which in this example is armeabi-v7a (ARM 32-bit) and arm64-v8a (ARM 64-bit).

    To select a specific native test to run, use colon (:) to specify the test name and hashtag (#) to further specify an individual method. For example, for the following test definition:

        TEST_F(InputDispatcherTest, InjectInputEvent_ValidatesKeyEvents)

    You can run the entire test using:

        atest inputflinger_tests:InputDispatcherTest

    or an individual test method using:

        atest inputflinger_tests:InputDispatcherTest#InjectInputEvent_ValidatesKeyEvents


    - - - - - - - - - - - - - -
    RUNNING TESTS IN ITERATION
    - - - - - - - - - - - - - -

    To run tests in iterations, simply pass --iterations argument. No matter pass or fail, atest won't stop testing until the max iteration is reached.

    Example:
        atest <test> --iterations    # 10 iterations(by default).
        atest <test> --iterations 5  # run <test> 5 times.

    Two approaches that assist users to detect flaky tests:

    1) Run all tests until a failure occurs or the max iteration is reached.

    Example:
        - 10 iterations(by default).
        atest <test> --rerun-until-failure
        - stop when failed or reached the 20th run.
        atest <test> --rerun-until-failure 20

    2) Run failed tests until passed or the max iteration is reached.

    Example:
        - 10 iterations(by default).
        atest <test> --retry-any-failure
        - stop when passed or reached the 20th run.
        atest <test> --retry-any-failure 20


    - - - - - - - - - - - -
    RUNNING TESTS ON AVD(s)
    - - - - - - - - - - - -

    Atest is able to run tests with the newly created AVD. Atest can build and 'acloud create' simultanously, and run tests after the AVD has been created successfully.

    Examples:
    - Start an AVD before running tests on that newly created device.

        acloud create && atest <test>

    can be simplified by:

        atest <test> --start-avd

    - Start AVD(s) by specifing 'acloud create' arguments and run tests on that newly created device.

        atest <test> --acloud-create "--build-id 6509363 --build-target aosp_cf_x86_phone-userdebug --branch aosp_master"

    To know detail about the argument, please run 'acloud create --help'.

    [WARNING]
    * --acloud-create must be the LAST optional argument: the remainder args will be consumed as its positional args.
    * --acloud-create/--start-avd do not delete newly created AVDs. The users will be deleting them manually.


    - - - - - - - - - - - -
    TESTS IN TEST MAPPING
    - - - - - - - - - - - -

    Atest can run tests in TEST_MAPPING files:

    1) Run presubmit tests in TEST_MAPPING files in current and parent
       directories. You can also specify a target directory.

    Example:
        atest  (run presubmit tests in TEST_MAPPING files and host unit tests in current and parent directories)
        atest --test-mapping </path/to/project>
               (run presubmit tests in TEST_MAPPING files in </path/to/project> and its parent directories)

    2) Run a specified test group in TEST_MAPPING files.

    Example:
        atest :postsubmit
              (run postsubmit tests in TEST_MAPPING files in current and parent directories)
        atest :all
              (Run tests from all groups in TEST_MAPPING files)
        atest --test-mapping </path/to/project>:postsubmit
              (run postsubmit tests in TEST_MAPPING files in </path/to/project> and its parent directories)
        atest --test-mapping </path/to/project>:mainline-presubmit
              (run mainline tests in TEST_MAPPING files in </path/to/project> and its parent directories)

    3) Run tests in TEST_MAPPING files including sub directories

    By default, atest will only search for tests in TEST_MAPPING files in current (or given directory) and its parent directories. If you want to run tests in TEST_MAPPING files in the sub-directories, you can use option --include-subdirs to force atest to include those tests too.

    Example:
        atest --include-subdirs [optional </path/to/project>:<test_group_name>]
              (run presubmit tests in TEST_MAPPING files in current, sub and parent directories)
    A path can be provided optionally if you want to search for tests in a given directory, with optional test group name. By default, the test group is presubmit.


    - - - - - - - - - - - - - -
    ADDITIONAL ARGS TO TRADEFED
    - - - - - - - - - - - - - -

    When trying to pass custom arguments for the test runners, everything after '--'
    will be consumed as custom args.

    Example:
        atest -v <test> -- <custom_args1> <custom_args2>

    Examples of passing options to the modules:
        atest <test> -- --module-arg <module-name>:<option-name>:<option-value>
        atest GtsPermissionTestCases -- --module-arg GtsPermissionTestCases:ignore-business-logic-failure:true

    Examples of passing options to the runner type or class:
        atest <test> -- --test-arg <test-class>:<option-name>:<option-value>
        atest CtsVideoTestCases -- --test-arg com.android.tradefed.testtype.JarHosttest:collect-tests-only:true


                                                     2022-03-25
"""
