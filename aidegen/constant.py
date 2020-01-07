#!/usr/bin/env python3
#
# Copyright 2018 - The Android Open Source Project
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
"""The common definitions of AIDEgen"""

# Env constant
OUT_DIR_COMMON_BASE_ENV_VAR = 'OUT_DIR_COMMON_BASE'
ANDROID_DEFAULT_OUT = 'out'
AIDEGEN_ROOT_PATH = 'tools/asuite/aidegen'
USER_HOME = '$USER_HOME$'

# Constants for module's info.
KEY_PATH = 'path'
KEY_DEPENDENCIES = 'dependencies'
KEY_DEPTH = 'depth'
KEY_CLASS = 'class'
KEY_INSTALLED = 'installed'
KEY_SRCS = 'srcs'
KEY_SRCJARS = 'srcjars'
KEY_CLASSES_JAR = 'classes_jar'
KEY_TAG = 'tags'
KEY_COMPATIBILITY = 'compatibility_suites'
KEY_AUTO_TEST_CONFIG = 'auto_test_config'
KEY_MODULE_NAME = 'module_name'
KEY_TEST_CONFIG = 'test_config'
# Java related classes.
JAVA_TARGET_CLASSES = ['APPS', 'JAVA_LIBRARIES', 'ROBOLECTRIC']
# C, C++ related classes.
NATIVE_TARGET_CLASSES = [
    'HEADER_LIBRARIES', 'NATIVE_TESTS', 'STATIC_LIBRARIES', 'SHARED_LIBRARIES'
]
TARGET_CLASSES = JAVA_TARGET_CLASSES
TARGET_CLASSES.extend(NATIVE_TARGET_CLASSES)

# Constants for IDE util.
IDE_ECLIPSE = 'Eclipse'
IDE_INTELLIJ = 'IntelliJ'
IDE_ANDROID_STUDIO = 'Android Studio'
IDE_CLION = 'CLion'
IDE_NAME_DICT = {
    'j': IDE_INTELLIJ,
    's': IDE_ANDROID_STUDIO,
    'e': IDE_ECLIPSE,
    'c': IDE_CLION
}

# Constants for asuite metrics
EXIT_CODE_EXCEPTION = -1
EXIT_CODE_NORMAL = 0
EXIT_CODE_AIDEGEN_EXCEPTION = 1
AIDEGEN_TOOL_NAME = 'aidegen'
ANDROID_TREE = 'is_android_tree'

# Exit code of the asuite metrics for parsing xml file failed.
XML_PARSING_FAILURE = 101

# Exit code of the asuite metrics for locating Android SDK path failed.
LOCATE_SDK_PATH_FAILURE = 102

# Exit code of the asuite metrics for IDE launched failed.
IDE_LAUNCH_FAILURE = 103

# Constants for file names
MERGED_MODULE_INFO = 'merged_module_info.json'
BLUEPRINT_JAVA_JSONFILE_NAME = 'module_bp_java_deps.json'
BLUEPRINT_CC_JSONFILE_NAME = 'module_bp_cc_deps.json'
CMAKELISTS_FILE_NAME = 'clion_project_lists.txt'
CLION_PROJECT_FILE_NAME = 'CMakeLists.txt'
ANDROID_BP = 'Android.bp'
ANDROID_MK = 'Android.mk'

# Constants for whole Android tree
WHOLE_ANDROID_TREE_TARGET = '#WHOLE_ANDROID_TREE#'

# Constants for ProjectInfo or ModuleData classes
JAR_EXT = '.jar'
TARGET_LIBS = [JAR_EXT]

# Constants for aidegen_functional_test
ANDROID_COMMON = 'android_common'
LINUX_GLIBC_COMMON = 'linux_glibc_common'

# Constants for ide_util
NOHUP = 'nohup'
ECLIPSE_WS = '~/Documents/AIDEGen_Eclipse_workspace'
IGNORE_STD_OUT_ERR_CMD = '2>/dev/null >&2'
