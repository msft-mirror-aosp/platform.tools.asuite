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

import os

from atest import constants

ANDROID_HOST_OUT = os.environ.get(constants.ANDROID_HOST_OUT)
ANDROID_ROOT_PATH = os.environ.get(constants.ANDROID_BUILD_TOP)
ROOT_DIR = os.path.join(ANDROID_ROOT_PATH, 'tools/asuite/aidegen')
ANDROID_OUT_DIR = os.environ.get(constants.ANDROID_OUT_DIR)
ANDROID_OUT = os.path.join(ANDROID_ROOT_PATH, 'out')
OUT_DIR = ANDROID_OUT_DIR or ANDROID_OUT
BLUEPRINT_JSONFILE_OUTDIR = os.path.join(OUT_DIR, 'soong')
KEY_PATH = 'path'
KEY_DEP = 'dependencies'
KEY_DEPTH = 'depth'
RELATIVE_HOST_OUT = os.path.relpath(ANDROID_HOST_OUT, ANDROID_ROOT_PATH)
