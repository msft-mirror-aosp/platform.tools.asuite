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

"""Rules used to run tests using Tradefed."""

load("//bazel/rules:platform_transitions.bzl", "host_transition")
load("//bazel/rules:tradefed_test_aspects.bzl", "soong_prebuilt_tradefed_test_aspect")
load("//bazel/rules:tradefed_test_info.bzl", "TradefedTestInfo")

_BAZEL_WORK_DIR = "${TEST_SRCDIR}/${TEST_WORKSPACE}/"

def _tradefed_deviceless_test_impl(ctx):
    tradefed_classpath = []
    for tradefed_classpath_jar in ctx.attr._tradefed_classpath_jars:
        for f in tradefed_classpath_jar.files.to_list():
            tradefed_classpath.append(_BAZEL_WORK_DIR + f.short_path)
    tradefed_classpath = ":".join(tradefed_classpath)

    all_deps = []
    all_deps.extend(ctx.attr.test)
    all_deps.extend(ctx.attr._tradefed_classpath_jars)
    all_deps.extend(ctx.attr._atest_tradefed_launcher)
    all_deps.extend(ctx.attr._atest_helper)
    all_deps.extend(ctx.attr._adb)

    runfiles = ctx.runfiles().merge_all([
        dep[DefaultInfo].default_runfiles for dep in all_deps
    ])

    shared_lib_dirs = []
    for f in runfiles.files.to_list():
        if f.extension == "so":
            shared_lib_dirs.append(_BAZEL_WORK_DIR + f.dirname)
    shared_lib_dirs = ":".join(shared_lib_dirs)

    script = ctx.actions.declare_file("tradefed_test_%s.sh" % ctx.label.name)
    ctx.actions.expand_template(
        template = ctx.file._template,
        output = script,
        is_executable = True,
        substitutions = {
            "{module_name}": ctx.attr.test[0][TradefedTestInfo].module_name,
            "{atest_tradefed_launcher}": _BAZEL_WORK_DIR + ctx.file._atest_tradefed_launcher.short_path,
            "{atest_helper}": _BAZEL_WORK_DIR + ctx.file._atest_helper.short_path,
            "{tradefed_tests_dir}": _BAZEL_WORK_DIR + ctx.attr.test[0].label.package,
            "{tradefed_classpath}": tradefed_classpath,
            "{shared_lib_dirs}": shared_lib_dirs,
            "{path_additions}": _BAZEL_WORK_DIR + ctx.file._adb.dirname,
        },
    )

    return [DefaultInfo(executable = script, runfiles = runfiles)]

tradefed_deviceless_test = rule(
    attrs = {
        "_template": attr.label(
            default = "//bazel/rules:tradefed_test.sh.template",
            allow_single_file = True,
        ),
        "_tradefed_classpath_jars": attr.label_list(
            default = [
                "//tools/tradefederation/contrib:tradefed-contrib",
                "//tools/tradefederation/core/test_framework:tradefed-test-framework",
                "//tools/tradefederation/core:tradefed",
                "//tools/asuite/atest:atest-tradefed",
                "//tools/asuite/atest/bazel/reporter:bazel-result-reporter",
            ],
            cfg = host_transition,
        ),
        "_atest_tradefed_launcher": attr.label(
            default = "//tools/asuite/atest:atest_tradefed.sh",
            allow_single_file = True,
            cfg = host_transition,
        ),
        "_atest_helper": attr.label(
            default = "//tools/asuite/atest:atest_script_help.sh",
            allow_single_file = True,
            cfg = host_transition,
        ),
        "_adb": attr.label(
            default = "//packages/modules/adb:adb",
            allow_single_file = True,
            cfg = host_transition,
        ),
        "test": attr.label(
            mandatory = True,
            cfg = host_transition,
            aspects = [soong_prebuilt_tradefed_test_aspect],
        ),
        # This attribute is required to use Starlark transitions. It allows
        # allowlisting usage of this rule. For more information, see
        # https://docs.bazel.build/versions/master/skylark/config.html#user-defined-transitions
        "_allowlist_function_transition": attr.label(
            default = "@bazel_tools//tools/allowlists/function_transition_allowlist",
        ),
    },
    test = True,
    implementation = _tradefed_deviceless_test_impl,
    doc = "A rule used to run host-side deviceless tests using Tradefed",
)
