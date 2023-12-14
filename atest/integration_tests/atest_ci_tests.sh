#!/usr/bin/env bash

# Copyright (C) 2023 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# A script to test the end-to-end flow of Atest on the Android CI.

set -eo pipefail
set -x

function get_build_var()
{
  (${PWD}/build/soong/soong_ui.bash --dumpvar-mode --abs $1)
}

if [ ! -n "${ANDROID_BUILD_TOP}" ] ; then
  export ANDROID_BUILD_TOP=${PWD}
fi

product_out=$(get_build_var PRODUCT_OUT)
out_dir=$(get_build_var OUT_DIR)

# ANDROID_BUILD_TOP is deprecated, so don't use it throughout the script.
# But if someone sets it, we'll respect it.
cd ${ANDROID_BUILD_TOP:-.}

export \
  ANDROID_PRODUCT_OUT=${product_out} \
  OUT=${product_out} \
  ANDROID_HOST_OUT=$(get_build_var HOST_OUT) \
  ANDROID_TARGET_OUT_TESTCASES=$(get_build_var TARGET_OUT_TESTCASES) \
  REMOTE_AVD=true \

build/soong/soong_ui.bash --make-mode atest --skip-soong-tests

# Use the versioned Python binaries in prebuilts/ for a reproducible
# build with minimal reliance on host tools. Add build/bazel/bin to PATH since
# atest needs 'b'
export PATH=${PWD}/prebuilts/build-tools/path/linux-x86:${PWD}/build/bazel/bin:${out_dir}/host/linux-x86/bin/:${PATH}

python3 tools/asuite/atest/integration_tests/atest_ci_tests.py $@