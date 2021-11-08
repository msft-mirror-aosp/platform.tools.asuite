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

"""Rule used to import artifacts prebuilt by Soong into the Bazel workspace.

The rule returns a DefaultInfo provider with all artifacts and runtime dependencies,
and a SoongPrebuiltInfo provider with the original Soong module name and artifacts.
"""

SoongPrebuiltInfo = provider(
    doc = "Info about a prebuilt Soong build module",
    fields = {
        "files": "Files imported from Soong outputs",
        "module_name": "Name of the original Soong build module",
    },
)

def _soong_prebuilt_impl(ctx):
    return [
        SoongPrebuiltInfo(
            files = depset(ctx.files.files),
            module_name = ctx.attr.module_name,
        ),
        DefaultInfo(
            files = depset(ctx.files.files),
            runfiles = ctx.runfiles(files = ctx.files.runtime_deps),
        ),
    ]

soong_prebuilt = rule(
    attrs = {
        "module_name": attr.string(),
        # Artifacts prebuilt by Soong.
        "files": attr.label_list(allow_files = True),
        # Targets that are needed by this target during runtime.
        "runtime_deps": attr.label_list(),
        # Build setting used to select artifacts.
        "_platform_flavor": attr.label(default = "//bazel/rules:platform_flavor"),
    },
    implementation = _soong_prebuilt_impl,
    doc = "A rule that imports artifacts prebuilt by Soong into the Bazel workspace",
)
