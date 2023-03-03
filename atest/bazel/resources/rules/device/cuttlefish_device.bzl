# Copyright (C) 2021 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Rule used to generate a Cuttlefish device environment.

This rule creates a device environment rule to run tests on a Cuttlefish Android
Virtual Device. Test targets that run in this environment will start a new
dedicated virtual device for each execution.

Device properties such as the image used can be configured via an attribute.
"""

load("//bazel/rules:platform_transitions.bzl", "host_transition")
load("//bazel/rules:device_test.bzl", "DeviceEnvironment")
load(
    "//:constants.bzl",
    "adb_label",
)

_BAZEL_WORK_DIR = "${TEST_SRCDIR}/${TEST_WORKSPACE}/"

def _cuttlefish_device_impl(ctx):
    img_dir = ctx.file.image.dirname
    path_additions = [_BAZEL_WORK_DIR + ctx.file._adb.dirname]

    ctx.actions.expand_template(
        template = ctx.file._create_script_template,
        output = ctx.outputs.out,
        is_executable = True,
        substitutions = {
            "{img_path}": _BAZEL_WORK_DIR + ctx.file.image.short_path,
            "{cvd_host_package_path}": _BAZEL_WORK_DIR + ctx.file.cvd_host_package.short_path,
            "{path_additions}": ":".join(path_additions),
        },
    )

    return DeviceEnvironment(
        runner = depset([ctx.outputs.out]),
        data = ctx.runfiles(files = [
            ctx.file.cvd_host_package,
            ctx.outputs.out,
            ctx.file.image,
        ]),
    )

cuttlefish_device = rule(
    attrs = {
        "image": attr.label(
            allow_single_file = True,
        ),
        "out": attr.output(mandatory = True),
        "cvd_host_package": attr.label(
            allow_single_file = True,
        ),
        "_create_script_template": attr.label(
            default = "//bazel/rules/device:create_cuttlefish.sh.template",
            allow_single_file = True,
        ),
        # This attribute is required to use Starlark transitions. It allows
        # allowlisting usage of this rule. For more information, see
        # https://docs.bazel.build/versions/master/skylark/config.html#user-defined-transitions
        "_allowlist_function_transition": attr.label(
            default = "@bazel_tools//tools/allowlists/function_transition_allowlist",
        ),
        "_adb": attr.label(
            default = adb_label,
            allow_single_file = True,
            cfg = host_transition,
        ),
    },
    implementation = _cuttlefish_device_impl,
)
