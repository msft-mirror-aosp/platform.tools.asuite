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

load("//bazel/rules:platform_transitions.bzl", "device_transition", "host_transition")
load("//bazel/rules:tradefed_test_aspects.bzl", "soong_prebuilt_tradefed_test_aspect")
load("//bazel/rules:tradefed_test_dependency_info.bzl", "TradefedTestDependencyInfo")
load("//bazel/rules:common_settings.bzl", "BuildSettingInfo")
load(
    "//:constants.bzl",
    "aapt_label",
    "adb_label",
    "atest_script_help_sh_label",
    "atest_tradefed_label",
    "atest_tradefed_sh_label",
    "bazel_result_reporter_label",
    "compatibility_tradefed_label",
    "tradefed_label",
    "tradefed_test_framework_label",
    "vts_core_tradefed_harness_label",
)

_TEST_SRCDIR = "${TEST_SRCDIR}"
_BAZEL_WORK_DIR = "%s/${TEST_WORKSPACE}/" % _TEST_SRCDIR
_PY_TOOLCHAIN = "@bazel_tools//tools/python:toolchain_type"
_TOOLCHAINS = [_PY_TOOLCHAIN]

_TRADEFED_TEST_ATTRIBUTES = {
    "module_name": attr.string(),
    "_tradefed_test_template": attr.label(
        default = "//bazel/rules:tradefed_test.sh.template",
        allow_single_file = True,
    ),
    "_tradefed_classpath_jars": attr.label_list(
        default = [
            atest_tradefed_label,
            tradefed_label,
            tradefed_test_framework_label,
            bazel_result_reporter_label,
        ],
        cfg = host_transition,
        aspects = [soong_prebuilt_tradefed_test_aspect],
    ),
    "_atest_tradefed_launcher": attr.label(
        default = atest_tradefed_sh_label,
        allow_single_file = True,
        cfg = host_transition,
        aspects = [soong_prebuilt_tradefed_test_aspect],
    ),
    "_atest_helper": attr.label(
        default = atest_script_help_sh_label,
        allow_single_file = True,
        cfg = host_transition,
        aspects = [soong_prebuilt_tradefed_test_aspect],
    ),
    "_adb": attr.label(
        default = adb_label,
        allow_single_file = True,
        cfg = host_transition,
        aspects = [soong_prebuilt_tradefed_test_aspect],
    ),
    "_extra_tradefed_result_reporters": attr.label(
        default = "//bazel/rules:extra_tradefed_result_reporters",
    ),
    # This attribute is required to use Starlark transitions. It allows
    # allowlisting usage of this rule. For more information, see
    # https://docs.bazel.build/versions/master/skylark/config.html#user-defined-transitions
    "_allowlist_function_transition": attr.label(
        default = "@bazel_tools//tools/allowlists/function_transition_allowlist",
    ),
}

def _add_dicts(*dictionaries):
    """Creates a new `dict` that has all the entries of the given dictionaries.

    This function serves as a replacement for the `+` operator which does not
    work with dictionaries. The implementation is inspired by Skylib's
    `dict.add` and duplicated to avoid the dependency. See
    https://github.com/bazelbuild/bazel/issues/6461 for more details.

    Note, if the same key is present in more than one of the input dictionaries,
    the last of them in the argument list overrides any earlier ones.

    Args:
        *dictionaries: Dictionaries to be added.

    Returns:
        A new `dict` that has all the entries of the given dictionaries.
    """
    result = {}
    for d in dictionaries:
        result.update(d)
    return result

def _tradefed_deviceless_test_impl(ctx):
    return _tradefed_test_impl(
        ctx,
        tradefed_options = [
            "-n",
            "--prioritize-host-config",
            "--skip-host-arch-check",
        ],
        test_host_deps = ctx.attr.test,
    )

tradefed_deviceless_test = rule(
    attrs = _add_dicts(
        _TRADEFED_TEST_ATTRIBUTES,
        {
            "test": attr.label(
                mandatory = True,
                cfg = host_transition,
                aspects = [soong_prebuilt_tradefed_test_aspect],
            ),
        },
    ),
    test = True,
    implementation = _tradefed_deviceless_test_impl,
    toolchains = _TOOLCHAINS,
    doc = "A rule used to run host-side deviceless tests using Tradefed",
)

def _tradefed_device_test_impl(ctx):
    tradefed_deps = []
    tradefed_deps.extend(ctx.attr._aapt)
    tradefed_deps.extend(ctx.attr.tradefed_deps)

    test_device_deps = []
    test_host_deps = []

    if ctx.attr.host_test:
        test_host_deps.extend(ctx.attr.host_test)
    if ctx.attr.device_test:
        test_device_deps.extend(ctx.attr.device_test)

    return _tradefed_test_impl(
        ctx,
        tradefed_deps = tradefed_deps,
        test_device_deps = test_device_deps,
        test_host_deps = test_host_deps,
        path_additions = [
            _BAZEL_WORK_DIR + ctx.file._aapt.dirname,
        ],
    )

_tradefed_device_test = rule(
    attrs = _add_dicts(
        _TRADEFED_TEST_ATTRIBUTES,
        {
            "device_test": attr.label(
                cfg = device_transition,
                aspects = [soong_prebuilt_tradefed_test_aspect],
            ),
            "host_test": attr.label(
                cfg = host_transition,
                aspects = [soong_prebuilt_tradefed_test_aspect],
            ),
            "tradefed_deps": attr.label_list(
                cfg = host_transition,
                aspects = [soong_prebuilt_tradefed_test_aspect],
            ),
            "_aapt": attr.label(
                default = aapt_label,
                allow_single_file = True,
                cfg = host_transition,
                aspects = [soong_prebuilt_tradefed_test_aspect],
            ),
        },
    ),
    test = True,
    implementation = _tradefed_device_test_impl,
    toolchains = _TOOLCHAINS,
    doc = "A rule used to run device tests using Tradefed",
)

def tradefed_device_driven_test(test, tradefed_deps = [], suites = [], **attrs):
    _tradefed_device_test(
        device_test = test,
        tradefed_deps = _get_tradefed_deps(suites, tradefed_deps),
        **attrs
    )

def tradefed_host_driven_device_test(test, tradefed_deps = [], suites = [], **attrs):
    _tradefed_device_test(
        host_test = test,
        tradefed_deps = _get_tradefed_deps(suites, tradefed_deps),
        **attrs
    )

def _tradefed_test_impl(
        ctx,
        tradefed_options = [],
        tradefed_deps = [],
        test_host_deps = [],
        test_device_deps = [],
        path_additions = []):
    path_additions = path_additions + [_BAZEL_WORK_DIR + ctx.file._adb.dirname]

    all_tradefed_deps = []
    all_tradefed_deps.extend(ctx.attr._tradefed_classpath_jars)
    all_tradefed_deps.extend(ctx.attr._atest_tradefed_launcher)
    all_tradefed_deps.extend(ctx.attr._atest_helper)
    all_tradefed_deps.extend(ctx.attr._adb)
    all_tradefed_deps.extend(tradefed_deps)

    all_host_deps = all_tradefed_deps + test_host_deps

    host_runfiles = _get_runfiles_from_targets(ctx, all_host_deps)

    runtime_jars = depset(
        transitive = [
            d[TradefedTestDependencyInfo].runtime_jars
            for d in all_host_deps
        ],
    ).to_list()
    tradefed_classpath = ":".join([_abspath(f) for f in runtime_jars])

    runtime_shared_libraries = depset(
        transitive = [
            d[TradefedTestDependencyInfo].runtime_shared_libraries
            for d in all_host_deps
        ],
    ).to_list()
    shared_lib_dirs = ":".join(
        [_BAZEL_WORK_DIR + f.dirname for f in runtime_shared_libraries],
    )

    # Configure the Python toolchain.
    py_toolchain_info = ctx.toolchains[_PY_TOOLCHAIN]
    py2_interpreter = py_toolchain_info.py2_runtime.interpreter
    py3_interpreter = py_toolchain_info.py3_runtime.interpreter

    # Create `python` and `python3` symlinks in the runfiles tree and add them to the executable
    # path. This is required because scripts reference these commands in their shebang line.
    host_runfiles = host_runfiles.merge(ctx.runfiles(symlinks = {
        "/".join([py2_interpreter.dirname, "python"]): py2_interpreter,
        "/".join([py3_interpreter.dirname, "python3"]): py3_interpreter,
    }))
    path_additions = path_additions + [
        _BAZEL_WORK_DIR + py2_interpreter.dirname,
        _BAZEL_WORK_DIR + py3_interpreter.dirname,
    ]

    result_reporters = [
        "com.android.tradefed.result.BazelExitCodeResultReporter",
        "com.android.tradefed.result.BazelXmlResultReporter",
    ]

    result_reporters.extend(ctx.attr._extra_tradefed_result_reporters[BuildSettingInfo].value)

    result_reporters_config_file = ctx.actions.declare_file("result-reporters-%s.xml" % ctx.label.name)
    _write_reporters_config_file(
        ctx,
        result_reporters_config_file,
        result_reporters,
    )
    reporter_runfiles = ctx.runfiles(files = [result_reporters_config_file])

    script = ctx.actions.declare_file("tradefed_test_%s.sh" % ctx.label.name)
    ctx.actions.expand_template(
        template = ctx.file._tradefed_test_template,
        output = script,
        is_executable = True,
        substitutions = {
            "{module_name}": ctx.attr.module_name,
            "{atest_tradefed_launcher}": _abspath(ctx.file._atest_tradefed_launcher),
            "{atest_helper}": _abspath(ctx.file._atest_helper),
            "{tradefed_tests_dir}": _TEST_SRCDIR,
            "{tradefed_classpath}": tradefed_classpath,
            "{shared_lib_dirs}": shared_lib_dirs,
            "{path_additions}": ":".join(path_additions),
            "{additional_tradefed_options}": " ".join(tradefed_options),
            "{result_reporters_config_file}": _abspath(result_reporters_config_file),
        },
    )

    device_runfiles = _get_runfiles_from_targets(ctx, test_device_deps)
    return [DefaultInfo(
        executable = script,
        runfiles = host_runfiles.merge_all([device_runfiles, reporter_runfiles]),
    )]

def _get_tradefed_deps(suites, tradefed_deps = []):
    suite_to_deps = {
        "host-unit-tests": [],
        "null-suite": [],
        "device-tests": [],
        "general-tests": [],
        "vts": [vts_core_tradefed_harness_label],
    }
    all_tradefed_deps = {d: None for d in tradefed_deps}

    for s in suites:
        all_tradefed_deps.update({
            d: None
            for d in suite_to_deps.get(s, [compatibility_tradefed_label])
        })

    # Since `vts-core-tradefed-harness` includes `compatibility-tradefed`, we
    # will exclude `compatibility-tradefed` if `vts-core-tradefed-harness` exists.
    if vts_core_tradefed_harness_label in all_tradefed_deps:
        all_tradefed_deps.pop(compatibility_tradefed_label, default = None)

    return all_tradefed_deps.keys()

def _write_reporters_config_file(ctx, config_file, result_reporters):
    config_lines = [
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>",
        "<configuration>",
    ]

    for result_reporter in result_reporters:
        config_lines.append("    <result_reporter class=\"%s\" />" % result_reporter)

    config_lines.append("</configuration>")

    ctx.actions.write(config_file, "\n".join(config_lines))

def _get_runfiles_from_targets(ctx, targets):
    return ctx.runfiles().merge_all([
        target[DefaultInfo].default_runfiles
        for target in targets
    ])

def _abspath(file):
    return _BAZEL_WORK_DIR + file.short_path