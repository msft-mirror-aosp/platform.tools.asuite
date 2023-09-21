# Copyright 2017, The Android Open Source Project
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

"""
Various globals used by atest.
"""

# pylint: disable=line-too-long

import os
import re
from collections import namedtuple

MODE = 'DEFAULT'

# Result server constants for atest_utils.
RESULT_SERVER = ''
RESULT_SERVER_ARGS = []
RESULT_SERVER_TIMEOUT = 5
# Result arguments if tests are configured in TEST_MAPPING.
TEST_MAPPING_RESULT_SERVER_ARGS = []

# Google service key for gts tests.
GTS_GOOGLE_SERVICE_ACCOUNT = ''

# Arg constants.
WAIT_FOR_DEBUGGER = 'WAIT_FOR_DEBUGGER'
DISABLE_INSTALL = 'DISABLE_INSTALL'
DISABLE_TEARDOWN = 'DISABLE_TEARDOWN'
SERIAL = 'SERIAL'
SHARDING = 'SHARDING'
ALL_ABI = 'ALL_ABI'
HOST = 'HOST'
DEVICE_ONLY = 'DEVICE_ONLY'
CUSTOM_ARGS = 'CUSTOM_ARGS'
DRY_RUN = 'DRY_RUN'
ANDROID_SERIAL = 'ANDROID_SERIAL'
INSTANT = 'INSTANT'
USER_TYPE = 'USER_TYPE'
ITERATIONS = 'ITERATIONS'
RERUN_UNTIL_FAILURE = 'RERUN_UNTIL_FAILURE'
RETRY_ANY_FAILURE = 'RETRY_ANY_FAILURE'
TF_DEBUG = 'TF_DEBUG'
DEFAULT_DEBUG_PORT = '10888'
COLLECT_TESTS_ONLY = 'COLLECT_TESTS_ONLY'
TF_TEMPLATE = 'TF_TEMPLATE'
FLAKES_INFO = 'FLAKES_INFO'
TF_EARLY_DEVICE_RELEASE = 'TF_EARLY_DEVICE_RELEASE'
BAZEL_MODE_FEATURES = 'BAZEL_MODE_FEATURES'
REQUEST_UPLOAD_RESULT = 'REQUEST_UPLOAD_RESULT'
DISABLE_UPLOAD_RESULT = 'DISABLE_UPLOAD_RESULT'
MODULES_IN = 'MODULES-IN-'
VERIFY_ENV_VARIABLE = 'VERIFY_ENV_VARIABLE'
SKIP_VARS = [VERIFY_ENV_VARIABLE]
AGGREGATE_METRIC_FILTER_ARG = 'AGGREGATE_METRIC_FILTER'
ENABLE_DEVICE_PREPARER = 'ENABLE_DEVICE_PREPARER'
ANNOTATION_FILTER = 'ANNOTATION_FILTER'
BAZEL_ARG = 'BAZEL_ARG'
COVERAGE = 'COVERAGE'
TEST_FILTER = 'TEST_FILTER'
TEST_TIMEOUT = 'TEST_TIMEOUT'
VERBOSE = 'VERBOSE'
LD_LIBRARY_PATH = 'LD_LIBRARY_PATH'

# Robolectric Types:
ROBOTYPE_MODERN = 1
ROBOTYPE_LEGACY = 2

# Codes of specific events. These are exceptions that don't stop anything
# but sending metrics.
ACCESS_CACHE_FAILURE = 101
ACCESS_HISTORY_FAILURE = 102
IMPORT_FAILURE = 103
PLOCATEDB_LOCKED = 104

# Test finder constants.
MODULE_CONFIG = 'AndroidTest.xml'
MODULE_COMPATIBILITY_SUITES = 'compatibility_suites'
MODULE_NAME = 'module_name'
MODULE_PATH = 'path'
MODULE_CLASS = 'class'
MODULE_AUTO_TEST_CONFIG = 'auto_test_config'
MODULE_INSTALLED = 'installed'
MODULE_CLASS_ROBOLECTRIC = 'ROBOLECTRIC'
MODULE_CLASS_NATIVE_TESTS = 'NATIVE_TESTS'
MODULE_CLASS_JAVA_LIBRARIES = 'JAVA_LIBRARIES'
MODULE_TEST_CONFIG = 'test_config'
MODULE_MAINLINE_MODULES = 'test_mainline_modules'
MODULE_DEPENDENCIES = 'dependencies'
MODULE_SRCS = 'srcs'
MODULE_IS_UNIT_TEST = 'is_unit_test'
MODULE_SHARED_LIBS = 'shared_libs'
MODULE_RUNTIME_DEPS = 'runtime_dependencies'
MODULE_STATIC_DEPS = 'static_dependencies'
MODULE_DATA_DEPS = 'data_dependencies'
MODULE_SUPPORTED_VARIANTS = 'supported_variants'
MODULE_LIBS = 'libs'
MODULE_STATIC_LIBS = 'static_libs'
MODULE_HOST_DEPS = 'host_dependencies'
MODULE_TARGET_DEPS = 'target_dependencies'
MODULE_TEST_OPTIONS_TAGS = 'test_options_tags'
MODULE_INFO_ID = 'module_info_id'


# Env constants
ANDROID_BUILD_TOP = 'ANDROID_BUILD_TOP'
ANDROID_OUT = 'OUT'
ANDROID_OUT_DIR = 'OUT_DIR'
ANDROID_OUT_DIR_COMMON_BASE = 'OUT_DIR_COMMON_BASE'
ANDROID_HOST_OUT = 'ANDROID_HOST_OUT'
ANDROID_PRODUCT_OUT = 'ANDROID_PRODUCT_OUT'
ANDROID_TARGET_PRODUCT = 'TARGET_PRODUCT'
TARGET_BUILD_VARIANT = 'TARGET_BUILD_VARIANT'
ANDROID_TARGET_OUT_TESTCASES = 'ANDROID_TARGET_OUT_TESTCASES'

# Test Info data keys
# Value of include-filter option.
TI_FILTER = 'filter'
TI_REL_CONFIG = 'rel_config'
TI_MODULE_CLASS = 'module_class'
# Value of module-arg option
TI_MODULE_ARG = 'module-arg'

# Google TF
GTF_MODULE = 'google-tradefed'
GTF_TARGET = 'google-tradefed-core'
# Defines the TF build targets which only exist in internal branches.
# TODO(b/283364305) Have a flag and use the setup in vendor to define the flag.
GTF_TARGETS = set()

# TEST_MAPPING filename
TEST_MAPPING = 'TEST_MAPPING'
# Test group for tests in TEST_MAPPING
TEST_GROUP_PRESUBMIT = 'presubmit'
TEST_GROUP_PRESUBMIT_LARGE = 'presubmit-large'
TEST_GROUP_POSTSUBMIT = 'postsubmit'
TEST_GROUP_ALL = 'all'
DEFAULT_TEST_GROUPS = [TEST_GROUP_PRESUBMIT,
                       TEST_GROUP_PRESUBMIT_LARGE]
# Key in TEST_MAPPING file for a list of imported TEST_MAPPING file
TEST_MAPPING_IMPORTS = 'imports'

# TradeFed command line args
TF_INCLUDE_FILTER_OPTION = 'include-filter'
TF_EXCLUDE_FILTER_OPTION = 'exclude-filter'
TF_INCLUDE_FILTER = '--include-filter'
TF_EXCLUDE_FILTER = '--exclude-filter'
TF_ATEST_INCLUDE_FILTER = '--atest-include-filter'
TF_ATEST_INCLUDE_FILTER_VALUE_FMT = '{test_name}:{test_filter}'
TF_MODULE_ARG = '--module-arg'
TF_MODULE_ARG_VALUE_FMT = '{test_name}:{option_name}:{option_value}'
TF_SUITE_FILTER_ARG_VALUE_FMT = '"{test_name} {option_value}"'
TF_SKIP_LOADING_CONFIG_JAR = '--skip-loading-config-jar'
TF_MODULE_FILTER = '--module'
TF_ENABLE_MAINLINE_PARAMETERIZED_MODULES = '--enable-mainline-parameterized-modules'
TF_ENABLE_PARAMETERIZED_MODULES = '--enable-parameterized-modules'
TF_MODULE_PARAMETER = '--module-parameter'

# Mobly constants
MOBLY_TEST_OPTIONS_TAG = 'mobly'

# Suite Plans
SUITE_PLANS = frozenset(['cts'])

# Constants of Steps
REBUILD_MODULE_INFO_FLAG = '--rebuild-module-info'
BUILD_STEP = 'build'
INSTALL_STEP = 'install'
TEST_STEP = 'test'
ALL_STEPS = [BUILD_STEP, INSTALL_STEP, TEST_STEP]

# ANSI code shift for colorful print
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

# Types of Levenshetine Distance Cost
COST_TYPO = (1, 1, 1)
COST_SEARCH = (8, 1, 5)
LD_RANGE = 2

# Value of TestInfo install_locations.
DEVICELESS_TEST = 'host'
DEVICE_TEST = 'device'
BOTH_TEST = 'both'

# Metrics
NO_METRICS_ARG = '--no-metrics'
METRICS_URL = 'http://asuite-218222.appspot.com/atest/metrics'
EXTERNAL = 'EXTERNAL_RUN'
INTERNAL = 'INTERNAL_RUN'
INTERNAL_EMAIL = '@google.com'
INTERNAL_HOSTNAME = ['.google.com', 'c.googlers.com']
TOOL_NAME = 'atest'
SUB_TOOL_NAME = ''
USER_FROM_TOOL = 'USER_FROM_TOOL'
USER_FROM_SUB_TOOL = 'USER_FROM_SUB_TOOL'
TF_PREPARATION = 'tf-preparation'

# Detect type for local_detect_event.
# XTS suite types encode from 100 to 199
DETECT_TYPE_XTS_SUITE = {'cts': 101,
                         'vts': 104}

# Considering a trade-off between speed and size, we set UPPER_LIMIT to 100000
# to make maximum file space 10M(100000(records)*100(byte/record)) at most.
# Therefore, to update history file will spend 1 sec at most in each run.
UPPER_LIMIT = 100000
TRIM_TO_SIZE = 50000

# VTS plans
VTS_STAGING_PLAN = 'vts-staging-default'

# TreeHugger TEST_MAPPING SUITE_PLANS
TEST_MAPPING_SUITES = ['device-tests', 'general-tests']

# VTS10 TF
VTS_TF_MODULE = 'vts10-tradefed'

# VTS TF
VTS_CORE_TF_MODULE = 'vts-tradefed'

# VTS suite set
VTS_CORE_SUITE = 'vts'

# MTS suite set
MTS_SUITE = 'mts'

# CTS tradefed jar
CTS_JAR = "cts-tradefed"

# ATest TF
ATEST_TF_MODULE = 'atest-tradefed'

# Atest index path and relative dirs/caches.
INDEX_DIR = os.path.join(os.getenv(ANDROID_HOST_OUT, ''), 'indices')
LOCATE_CACHE = os.path.join(INDEX_DIR, 'plocate.db')
BUILDFILES_STP = os.path.join(INDEX_DIR, 'buildfiles.stp')
INT_INDEX = os.path.join(INDEX_DIR, 'integration.idx')
CLASS_INDEX = os.path.join(INDEX_DIR, 'classes.idx')
CC_CLASS_INDEX = os.path.join(INDEX_DIR, 'cc_classes.idx')
PACKAGE_INDEX = os.path.join(INDEX_DIR, 'packages.idx')
QCLASS_INDEX = os.path.join(INDEX_DIR, 'fqcn.idx')

# Regeular Expressions
CC_EXT_RE = re.compile(r'.*\.(cc|cpp)$')
JAVA_EXT_RE = re.compile(r'.*\.(java|kt)$')
# e.g. /path/to/ccfile.cc: TYPED_TEST_P(test_name, method_name){
CC_OUTPUT_RE = re.compile(
    r'(?P<file_path>/.*):\s*(TYPED_TEST(_P)*|TEST(_F|_P)*)\s*\('
    r'(?P<test_name>\w+)\s*,\s*(?P<method_name>\w+)\)\s*\{')
# Used by locate command.
CC_GREP_RE = r'^\s*(TYPED_TEST(_P)*|TEST(_F|_P)*)\s*\(\w+,'
# e.g. /path/to/Javafile.java:package com.android.settings.accessibility
# grab the path, Javafile(class) and com.android.settings.accessibility(package)
CLASS_OUTPUT_RE = re.compile(r'(?P<java_path>.*/(?P<class>[A-Z]\w+)\.\w+)[:].*')
QCLASS_OUTPUT_RE = re.compile(r'(?P<java_path>.*/(?P<class>[A-Z]\w+)\.\w+)'
                              r'[:]\s*package\s+(?P<package>[^(;|\s)]+)\s*')
PACKAGE_OUTPUT_RE = re.compile(r'(?P<java_dir>/.*/).*[.](java|kt)[:]\s*package\s+'
                               r'(?P<package>[^(;|\s)]+)\s*')

ATEST_RESULT_ROOT = '/tmp/atest_result'
ATEST_TEST_RECORD_PROTO = 'test_record.proto'
LATEST_RESULT_FILE = os.path.join(ATEST_RESULT_ROOT, 'LATEST', 'test_result')
TEST_WITH_MAINLINE_MODULES_RE = re.compile(r'(?P<test>.*)\[(?P<mainline_modules>.*'
                                           r'[.](apk|apks|apex))\]$')

# Tests list which need vts_ltp_tests as test dependency
REQUIRED_LTP_TEST_MODULES = [
    'vts_ltp_test_arm',
    'vts_ltp_test_arm_64',
    'vts_ltp_test_arm_64_lowmem',
    'vts_ltp_test_arm_64_hwasan',
    'vts_ltp_test_arm_64_lowmem_hwasan',
    'vts_ltp_test_arm_lowmem',
    'vts_ltp_test_x86_64',
    'vts_ltp_test_x86'
]
# Tests list which need vts_kselftest_tests as test dependency
REQUIRED_KSELFTEST_TEST_MODULES = [
    'vts_linux_kselftest_arm_32',
    'vts_linux_kselftest_arm_64',
    'vts_linux_kselftest_x86_32',
    'vts_linux_kselftest_x86_64',
]

# XTS suite set dependency.
SUITE_DEPS = {}

# Tradefed log file name term.
TF_HOST_LOG = 'host_log_*'

# Flake service par path
FLAKE_SERVICE_PATH = '/foo'
FLAKE_TMP_PATH = '/tmp'
FLAKE_FILE = 'flakes_info.par'
FLAKE_TARGET = 'aosp_cf_x86_phone-userdebug'
FLAKE_BRANCH = 'aosp-master'
FLAKE_TEST_NAME = 'suite/test-mapping-presubmit-retry_cloud-tf'
FLAKE_PERCENT = 'flake_percent'
FLAKE_POSTSUBMIT = 'postsubmit_flakes_per_week'

# cert status command
CERT_STATUS_CMD = ''

ASUITE_REPO_PROJECT_NAME = 'platform/tools/asuite'

# logstorage api scope.
SCOPE_BUILD_API_SCOPE = ''
STORAGE_API_VERSION = ''
STORAGE_SERVICE_NAME = ''
DO_NOT_UPLOAD = 'DO_NOT_UPLOAD'
CLIENT_ID = ''
CLIENT_SECRET = ''
CREDENTIAL_FILE_NAME = ''
TOKEN_FILE_PATH = ''
INVOCATION_ID = 'INVOCATION_ID'
WORKUNIT_ID = 'WORKUNIT_ID'
LOCAL_BUILD_ID = 'LOCAL_BUILD_ID'
BUILD_TARGET = 'BUILD_TARGET'
RESULT_LINK = ''
TF_GLOBAL_CONFIG = ''
UPLOAD_TEST_RESULT_MSG = 'Upload test result?'
DISCOVERY_SERVICE = ''
STORAGE2_TEST_URI = ''

# SSO constants.
TOKEN_EXCHANGE_COMMAND = ''
TOKEN_EXCHANGE_REQUEST = ''
SCOPE = ''

# Example arguments used in ~/.atest/config
ATEST_EXAMPLE_ARGS = ('## Specify only one option per line; any test name/path will be ignored automatically.\n'
                      '## Option that follows a "#" will be ignored.\n'
                      'hello_world_test   # Test name will be skipped WITHOUT warning.\n'
                      '# -- --module-arg Foo:variable:value   # Only support atest arguments so "--" will be ignored.\n'
                      '                                       # and will stop running tests.\n'
                      '# --iterations=3\n'
                      '# --retry-any-failure=5\n'
                      '# --rerun-until-failure=5\n'
                      '# --start-avd        # also run "acloud create" concurrently.\n'
                      '# --all-abi          # Set to run tests for all abis.\n'
                      '# --verbose          # turn on verbose mode for debugging.\n')

# AndroidJUnitTest related argument.
ANDROID_JUNIT_CLASS = 'com.android.tradefed.testtype.AndroidJUnitTest'
INCLUDE_ANNOTATION = 'include-annotation'
EXCLUDE_ANNOTATION = 'exclude-annotation'
SUPPORTED_FILTERS = [INCLUDE_ANNOTATION, EXCLUDE_ANNOTATION]

# Tradefed config-descriptor metadata.
CONFIG_DESCRIPTOR = 'config-descriptor:metadata'
PARAMETER_KEY = 'parameter'
MAINLINE_PARAM_KEY = 'mainline-param'

# Tradefed related constant.
TF_TEST_ARG = '--test-arg'
TF_AND_JUNIT_CLASS = 'com.android.tradefed.testtype.AndroidJUnitTest'
TF_EXCLUDE_ANNOTATE = 'exclude-annotation'
INSTANT_MODE_ANNOTATE = 'android.platform.test.annotations.AppModeInstant'
TF_PARA_INSTANT_APP = 'instant_app'
TF_PARA_SECOND_USR = 'secondary_user'
TF_PARA_MULTIABI = 'multi_abi'
DEFAULT_EXCLUDE_PARAS = {TF_PARA_INSTANT_APP,
                         TF_PARA_SECOND_USR,
                         TF_PARA_MULTIABI
                         }
DEFAULT_EXCLUDE_NOT_PARAS = {'not_' + TF_PARA_INSTANT_APP,
                            'not_' + TF_PARA_SECOND_USR,
                            'not_' + TF_PARA_MULTIABI}

# ATest integration test related constants.
VERIFY_DATA_PATH = os.path.join(
    os.environ.get(ANDROID_BUILD_TOP, os.getcwd()),
    'tools/asuite/atest/test_data/test_commands.json')
VERIFY_ENV_PATH = os.path.join(
    os.environ.get(ANDROID_BUILD_TOP, os.getcwd()),
    'tools/asuite/atest/test_data/test_environ.json')
RUNNER_COMMAND_PATH = os.path.join(
    os.environ.get(ANDROID_BUILD_TOP, os.getcwd()),
    'tools/asuite/atest/test_data/runner_commands.json')

# Tradefed log saver template for ATest
ATEST_TF_LOG_SAVER = 'template/log/atest_log_saver'
DEVICE_SETUP_PREPARER = 'template/preparers/device-preparer'
LOG_ROOT_OPTION_NAME = 'atest-log-file-path'
LOG_SAVER_EXT_OPTION = ''

# Tradefed log saver template for uploading logs to cloud storage.
GOOGLE_LOG_SAVER = ''
GOOGLE_LOG_SAVER_LOG_ROOT_OPTION_NAME = ''
GOOGLE_LOG_SAVER_EXT_OPTION = ''

# Log messages here.
REQUIRE_DEVICES_MSG = (
    'Please ensure there is at least one connected device via:\n'
    '    $ adb devices')

# Default shard num.
SHARD_NUM = 2

ROBOLEAF_TEST_FILTER = 'roboleaf_test_filter'

# Flags which roboleaf mode already supported:
#   --iterations, --rerun-until-failure, --retry-any-failure, --verbose,
#   --bazel-arg, --, --wait-for-debugger, --host
#
# Flags which roboleaf mode doesn't need to support:
#   --minimal-build, --bazel_mode, --null-feature, --experimental-remote-avd,
#   --experimental-device-driven-test, --experimental-java-runtime-dependencies,
#   --experimental-remote, --experimental-host-driven-test,
#   --experimental-robolectric-test, --no-bazel-detailed-summary,
#   --rebuild-module-info, --sqlite-module-cache
#
# A dict of flags which are unsupported by roboleaf mode. The key is the
# attribute name of flags. The value is a namedtuple of the function used to
# check whether the unsupported flag is specified and the roboleaf mode should
# be disabled, and the unsupported reason. The function takes two arguments,
# default flag value and exact flag value.

UnsupportedFlag = namedtuple('UnsupportedFlag', ['is_unsupported_func', 'reason'])
ROBOLEAF_UNSUPPORTED_FLAGS = {
    'steps': UnsupportedFlag(
        lambda _, v: v is not None,
        "Bazel builds the minimum required deps, and keeps the "
        "build up-to-date, so it is unnecessary to specify steps to avoid the build. "
        "Remove this flag."
    ),
    'auto_sharding': UnsupportedFlag(lambda d, v: d != v, ""),
    'all_abi': UnsupportedFlag(
        lambda d, v: d != v,
        "Bazel will run tests for the current target product's ABI. Remove this flag."),
    'disable_teardown': UnsupportedFlag(lambda d, v: d != v, ""),
    'enable_device_preparer': UnsupportedFlag(lambda d, v: d != v, ""),
    'experimental_coverage': UnsupportedFlag(lambda d, v: d != v, ""),
    'test_mapping': UnsupportedFlag(lambda d, v: d != v, ""),
    'device_only': UnsupportedFlag(lambda d, v: d != v, ""),
    'sharding': UnsupportedFlag(lambda d, v: d != v, ""),
    'use_modules_in': UnsupportedFlag(lambda d, v: d != v, ""),
    'auto_ld_library_path': UnsupportedFlag(lambda d, v: d != v, ""),
    'request_upload_result': UnsupportedFlag(lambda d, v: d != v, ""),
    'disable_upload_result': UnsupportedFlag(lambda d, v: d != v, ""),
    'smart_testing_local': UnsupportedFlag(lambda d, v: d != v, ""),
    'include_subdirs': UnsupportedFlag(lambda d, v: d != v, ""),
    'enable_file_patterns': UnsupportedFlag(lambda d, v: d != v, ""),
    'host_unit_test_only': UnsupportedFlag(lambda d, v: d != v, ""),
    'collect_tests_only': UnsupportedFlag(lambda d, v: d != v, ""),
    'dry_run': UnsupportedFlag(lambda d, v: d != v, "Roboleaf mode/Bazel will not support dry-run."),
    'info': UnsupportedFlag(lambda d, v: d != v, ""),
    'list_modules': UnsupportedFlag(lambda d, v: d != v, ""),
    'version': UnsupportedFlag(lambda d, v: d != v, ""),
    'help': UnsupportedFlag(lambda d, v: d != v, ""),
    'build_output': UnsupportedFlag(lambda d, v: d != v, ""),
    'acloud_create': UnsupportedFlag(lambda d, v: d != v, ""),
    'start_avd': UnsupportedFlag(lambda d, v: d != v, ""),
    'serial': UnsupportedFlag(lambda d, v: d != v, ""),
    'flakes_info': UnsupportedFlag(lambda d, v: d != v, ""),
    'tf_early_device_release': UnsupportedFlag(lambda d, v: d != v, ""),
    'test_config_select': UnsupportedFlag(lambda d, v: d != v, ""),
    'generate_baseline': UnsupportedFlag(lambda d, v: d != v, ""),
    'generate_new_metrics': UnsupportedFlag(lambda d, v: d != v, ""),
    'detect_regression': UnsupportedFlag(lambda d, v: d != v, ""),
    'instant': UnsupportedFlag(lambda d, v: d != v, ""),
    'user_type': UnsupportedFlag(lambda d, v: d != v, ""),
    'annotation_filter': UnsupportedFlag(lambda d, v: d != v, ""),
    'clear_cache': UnsupportedFlag(
        lambda d, v: d != v,
        "Bazel will always keep the build outputs up-to-date. "
        "To invalidate cached test results, pass --bazel-arg=--nocache_test_results instead."
    ),
    'update_cmd_mapping': UnsupportedFlag(lambda d, v: d != v, ""),
    'verify_cmd_mapping': UnsupportedFlag(lambda d, v: d != v, ""),
    'verify_env_variable': UnsupportedFlag(lambda d, v: d != v, ""),
    'generate_runner_cmd': UnsupportedFlag(lambda d, v: d != v, ""),
    'tf_debug': UnsupportedFlag(lambda d, v: d != v, ""),
    'tf_template': UnsupportedFlag(lambda d, v: d != v, ""),
    'test_filter': UnsupportedFlag(lambda d, v: d != v, ""),
    'test_timeout': UnsupportedFlag(lambda d, v: d != v, ""),
    'latest_result': UnsupportedFlag(lambda d, v: d != v, ""),
    'history': UnsupportedFlag(lambda d, v: d != v, ""),
    'no_metrics': UnsupportedFlag(lambda d, v: d != v, ""),
    'aggregate_metric_filter': UnsupportedFlag(lambda d, v: d != v, ""),
    'no_checking_device': UnsupportedFlag(lambda d, v: d != v, ""),
}
