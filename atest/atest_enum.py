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

"""
Atest custom enum class.
"""

from enum import IntEnum, unique, Enum

@unique
class DetectType(IntEnum):
    """An Enum class for local_detect_event."""
    # Detect type for local_detect_event; next expansion: 26
    BUG_DETECTED = 0
    ACLOUD_CREATE = 1
    FIND_BUILD = 2
    NO_FLAKE = 3
    HAS_FLAKE = 4
    TF_TEARDOWN_LOGCAT = 5
    REBUILD_MODULE_INFO = 6
    NOT_REBUILD_MODULE_INFO = 7
    ONLY_BUILD_MODULE_INFO = 8
    FUZZY_SEARCH_TIME = 9
    PERMISSION_INCONSISTENT = 10
    SMART_REBUILD_MODULE_INFO = 11
    CLEAN_BUILD = 12
    TESTABLE_MODULES = 13
    # Tradefed exit codes v.s. exit conditions
    # 0: NO_ERROR             1: CONFIG_EXCEPTION
    # 2: NO_BUILD             3: DEVICE_UNRESPONSIVE
    # 4: DEVICE_UNAVAILABLE   5: FATAL_HOST_ERROR
    # 6: THROWABLE_EXCEPTION  7: NO_DEVICE_ALLOCATED
    # 8: WRONG_JAVA_VERSION
    TF_EXIT_CODE = 14
    ATEST_CONFIG = 15
    TEST_WITH_ARGS = 16
    TEST_NULL_ARGS = 17
    MODULE_MERGE = 18          # Deprecated. Use MODULE_MERGE_MS instead.
    MODULE_INFO_INIT_TIME = 19 # Deprecated. Use MODULE_INFO_INIT_MS instead.
    MODULE_MERGE_MS = 20
    NATIVE_TEST_NOT_FOUND = 21
    BAZEL_WORKSPACE_GENERATE_TIME = 22
    MODULE_LOAD_MS = 23
    MODULE_INFO_INIT_MS = 24
    INIT_AND_FIND_MS = 25
    FOUND_INSTRUMENTATION_TEST = 26
    FOUND_TARGET_ARTIFACTS = 27

@unique
class ExitCode(IntEnum):
    """An Enum class for sys.exit()"""
    SUCCESS = 0
    ENV_NOT_SETUP = 1
    BUILD_FAILURE = 2
    ERROR = 3
    TEST_NOT_FOUND = 4
    TEST_FAILURE = 5
    VERIFY_FAILURE = 6
    OUTSIDE_ROOT = 7
    AVD_CREATE_FAILURE = 8
    AVD_INVALID_ARGS = 9
    EXIT_BEFORE_MAIN = 10
    DEVICE_NOT_FOUND = 11
    MIXED_TYPE_FILTER = 12
    INPUT_TEST_REFERENCE_ERROR = 13
    CONFIG_INVALID_FORMAT = 14
    # The code > 100 are reserved for collecting data only, actually the run
    # doesn't finish at the point.
    COLLECT_ONLY_FILE_NOT_FOUND = 101

@unique
class FilterType(Enum):
    """An Enum class for filter types"""
    WILDCARD_FILTER = 'wildcard class_method'
    REGULAR_FILTER = 'regular class_method'

# TODO: (b/218441706) Convert AtestEnum to a real Enum class.
class AtestEnum(tuple):
    """enum library isn't a Python 2.7 built-in, so roll our own."""
    __getattr__ = tuple.index
