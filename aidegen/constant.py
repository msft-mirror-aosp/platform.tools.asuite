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

# Constants for module's info.
KEY_PATH = 'path'
KEY_DEPENDENCIES = 'dependencies'
KEY_DEPTH = 'depth'
KEY_CLASS = 'class'
KEY_INSTALLED = 'installed'
KEY_SRCS = 'srcs'
KEY_SRCJARS = 'srcjars'
KEY_CLASSES_JAR = 'classes_jar'

# Constants for IDE util.
IDE_ECLIPSE = 'Eclipse'
IDE_INTELLIJ = 'IntelliJ'
IDE_ANDROID_STUDIO = 'Android Studio'
IDE_NAME_DICT = {'j': IDE_INTELLIJ, 's': IDE_ANDROID_STUDIO, 'e': IDE_ECLIPSE}

# Constants for asuite metrics
EXIT_CODE_EXCEPTION = -1
EXIT_CODE_NORMAL = 0
EXIT_CODE_AIDEGEN_EXCEPTION = 1
AIDEGEN_TOOL_NAME = 'aidegen'
ANDROID_TREE = 'is_android_tree'

# Constants for file names
MERGED_MODULE_INFO = 'merged_module_info.json'
BLUEPRINT_JSONFILE_NAME = 'module_bp_java_deps.json'
