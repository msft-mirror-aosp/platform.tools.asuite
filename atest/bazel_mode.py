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

import dataclasses
import os
import shutil

from abc import ABC, abstractmethod
from collections import defaultdict, OrderedDict
from pathlib import Path
from typing import Any, Dict, IO, List, Set, Callable

import atest_utils
import constants
import module_info

from test_finders import test_finder_base
from test_runners import test_runner_base


def generate_bazel_workspace(mod_info: module_info.ModuleInfo):
    """Generate or update the Bazel workspace used for running tests."""
    src_root_path = Path(os.environ.get(constants.ANDROID_BUILD_TOP))
    workspace_generator = WorkspaceGenerator(
        src_root_path, src_root_path.joinpath('out/atest_bazel_workspace'),
        Path(os.environ.get(constants.ANDROID_PRODUCT_OUT)),
        Path(os.environ.get(constants.ANDROID_HOST_OUT)),
        Path(atest_utils.get_build_out_dir()), mod_info)
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
        self.prerequisite_modules = {
            'adb',
            'tradefed',
            'tradefed-contrib',
            'tradefed-test-framework',
            'atest-tradefed',
            'atest_tradefed.sh',
            'atest_script_help.sh',
        }

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

        self._add_prerequisite_module_targets()
        self._add_test_module_targets()

        self.workspace_out_path.mkdir(parents=True)
        self._generate_artifacts()

        atest_utils.save_md5([str(self.mod_info.mod_info_file_path)],
                             self.mod_info_md5_path)

    def _add_prerequisite_module_targets(self):
        for module_name in self.prerequisite_modules:
            self._add_prebuilt_target_by_module_name(module_name)

    def _add_test_module_targets(self):
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
            self._add_deviceless_test_target(info)

    def _add_target(self, package_path: str, target_name: str,
                    create_fn: Callable) -> 'Target':
        package = self.path_to_package.setdefault(package_path,
                                                  Package(package_path))
        target = package.get_target(target_name)

        if target:
            return target

        target = create_fn()
        package.add_target(target)
        return target

    def _add_prebuilt_target_by_module_name(self, module_name: str):
        self._add_prebuilt_target(self._get_module_info(module_name))

    def _add_prebuilt_target(self, info: Dict[str, Any]) -> 'Target':
        package_name = self._get_module_path(info)
        name = info['module_name']

        def create():
            runtime_dep_targets = []

            for lib_name in info.get(constants.MODULE_SHARED_LIBS, []):
                lib_info = self._get_module_info(lib_name)
                if not lib_info.get(constants.MODULE_INSTALLED):
                    continue
                runtime_dep_targets.append(self._add_prebuilt_target(lib_info))

            return SoongPrebuiltTarget.create(
                self,
                info,
                package_name,
                self.mod_info.is_testable_module(info),
                runtime_dep_targets
            )

        return self._add_target(package_name, name, create)

    def _add_deviceless_test_target(self, info: Dict[str, Any]) -> 'Target':
        package_name = self._get_module_path(info)
        name = info['module_name'] + "_host"

        def create():
            test_prebuilt_target = self._add_prebuilt_target(info)
            return DevicelessTestTarget.create(
                name, package_name, test_prebuilt_target.qualified_name())

        return self._add_target(package_name, name, create)

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

    def get_target(self, target_name: str) -> 'Target':
        return self.name_to_target.get(target_name, None)


@dataclasses.dataclass(frozen=True)
class Import:
    bzl_package: str
    symbol: str


@dataclasses.dataclass(frozen=True)
class Config:
    name: str
    out_path: Path


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

    def write_to_build_file(self, f: IO):
        pass

    def create_filesystem_layout(self, package_dir: Path):
        pass


class DevicelessTestTarget(Target):
    """Class for generating a deviceless test target."""

    @staticmethod
    def create(name: str, package_name: str, prebuilt_target_name: str):
        return DevicelessTestTarget(name, package_name, prebuilt_target_name)

    def __init__(self, name: str, package_name: str, prebuilt_target_name: str):
        self._name = name
        self._package_name = package_name
        self._prebuilt_target_name = prebuilt_target_name

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

    def write_to_build_file(self, f: IO):
        def fprint(text):
            print(text, file=f)

        fprint('tradefed_deviceless_test(')
        fprint(f'    name = "{self._name}",')
        fprint(f'    test = "{self._prebuilt_target_name}",')
        fprint(')')


class SoongPrebuiltTarget(Target):
    """Class for generating a Soong prebuilt target on disk."""

    @staticmethod
    def create(gen: WorkspaceGenerator,
               info: Dict[str, Any],
               package_name: str='',
               test_module: bool=False,
               runtime_dep_targets: List[Target]=None):
        module_name = info['module_name']

        configs = [
            Config('host', gen.host_out_path),
            Config('device', gen.product_out_path),
        ]

        installed_paths = get_module_installed_paths(info, gen.src_root_path)
        config_files = group_paths_by_config(configs, installed_paths)

        # For test modules, we only create symbolic link to the 'testcases'
        # directory since the information in module-info is not accurate.
        if test_module:
            config_files = {c: [c.out_path.joinpath(f'testcases/{module_name}')]
                            for c in config_files.keys()}

        if not config_files:
            raise Exception(f'Module `{module_name}` does not have any'
                            f' installed paths')

        return SoongPrebuiltTarget(module_name, package_name, config_files,
                                   runtime_dep_targets)

    def __init__(self, name: str, package_name: str,
                 config_files: Dict[Config, List[Path]],
                 runtime_dep_targets: List[Target]=None):
        self._name = name
        self._package_name = package_name
        self.config_files = config_files
        self.config_dep_targets = group_targets_by_config(
            runtime_dep_targets or [])

    def name(self) -> str:
        return self._name

    def package_name(self) -> str:
        return self._package_name

    def required_imports(self) -> Set[Import]:
        return {
            Import('//bazel/rules:soong_prebuilt.bzl', 'soong_prebuilt'),
        }

    def supported_configs(self) -> Set[Config]:
        return self.config_files.keys()

    def write_to_build_file(self, f: IO):
        def fprint(text):
            print(text, file=f)

        fprint('soong_prebuilt(')
        fprint(f'    name = "{self._name}",')
        fprint('    files = select({')

        for config in sorted(self.config_files.keys(), key=lambda c: c.name):
            fprint(f'        "//bazel/rules:{config.name}":'
                   f' glob(["{self._name}/{config.name}/**/*"]),')

        fprint('    }),')
        fprint(f'    module_name = "{self._name}",')

        if self.config_dep_targets:
            fprint('    runtime_deps = select({')

            for config, deps in sorted(self.config_dep_targets.items(),
                                     key=lambda c: c[0].name):
                runtime_dep_names = sorted(d.qualified_name() for d in deps)

                fprint(f'        "//bazel/rules:{config.name}": [')
                fprint('\n'.join(
                    f'            "{d}",' for d in runtime_dep_names))
                fprint('        ],')

            fprint('    }),')

        fprint(')')

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


def group_paths_by_config(
    configs: List[Config], paths: List[Path]) -> Dict[Config, List[Path]]:

    config_files = defaultdict(list)

    for f in paths:
        matching_configs = [
            c for c in configs if _is_relative_to(f, c.out_path)]

        # The path can only appear in ANDROID_HOST_OUT for host target or
        # ANDROID_PRODUCT_OUT, but cannot appear in both.
        if len(matching_configs) != 1:
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


def _decorate_find_method(mod_info, finder_method_func):
    """A finder_method decorator to override TestInfo properties."""

    def use_bazel_runner(finder_obj, test_id):
        test_infos = finder_method_func(finder_obj, test_id)
        if not test_infos:
            return test_infos
        for tinfo in test_infos:
            m_info = mod_info.get_module_info(tinfo.test_name)
            if mod_info.is_unit_test(m_info):
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

class BazelTestRunner(test_runner_base.TestRunnerBase):
    """Bazel Test Runner class."""
    NAME = 'BazelTestRunner'
    EXECUTABLE = 'none'

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
            subproc = self.run(run_cmd,
                               output_to_stdout=True)
            ret_code |= self.wait_for_subprocess(subproc)
        return ret_code

    def host_env_check(self):
        """Check that host env has everything we need.

        We actually can assume the host env is fine because we have the same
        requirements that atest has. Update this to check for android env vars
        if that changes.
        """

    def get_test_runner_build_reqs(self):
        """Return the build requirements.

        Returns:
            Set of build targets.
        """
        return set()

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
        run_cmds = []
        for tinfo in test_infos:
            run_cmds.append('echo "bazel test";')
        return run_cmds
