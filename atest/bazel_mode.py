# Copyright 2021, The Android Open Source Project
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
Implementation of Atest's Bazel mode.

Bazel mode runs tests using Bazel by generating a synthetic workspace that
contains test targets. Using Bazel allows Atest to leverage features such as
sandboxing, caching, and remote execution.
"""
# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring

from __future__ import annotations

import contextlib
import dataclasses
import functools
import os
import shutil
import subprocess

from abc import ABC, abstractmethod
from collections import defaultdict, deque, OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, IO, List, Set

import atest_utils
import constants
import module_info

from test_finders import test_finder_base
from test_finders import test_info
from test_runners import test_runner_base


_BAZEL_WORKSPACE_DIR = 'atest_bazel_workspace'


def get_bazel_workspace_dir() -> Path:
    return Path(atest_utils.get_build_out_dir()).joinpath(_BAZEL_WORKSPACE_DIR)


def generate_bazel_workspace(mod_info: module_info.ModuleInfo):
    """Generate or update the Bazel workspace used for running tests."""
    src_root_path = Path(os.environ.get(constants.ANDROID_BUILD_TOP))
    workspace_path = get_bazel_workspace_dir()
    workspace_generator = WorkspaceGenerator(
        src_root_path,
        workspace_path,
        Path(os.environ.get(constants.ANDROID_PRODUCT_OUT)),
        Path(os.environ.get(constants.ANDROID_HOST_OUT)),
        Path(atest_utils.get_build_out_dir()),
        mod_info,
    )
    workspace_generator.generate()


class WorkspaceGenerator:
    """Class for generating a Bazel workspace."""

    # pylint: disable=too-many-arguments
    def __init__(self, src_root_path: Path, workspace_out_path: Path,
                 product_out_path: Path, host_out_path: Path,
                 build_out_dir: Path, mod_info: module_info.ModuleInfo):
        """Initializes the generator.

        Args:
            src_root_path: Path of the ANDROID_BUILD_TOP.
            workspace_out_path: Path where the workspace will be output.
            product_out_path: Path of the ANDROID_PRODUCT_OUT.
            host_out_path: Path of the ANDROID_HOST_OUT.
            build_out_dir: Path of OUT_DIR
            mod_info: ModuleInfo object.
        """
        self.src_root_path = src_root_path
        self.workspace_out_path = workspace_out_path
        self.product_out_path = product_out_path
        self.host_out_path = host_out_path
        self.build_out_dir = build_out_dir
        self.mod_info = mod_info
        self.mod_info_md5_path = self.workspace_out_path.joinpath(
            'mod_info_md5')
        self.path_to_package = {}

    def generate(self):
        """Generate the Bazel workspace if mod_info doesn't exist or stale."""
        if atest_utils.check_md5(self.mod_info_md5_path):
            return

        atest_utils.colorful_print("Generating Bazel workspace.\n",
                                   constants.RED)

        if self.workspace_out_path.exists():
            # We raise an exception if rmtree fails to avoid leaving stale
            # files in the workspace that could interfere with execution.
            shutil.rmtree(self.workspace_out_path)

        self._add_test_module_targets()

        self.workspace_out_path.mkdir(parents=True)
        self._generate_artifacts()

        atest_utils.save_md5([self.mod_info.mod_info_file_path],
                             self.mod_info_md5_path)

    def _add_test_module_targets(self):
        seen = set()

        for name, info in self.mod_info.name_to_module_info.items():
            # Ignore modules that have a 'host_cross_' prefix since they are
            # duplicates of existing modules. For example,
            # 'host_cross_aapt2_tests' is a duplicate of 'aapt2_tests'. We also
            # ignore modules with a '_32' suffix since these also are redundant
            # given that modules have both 32 and 64-bit variants built by
            # default. See b/77288544#comment6 and b/23566667 for more context.
            if name.endswith("_32") or name.startswith("host_cross_"):
                continue
            if not self.is_host_unit_test(info):
                continue
            if not self.mod_info.is_testable_module(info):
                continue

            target = self._add_deviceless_test_target(info)
            self._resolve_dependencies(target, seen)

    def _resolve_dependencies(
        self, top_level_target: Target, seen: Set[Target]):

        stack = [deque([top_level_target])]

        while stack:
            top = stack[-1]

            if not top:
                stack.pop()
                continue

            target = top.popleft()

            # Note that we're relying on Python's default identity-based hash
            # and equality methods. This is fine since we actually DO want
            # reference-equality semantics for Target objects in this context.
            if target in seen:
                continue

            seen.add(target)

            next_top = deque()

            for ref in target.dependencies():
                info = ref.info or self._get_module_info(ref.name)
                ref.set(self._add_prebuilt_target(info))
                next_top.append(ref.target())

            stack.append(next_top)

    def _add_deviceless_test_target(self, info: Dict[str, Any]) -> Target:
        package_name = self._get_module_path(info)
        name = info['module_name'] + "_host"

        def create():
            return DevicelessTestTarget.create(
                name,
                package_name,
                info,
            )

        return self._add_target(package_name, name, create)

    def _add_prebuilt_target(self, info: Dict[str, Any]) -> Target:
        package_name = self._get_module_path(info)
        name = info['module_name']

        def create():
            return SoongPrebuiltTarget.create(
                self,
                info,
                package_name,
            )

        return self._add_target(package_name, name, create)

    def _add_target(self, package_path: str, target_name: str,
                    create_fn: Callable) -> Target:

        package = self.path_to_package.get(package_path)

        if not package:
            package = Package(package_path)
            self.path_to_package[package_path] = package

        target = package.get_target(target_name)

        if target:
            return target

        target = create_fn()
        package.add_target(target)

        return target

    def _get_module_info(self, module_name: str) -> Dict[str, Any]:
        info = self.mod_info.get_module_info(module_name)

        if not info:
            raise Exception(f'Could not find module `{module_name}` in'
                            f' module_info file')

        return info

    def _get_module_path(self, info: Dict[str, Any]) -> str:
        mod_path = info.get(constants.MODULE_PATH)

        if len(mod_path) != 1:
            module_name = info['module_name']
            # We usually have a single path but there are a few exceptions for
            # modules like libLLVM_android and libclang_android.
            # TODO(nelsonli): Remove this check once b/153609531 is fixed.
            raise Exception(f'Module `{module_name}` does not have exactly one'
                            f' path: {mod_path}')

        return mod_path[0]

    def is_host_unit_test(self, info: Dict[str, Any]) -> bool:
        return self.mod_info.is_suite_in_compatibility_suites(
            'host-unit-tests', info)

    def _generate_artifacts(self):
        """Generate workspace files on disk."""

        self._create_base_files()
        self._create_rules_dir()

        for package in self.path_to_package.values():
            package.generate(self.workspace_out_path)

    def _create_rules_dir(self):
        symlink = self.workspace_out_path.joinpath('bazel/rules')
        symlink.parent.mkdir(parents=True)
        symlink.symlink_to(self.src_root_path.joinpath(
            'tools/asuite/atest/bazel/rules'))

    def _create_base_files(self):
        self.workspace_out_path.joinpath('WORKSPACE').touch()
        self.workspace_out_path.joinpath('.bazelrc').symlink_to(
            self.src_root_path.joinpath('tools/asuite/atest/bazel/bazelrc'))


class Package:
    """Class for generating an entire Package on disk."""

    def __init__(self, path: str):
        self.path = path
        self.imports = defaultdict(set)
        self.name_to_target = OrderedDict()

    def add_target(self, target):
        target_name = target.name()

        if target_name in self.name_to_target:
            raise Exception(f'Cannot add target `{target_name}` which already'
                            f' exists in package `{self.path}`')

        self.name_to_target[target_name] = target

        for i in target.required_imports():
            self.imports[i.bzl_package].add(i.symbol)

    def generate(self, workspace_out_path: Path):
        package_dir = workspace_out_path.joinpath(self.path)
        package_dir.mkdir(parents=True, exist_ok=True)

        self._create_filesystem_layout(package_dir)
        self._write_build_file(package_dir)

    def _create_filesystem_layout(self, package_dir: Path):
        for target in self.name_to_target.values():
            target.create_filesystem_layout(package_dir)

    def _write_build_file(self, package_dir: Path):
        with package_dir.joinpath('BUILD.bazel').open('w') as f:
            f.write('package(default_visibility = ["//visibility:public"])\n')
            f.write('\n')

            for bzl_package, symbols in sorted(self.imports.items()):
                symbols_text = ', '.join('"%s"' % s for s in sorted(symbols))
                f.write(f'load("{bzl_package}", {symbols_text})\n')

            for target in self.name_to_target.values():
                f.write('\n')
                target.write_to_build_file(f)

    def get_target(self, target_name: str) -> Target:
        return self.name_to_target.get(target_name, None)


@dataclasses.dataclass(frozen=True)
class Import:
    bzl_package: str
    symbol: str


@dataclasses.dataclass(frozen=True)
class Config:
    name: str
    out_path: Path


class ModuleRef:

    @staticmethod
    def for_info(info) -> ModuleRef:
        return ModuleRef(info=info)

    @staticmethod
    def for_name(name) -> ModuleRef:
        return ModuleRef(name=name)

    def __init__(self, info=None, name=None):
        self.info = info
        self.name = name
        self._target = None

    def target(self) -> Target:
        if not self._target:
            module_name = self.info['module_name']
            raise Exception(f'Target not set for ref `{module_name}`')

        return self._target

    def set(self, target):
        self._target = target


class Target(ABC):
    """Abstract class for a Bazel target."""

    @abstractmethod
    def name(self) -> str:
        pass

    def package_name(self) -> str:
        pass

    def qualified_name(self) -> str:
        return f'//{self.package_name()}:{self.name()}'

    def required_imports(self) -> Set[Import]:
        return set()

    def supported_configs(self) -> Set[Config]:
        return set()

    def dependencies(self) -> List[ModuleRef]:
        return []

    def write_to_build_file(self, f: IO):
        pass

    def create_filesystem_layout(self, package_dir: Path):
        pass


class DevicelessTestTarget(Target):
    """Class for generating a deviceless test target."""

    PREREQUISITES = frozenset({
        'adb',
        'atest-tradefed',
        'atest_script_help.sh',
        'atest_tradefed.sh',
        'tradefed',
        'tradefed-contrib',
        'tradefed-test-framework',
        'bazel-result-reporter'
    })

    @staticmethod
    def create(name: str, package_name: str, info: Dict[str, Any]):
        return DevicelessTestTarget(name, package_name, info)

    def __init__(self, name: str, package_name: str, info: Dict[str, Any]):
        self._name = name
        self._package_name = package_name
        self._test_module_ref = ModuleRef.for_info(info)

    def name(self) -> str:
        return self._name

    def package_name(self) -> str:
        return self._package_name

    def required_imports(self) -> Set[Import]:
        return {
            Import('//bazel/rules:tradefed_test.bzl',
                   'tradefed_deviceless_test'),
        }

    def supported_configs(self) -> Set[Config]:
        return set()

    def dependencies(self) -> List[ModuleRef]:
        prerequisite_refs = map(
            ModuleRef.for_name, DevicelessTestTarget.PREREQUISITES)
        return [self._test_module_ref] + list(prerequisite_refs)

    def write_to_build_file(self, f: IO):
        prebuilt_target_name = self._test_module_ref.target().qualified_name()
        writer = IndentWriter(f)

        writer.write_line('tradefed_deviceless_test(')

        with writer.indent():
            writer.write_line(f'name = "{self._name}",')
            writer.write_line(f'test = "{prebuilt_target_name}",')

        writer.write_line(')')


class SoongPrebuiltTarget(Target):
    """Class for generating a Soong prebuilt target on disk."""

    @staticmethod
    def create(gen: WorkspaceGenerator,
               info: Dict[str, Any],
               package_name: str=''):
        module_name = info['module_name']

        configs = [
            Config('host', gen.host_out_path),
            Config('device', gen.product_out_path),
        ]

        installed_paths = get_module_installed_paths(info, gen.src_root_path)
        config_files = group_paths_by_config(configs, installed_paths)

        # For test modules, we only create symbolic link to the 'testcases'
        # directory since the information in module-info is not accurate.
        #
        # Note that we use is_tf_testable_module here instead of ModuleInfo
        # class's is_testable_module method to avoid misadding a shared library
        # as a test module.
        # e.g.
        # 1. test_module A has a shared_lib (or RLIB, DYLIB) of B
        # 2. We create target B as a result of method _resolve_dependencies for
        #    target A
        # 3. B matches the conditions of is_testable_module:
        #     a. B has installed path.
        #     b. has_config return True
        #     Note that has_config method also looks for AndroidTest.xml in the
        #     dir of B. If there is a test module in the same dir, B could be
        #     added as a test module.
        # 4. We create symbolic link to the 'testcases' for non test target B
        #    and cause errors.
        if is_tf_testable_module(gen.mod_info, info):
            config_files = {c: [c.out_path.joinpath(f'testcases/{module_name}')]
                            for c in config_files.keys()}

        return SoongPrebuiltTarget(
            module_name,
            package_name,
            config_files,
            find_runtime_dep_refs(gen.mod_info, info, configs,
                                  gen.src_root_path)
        )

    def __init__(self, name: str, package_name: str,
                 config_files: Dict[Config, List[Path]],
                 runtime_dep_refs: List[ModuleRef]):
        self._name = name
        self._package_name = package_name
        self.config_files = config_files
        self.runtime_dep_refs = runtime_dep_refs

    def name(self) -> str:
        return self._name

    def package_name(self) -> str:
        return self._package_name

    def required_imports(self) -> Set[Import]:
        return {
            Import('//bazel/rules:soong_prebuilt.bzl', self._rule_name()),
        }

    @functools.lru_cache(maxsize=None)
    def supported_configs(self) -> Set[Config]:
        supported_configs = set(self.config_files.keys())

        if supported_configs:
            return supported_configs

        # If a target has no installed files, then it supports the same
        # configurations as its dependencies. This is required because some
        # build modules are just intermediate targets that don't produce any
        # output but that still have transitive dependencies.
        for ref in self.runtime_dep_refs:
            supported_configs.update(ref.target().supported_configs())

        return supported_configs

    def dependencies(self) -> List[ModuleRef]:
        return self.runtime_dep_refs

    def write_to_build_file(self, f: IO):
        writer = IndentWriter(f)

        writer.write_line(f'{self._rule_name()}(')

        with writer.indent():
            writer.write_line(f'name = "{self._name}",')
            writer.write_line(f'module_name = "{self._name}",')
            self._write_files_attribute(writer)
            self._write_runtime_deps_attribute(writer)

        writer.write_line(')')

    def create_filesystem_layout(self, package_dir: Path):
        prebuilts_dir = package_dir.joinpath(self._name)
        prebuilts_dir.mkdir()

        for config, files in self.config_files.items():
            config_prebuilts_dir = prebuilts_dir.joinpath(config.name)
            config_prebuilts_dir.mkdir()

            for f in files:
                rel_path = f.relative_to(config.out_path)
                symlink = config_prebuilts_dir.joinpath(rel_path)
                symlink.parent.mkdir(parents=True, exist_ok=True)
                symlink.symlink_to(f)

    def _rule_name(self):
        return ('soong_prebuilt' if self.config_files
                else 'soong_uninstalled_prebuilt')

    def _write_files_attribute(self, writer: IndentWriter):
        if not self.config_files:
            return

        name = self._name

        writer.write('files = ')
        write_config_select(
            writer,
            self.config_files,
            lambda c, _: writer.write(f'glob(["{name}/{c.name}/**/*"])'),
        )
        writer.write_line(',')

    def _write_runtime_deps_attribute(self, writer):
        config_deps = filter_configs(
            group_targets_by_config(r.target() for r in self.runtime_dep_refs),
            self.supported_configs()
        )

        if not config_deps:
            return

        for config in self.supported_configs():
            config_deps.setdefault(config, list())

        writer.write('runtime_deps = ')
        write_config_select(
            writer,
            config_deps,
            lambda _, targets: write_target_list(writer, targets),
        )
        writer.write_line(',')


def group_paths_by_config(
    configs: List[Config], paths: List[Path]) -> Dict[Config, List[Path]]:

    config_files = defaultdict(list)

    for f in paths:
        matching_configs = [
            c for c in configs if _is_relative_to(f, c.out_path)]

        if not matching_configs:
            continue

        # The path can only appear in ANDROID_HOST_OUT for host target or
        # ANDROID_PRODUCT_OUT, but cannot appear in both.
        if len(matching_configs) > 1:
            raise Exception(f'Installed path `{f}` is not in'
                            f' ANDROID_HOST_OUT or ANDROID_PRODUCT_OUT')

        config_files[matching_configs[0]].append(f)

    return config_files


def group_targets_by_config(
    targets: List[Target]) -> Dict[Config, List[Target]]:

    config_to_targets = defaultdict(list)

    for target in targets:
        for config in target.supported_configs():
            config_to_targets[config].append(target)

    return config_to_targets


def filter_configs(
    config_dict: Dict[Config, Any], configs: Set[Config],) -> Dict[Config, Any]:
    return { k: v for (k, v) in config_dict.items() if k in configs }


def _is_relative_to(path1: Path, path2: Path) -> bool:
    """Return True if the path is relative to another path or False."""
    # Note that this implementation is required because Path.is_relative_to only
    # exists starting with Python 3.9.
    try:
        path1.relative_to(path2)
        return True
    except ValueError:
        return False


def get_module_installed_paths(
    info: Dict[str, Any], src_root_path: Path) -> List[Path]:

    # Install paths in module-info are usually relative to the Android
    # source root ${ANDROID_BUILD_TOP}. When the output directory is
    # customized by the user however, the install paths are absolute.
    def resolve(install_path_string):
        install_path = Path(install_path_string)
        if not install_path.expanduser().is_absolute():
            return src_root_path.joinpath(install_path)
        return install_path

    return map(resolve, info.get(constants.MODULE_INSTALLED))


def find_runtime_dep_refs(
    mod_info: module_info.ModuleInfo,
    info: module_info.Module,
    configs: List[Config],
    src_root_path: Path,
) -> List[ModuleRef]:
    """Return module dependencies required at runtime."""

    runtime_dep_refs = []

    # We don't use the `dependencies` module-info field for shared libraries
    # since it's ambiguous and could generate more targets and pull in more
    # dependencies than necessary. In particular, libraries that support both
    # static and dynamic linking could end up becoming runtime dependencies
    # even though the build specifies static linking. For example, if a target
    # 'T' is statically linked to 'U' which supports both variants, the latter
    # still appears as a dependency. Since we can't tell, this would result in
    # the shared library variant of 'U' being added on the library path.
    for lib_name in info.get(constants.MODULE_SHARED_LIBS, []):
        lib_info = mod_info.get_module_info(lib_name)
        if not lib_info:
            continue
        installed_paths = get_module_installed_paths(lib_info,
                                                     src_root_path)
        config_files = group_paths_by_config(configs, installed_paths)
        if not config_files:
            continue

        runtime_dep_refs.append(ModuleRef.for_info(lib_info))

    runtime_library_class = {'RLIB_LIBRARIES', 'DYLIB_LIBRARIES'}
    # We collect rlibs even though they are technically static libraries since
    # they could refer to dylibs which are required at runtime. Generating
    # Bazel targets for these intermediate modules keeps the generator simple
    # and preserves the shape (isomorphic) of the Soong structure making the
    # workspace easier to debug.
    for dep_name in info.get(constants.MODULE_DEPENDENCIES, []):
        dep_info = mod_info.get_module_info(dep_name)
        if not dep_info:
            continue
        if not runtime_library_class.intersection(
            dep_info.get(constants.MODULE_CLASS, [])):
            continue
        runtime_dep_refs.append(ModuleRef.for_info(dep_info))

    return runtime_dep_refs


class IndentWriter:

    def __init__(self, f: IO):
        self._file = f
        self._indent_level = 0
        self._indent_string = 4 * ' '
        self._indent_next = True

    def write_line(self, text: str=''):
        if text:
            self.write(text)

        self._file.write('\n')
        self._indent_next = True

    def write(self, text):
        if self._indent_next:
            self._file.write(self._indent_string * self._indent_level)
            self._indent_next = False

        self._file.write(text)

    @contextlib.contextmanager
    def indent(self):
        self._indent_level += 1
        yield
        self._indent_level -= 1


def write_config_select(
    writer: IndentWriter,
    config_dict: Dict[Config, Any],
    write_value_fn: Callable,
):
    writer.write_line('select({')

    with writer.indent():
        for config, value in sorted(
            config_dict.items(), key=lambda c: c[0].name):

            writer.write(f'"//bazel/rules:{config.name}": ')
            write_value_fn(config, value)
            writer.write_line(',')

    writer.write('})')


def write_target_list(writer: IndentWriter, targets: List[Target]):
    writer.write_line('[')

    with writer.indent():
        for label in sorted(set(t.qualified_name() for t in targets)):
            writer.write_line(f'"{label}",')

    writer.write(']')


def is_tf_testable_module(mod_info: module_info.ModuleInfo,
                          info: Dict[str, Any]):
    """Check if the module is a Tradefed runnable test module.

    ModuleInfo.is_testable_module() is from ATest's point of view. It only
    checks if a module has installed path and has local config files. This
    way is not reliable since some libraries might match these two conditions
    and be included mistakenly. Robolectric_utils is an example that matched
    these two conditions but not testable. This function make sure the module
    is a TF runnable test module.
    """
    return (mod_info.is_testable_module(info)
            and info.get(constants.MODULE_COMPATIBILITY_SUITES))


def _decorate_find_method(mod_info, finder_method_func):
    """A finder_method decorator to override TestInfo properties."""

    def use_bazel_runner(finder_obj, test_id):
        test_infos = finder_method_func(finder_obj, test_id)
        if not test_infos:
            return test_infos
        for tinfo in test_infos:
            m_info = mod_info.get_module_info(tinfo.test_name)
            if mod_info.is_suite_in_compatibility_suites(
                'host-unit-tests', m_info):
                tinfo.test_runner = BazelTestRunner.NAME
        return test_infos
    return use_bazel_runner


def create_new_finder(mod_info, finder):
    """Create new test_finder_base.Finder with decorated find_method.

    Args:
      mod_info: ModuleInfo object.
      finder: Test Finder class.

    Returns:
        List of ordered find methods.
    """
    return test_finder_base.Finder(finder.test_finder_instance,
                                   _decorate_find_method(
                                       mod_info,
                                       finder.find_method),
                                   finder.finder_info)


def default_run_command(args: List[str], cwd: Path) -> str:
    return subprocess.check_output(
        args=args,
        cwd=cwd,
        text=True,
        stderr=subprocess.DEVNULL,
    )


class BazelTestRunner(test_runner_base.TestRunnerBase):
    """Bazel Test Runner class."""

    NAME = 'BazelTestRunner'
    EXECUTABLE = 'none'

    # pylint: disable=redefined-outer-name
    # pylint: disable=too-many-arguments
    def __init__(self,
                 results_dir,
                 mod_info: module_info.ModuleInfo,
                 test_infos: List[test_info.TestInfo]=None,
                 src_top: Path=None,
                 workspace_path: Path=None,
                 run_command: Callable=default_run_command,
                 **kwargs):
        super().__init__(results_dir, **kwargs)
        self.mod_info = mod_info
        self.test_infos = test_infos
        self.src_top = src_top or Path(os.environ.get(
            constants.ANDROID_BUILD_TOP))
        self.starlark_file = self.src_top.joinpath(
            'tools/asuite/atest/bazel/format_as_soong_module_name.cquery')

        self.bazel_binary = self.src_top.joinpath(
            'prebuilts/bazel/linux-x86_64/bazel')
        self.bazel_workspace = workspace_path or get_bazel_workspace_dir()
        self.run_command = run_command

    # pylint: disable=unused-argument
    def run_tests(self, test_infos, extra_args, reporter):
        """Run the list of test_infos.

        Args:
            test_infos: List of TestInfo.
            extra_args: Dict of extra args to add to test run.
            reporter: An instance of result_report.ResultReporter
        """
        reporter.register_unsupported_runner(self.NAME)
        ret_code = constants.EXIT_CODE_SUCCESS

        run_cmds = self.generate_run_commands(test_infos, extra_args)
        for run_cmd in run_cmds:
            subproc = self.run(run_cmd, output_to_stdout=True)
            ret_code |= self.wait_for_subprocess(subproc)
        return ret_code

    def host_env_check(self):
        """Check that host env has everything we need.

        We actually can assume the host env is fine because we have the same
        requirements that atest has. Update this to check for android env vars
        if that changes.
        """

    def get_test_runner_build_reqs(self) -> Set[str]:
        if not self.test_infos:
            return set()

        deps_expression = ' + '.join(
            sorted(self.test_info_target_label(i) for i in self.test_infos)
        )

        query_args = [
            self.bazel_binary,
            'cquery',
            f'deps(tests({deps_expression}))',
            '--output=starlark',
            f'--starlark:file={self.starlark_file}',
        ]

        output = self.run_command(query_args, self.bazel_workspace)

        return set(filter(bool, map(str.strip, output.splitlines())))

    def test_info_target_label(self, test: test_info.TestInfo) -> str:
        info = self.mod_info.get_module_info(test.test_name)
        package_name = info.get(constants.MODULE_PATH)[0]
        return f'//{package_name}:{test.test_name}_host'

    # pylint: disable=unused-argument
    # pylint: disable=unused-variable
    def generate_run_commands(self, test_infos, extra_args, port=None):
        """Generate a list of run commands from TestInfos.

        Args:
            test_infos: A set of TestInfo instances.
            extra_args: A Dict of extra args to append.
            port: Optional. An int of the port number to send events to.

        Returns:
            A list of run commands to run the tests.
        """
        target_patterns = ' '.join(self.test_info_target_label(i)
                                   for i in test_infos)
        # Use 'cd' instead of setting the working directory in the subprocess
        # call for a working --dry-run command that users can run.
        return [f'cd {self.bazel_workspace} &&'
                f'{self.bazel_binary} test {target_patterns}']
