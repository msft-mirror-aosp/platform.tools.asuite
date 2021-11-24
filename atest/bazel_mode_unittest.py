#!/usr/bin/env python3
#
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

"""Unit tests for bazel_mode."""
# pylint: disable=invalid-name
# pylint: disable=missing-function-docstring

import shlex
import shutil
import tempfile
import unittest

from pathlib import Path
from unittest import mock

# pylint: disable=import-error
from pyfakefs import fake_filesystem_unittest

import bazel_mode
import constants
import module_info

from test_finders import test_info
from test_runners import atest_tf_test_runner


ATEST_TF_RUNNER = atest_tf_test_runner.AtestTradefedTestRunner.NAME
BAZEL_RUNNER = bazel_mode.BazelTestRunner.NAME
MODULE_BUILD_TARGETS = {'foo1', 'foo2', 'foo3'}
MODULE_NAME = 'foo'


class GenerationTestFixture(fake_filesystem_unittest.TestCase):
    """Fixture for workspace generation tests."""

    def setUp(self):
        self.setUpPyfakefs()

        self.src_root_path = Path('/src')
        self.out_dir_path = self.src_root_path.joinpath('out')
        self.out_dir_path.mkdir(parents=True)
        self.product_out_path = self.out_dir_path.joinpath('product')
        self.host_out_path = self.out_dir_path.joinpath('host')
        self.workspace_out_path = self.out_dir_path.joinpath('workspace')

    def create_workspace_generator(self, modules=None):
        mod_info = self.create_module_info(modules)

        generator = bazel_mode.WorkspaceGenerator(
            self.src_root_path,
            self.workspace_out_path,
            self.product_out_path,
            self.host_out_path,
            self.out_dir_path,
            mod_info
        )

        return generator

    def run_generator(self, mod_info):
        generator = bazel_mode.WorkspaceGenerator(
            self.src_root_path,
            self.workspace_out_path,
            self.product_out_path,
            self.host_out_path,
            self.out_dir_path,
            mod_info
        )

        generator.generate()

    # pylint: disable=protected-access
    @mock.patch.dict('os.environ', {constants.ANDROID_BUILD_TOP:'/'})
    def create_empty_module_info(self):
        fake_temp_file_name = next(tempfile._get_candidate_names())
        self.fs.create_file(fake_temp_file_name, contents='{}')
        return module_info.ModuleInfo(module_file=fake_temp_file_name)

    def create_module_info(self, modules=None):
        mod_info = self.create_empty_module_info()
        modules = modules or []

        for module_name in bazel_mode.DevicelessTestTarget.PREREQUISITES:
            info = host_module(name=module_name, path='prebuilts')
            mod_info.name_to_module_info[module_name] = info

        for m in modules:
            mod_info.name_to_module_info[m['module_name']] = m

        return mod_info

    def assertSymlinkTo(self, symlink_path, target_path):
        self.assertEqual(symlink_path.resolve(strict=False), target_path)

    def assertTargetInWorkspace(self, name, package=''):
        self.assertInBuildFile(f'name = "{name}"', package=package)

    def assertTargetNotInWorkspace(self, name, package=''):
        build_file = self.workspace_out_path.joinpath(package, 'BUILD.bazel')
        if not build_file.exists():
            return
        self.assertNotIn(f'name = "{name}"', build_file.read_text())

    def assertInBuildFile(self, substring, package=''):
        build_file = self.workspace_out_path.joinpath(package, 'BUILD.bazel')
        self.assertIn(substring, build_file.read_text())

    def assertNotInBuildFile(self, substring, package=''):
        build_file = self.workspace_out_path.joinpath(package, 'BUILD.bazel')
        self.assertNotIn(substring, build_file.read_text())

    def assertFileInWorkspace(self, relative_path, package=''):
        path = self.workspace_out_path.joinpath(package, relative_path)
        self.assertTrue(path.exists())

    def assertFileNotInWorkspace(self, relative_path, package=''):
        path = self.workspace_out_path.joinpath(package, relative_path)
        self.assertFalse(path.exists())


class BasicWorkspaceGenerationTest(GenerationTestFixture):
    """Tests for basic workspace generation and update."""

    def test_generate_workspace_when_nonexistent(self):
        workspace_generator = self.create_workspace_generator()
        shutil.rmtree(workspace_generator.workspace_out_path,
                      ignore_errors=True)

        workspace_generator.generate()

        self.assertTrue(workspace_generator.workspace_out_path.is_dir())

    def test_regenerate_workspace_when_module_info_deleted(self):
        workspace_generator = self.create_workspace_generator()
        workspace_generator.generate()
        workspace_stat = workspace_generator.workspace_out_path.stat()

        workspace_generator.mod_info.mod_info_file_path.unlink()
        workspace_generator = self.create_workspace_generator()
        workspace_generator.generate()

        new_workspace_stat = workspace_generator.workspace_out_path.stat()
        self.assertNotEqual(workspace_stat, new_workspace_stat)

    def test_not_regenerate_workspace_when_module_info_unchanged(self):
        workspace_generator1 = self.create_workspace_generator()
        workspace_generator1.generate()
        workspace_stat = workspace_generator1.workspace_out_path.stat()

        workspace_generator2 = self.create_workspace_generator()
        workspace_generator2.generate()
        new_workspace_stat = workspace_generator2.workspace_out_path.stat()

        self.assertEqual(workspace_stat, new_workspace_stat)

    def test_not_regenerate_workspace_when_module_only_touched(self):
        workspace_generator = self.create_workspace_generator()
        workspace_generator.generate()
        workspace_stat = workspace_generator.workspace_out_path.stat()

        Path(workspace_generator.mod_info.mod_info_file_path).touch()
        workspace_generator = self.create_workspace_generator()
        workspace_generator.generate()

        new_workspace_stat = workspace_generator.workspace_out_path.stat()
        self.assertEqual(workspace_stat, new_workspace_stat)

    def test_regenerate_workspace_when_module_info_changed(self):
        workspace_generator = self.create_workspace_generator()
        workspace_generator.generate()
        workspace_stat = workspace_generator.workspace_out_path.stat()

        mod_info_file_path = workspace_generator.mod_info.mod_info_file_path
        with open(mod_info_file_path, 'a') as f:
            f.write(' ')
        workspace_generator = self.create_workspace_generator()
        workspace_generator.generate()

        new_workspace_stat = workspace_generator.workspace_out_path.stat()
        self.assertNotEqual(workspace_stat, new_workspace_stat)

    def test_regenerate_workspace_when_md5_file_removed(self):
        workspace_generator = self.create_workspace_generator()
        workspace_generator.generate()
        workspace_stat = workspace_generator.workspace_out_path.stat()

        workspace_generator.mod_info.mod_info_file_path.unlink()
        workspace_generator = self.create_workspace_generator()
        workspace_generator.generate()

        new_workspace_stat = workspace_generator.workspace_out_path.stat()
        self.assertNotEqual(workspace_stat, new_workspace_stat)

    def test_scrub_old_workspace_when_regenerating(self):
        workspace_generator = self.create_workspace_generator()
        workspace_generator.generate()
        some_file = workspace_generator.workspace_out_path.joinpath('some_file')
        some_file.touch()
        self.assertTrue(some_file.is_file())

        # Remove the md5 file to regenerate the workspace.
        workspace_generator.mod_info.mod_info_file_path.unlink()
        workspace_generator = self.create_workspace_generator()
        workspace_generator.generate()

        self.assertFalse(some_file.is_file())

    def test_generate_workspace_file(self):
        gen = self.create_workspace_generator()

        gen.generate()

        self.assertTrue(gen.workspace_out_path.joinpath('WORKSPACE').exists())

    def test_generate_bazelrc_file(self):
        gen = self.create_workspace_generator()
        bazelrc_path = gen.workspace_out_path.joinpath('.bazelrc')

        gen.generate()

        self.assertSymlinkTo(
            bazelrc_path,
            self.src_root_path.joinpath('tools/asuite/atest/bazel/bazelrc')
        )

    def test_generate_rules_dir(self):
        gen = self.create_workspace_generator()
        rules_dir_path = gen.workspace_out_path.joinpath('bazel/rules')

        gen.generate()

        self.assertSymlinkTo(
            rules_dir_path,
            self.src_root_path.joinpath('tools/asuite/atest/bazel/rules')
        )

    def test_generate_host_unit_test_module_target(self):
        mod_info = self.create_module_info(modules=[
            host_unit_test_module(name='hello_world_test')
        ])

        self.run_generator(mod_info)

        self.assertTargetInWorkspace('hello_world_test_host')

    def test_not_generate_host_test_module_target(self):
        mod_info = self.create_module_info(modules=[
            host_test_module(name='hello_world_test'),
        ])

        self.run_generator(mod_info)

        self.assertTargetNotInWorkspace('hello_world_test')


class HostUnitTestModuleTestTargetGenerationTest(GenerationTestFixture):
    """Tests for host unit test module test target generation."""

    def test_generate_deviceless_test_import(self):
        mod_info = self.create_module_info(modules=[
            host_unit_test_module(name='hello_world_test'),
        ])

        self.run_generator(mod_info)

        self.assertInBuildFile(
            'load("//bazel/rules:tradefed_test.bzl",'
            ' "tradefed_deviceless_test")\n'
        )

    def test_generate_deviceless_test_target(self):
        mod_info = self.create_module_info(modules=[
            host_unit_test_module(
                name='hello_world_test', path='example/tests'),
        ])

        self.run_generator(mod_info)

        self.assertInBuildFile(
            'tradefed_deviceless_test(\n'
            '    name = "hello_world_test_host",\n'
            '    test = "//example/tests:hello_world_test",\n'
            ')',
            package='example/tests',
        )

    def test_generate_test_module_prebuilt(self):
        mod_info = self.create_module_info(modules=[
            host_unit_test_module(name='hello_world_test'),
        ])

        self.run_generator(mod_info)

        self.assertTargetInWorkspace('hello_world_test')

    def test_raise_when_prerequisite_not_in_module_info(self):
        mod_info = self.create_module_info(modules=[
            host_unit_test_module(),
        ])
        del mod_info.name_to_module_info['adb']

        with self.assertRaises(Exception) as context:
            self.run_generator(mod_info)

        self.assertIn('adb', str(context.exception))

    def test_raise_when_prerequisite_module_missing_path(self):
        mod_info = self.create_module_info(modules=[
            host_unit_test_module(),
        ])
        mod_info.name_to_module_info['adb'].get('path').clear()

        with self.assertRaises(Exception) as context:
            self.run_generator(mod_info)

        self.assertIn('adb', str(context.exception))


class ModulePrebuiltTargetGenerationTest(GenerationTestFixture):
    """Tests for module prebuilt target generation."""

    def test_generate_prebuilt_import(self):
        mod_info = self.create_module_info(modules=[
            supported_test_module(),
        ])

        self.run_generator(mod_info)

        self.assertInBuildFile(
            'load("//bazel/rules:soong_prebuilt.bzl", "soong_prebuilt")\n'
        )

    def test_generate_prebuilt_target_for_multi_config_test_module(self):
        mod_info = self.create_module_info(modules=[
            multi_config(supported_test_module(name='libhello')),
        ])

        self.run_generator(mod_info)

        self.assertInBuildFile(
            'soong_prebuilt(\n'
            '    name = "libhello",\n'
            '    files = select({\n'
            '        "//bazel/rules:device": glob(["libhello/device/**/*"]),\n'
            '        "//bazel/rules:host": glob(["libhello/host/**/*"]),\n'
            '    }),\n'
            '    module_name = "libhello",\n'
            ')\n'
        )

    def test_create_symlinks_to_testcases_for_multi_config_test_module(self):
        module_name = 'hello_world_test'
        mod_info = self.create_module_info(modules=[
            multi_config(supported_test_module(name=module_name))
        ])
        module_out_path = self.workspace_out_path.joinpath(module_name)

        self.run_generator(mod_info)

        self.assertSymlinkTo(
            module_out_path.joinpath(f'host/testcases/{module_name}'),
            self.host_out_path.joinpath(f'testcases/{module_name}'))
        self.assertSymlinkTo(
            module_out_path.joinpath(f'device/testcases/{module_name}'),
            self.product_out_path.joinpath(f'testcases/{module_name}'))

    def test_generate_files_for_host_only_test_module(self):
        mod_info = self.create_module_info(modules=[
            host_only_config(supported_test_module(name='test1')),
        ])

        self.run_generator(mod_info)

        self.assertInBuildFile(
            '    files = select({\n'
            '        "//bazel/rules:host": glob(["test1/host/**/*"]),\n'
            '    }),\n'
        )

    def test_generate_files_for_device_only_test_module(self):
        mod_info = self.create_module_info(modules=[
            device_only_config(supported_test_module(name='test1')),
        ])

        self.run_generator(mod_info)

        self.assertInBuildFile(
            '    files = select({\n'
            '        "//bazel/rules:device": glob(["test1/device/**/*"]),\n'
            '    }),\n'
        )

    def test_not_create_device_symlinks_for_host_only_test_module(self):
        mod_info = self.create_module_info(modules=[
            host_only_config(supported_test_module(name='test1')),
        ])

        self.run_generator(mod_info)

        self.assertFileNotInWorkspace('test1/device')

    def test_not_create_host_symlinks_for_device_test_module(self):
        mod_info = self.create_module_info(modules=[
            device_only_config(supported_test_module(name='test1')),
        ])

        self.run_generator(mod_info)

        self.assertFileNotInWorkspace('test1/host')


class ModuleSharedLibGenerationTest(GenerationTestFixture):
    """Tests for module shared libs target generation."""

    def test_generate_runtime_deps_per_shared_lib_config(self):
        mod_info = self.create_module_info(modules=[
            supported_test_module(shared_libs=[
                'libhost',
                'libdevice',
                'libmulti'
            ]),
            host_module(name='libhost'),
            device_module(name='libdevice'),
            multi_config_module(name='libmulti'),
        ])

        self.run_generator(mod_info)

        self.assertInBuildFile(
            '    runtime_deps = select({\n'
            '        "//bazel/rules:device": [\n'
            '            "//:libdevice",\n'
            '            "//:libmulti",\n'
            '        ],\n'
            '        "//bazel/rules:host": [\n'
            '            "//:libhost",\n'
            '            "//:libmulti",\n'
            '        ],\n'
            '    }),\n'
        )

    def test_generate_runtime_deps_in_order(self):
        mod_info = self.create_module_info(modules=[
            supported_test_module(shared_libs=['libhello2', 'libhello1']),
            host_module(name='libhello1'),
            host_module(name='libhello2'),
        ])

        self.run_generator(mod_info)

        self.assertInBuildFile(
            '            "//:libhello1",\n'
            '            "//:libhello2",\n'
        )

    def test_generate_target_for_shared_lib(self):
        mod_info = self.create_module_info(modules=[
            supported_test_module(shared_libs=['libhello']),
            host_module(name='libhello'),
        ])

        self.run_generator(mod_info)

        self.assertTargetInWorkspace('libhello')

    def test_not_generate_for_missing_shared_lib_module(self):
        mod_info = self.create_module_info(modules=[
            supported_test_module(shared_libs=['libhello'])
        ])

        self.run_generator(mod_info)

        self.assertNotInBuildFile('            "//:libhello",\n')
        self.assertTargetNotInWorkspace('libhello')

    def test_not_generate_for_uninstalled_shared_lib(self):
        mod_info = self.create_module_info(modules=[
            supported_test_module(shared_libs=['libhello']),
            host_module(name='libhello', installed=[]),
        ])

        self.run_generator(mod_info)

        self.assertNotInBuildFile('            "//:libhello",\n')
        self.assertTargetNotInWorkspace('libhello')

    def test_raise_when_shared_lib_install_path_for_unsupported_config(self):
        unsupported_install_path = 'out/other'
        mod_info = self.create_module_info(modules=[
            supported_test_module(shared_libs=['libhello']),
            module('libhello', installed=[unsupported_install_path]),
        ])

        with self.assertRaises(Exception) as context:
            self.run_generator(mod_info)

        self.assertIn(unsupported_install_path, str(context.exception))

    def test_raise_when_shared_lib_module_install_path_ambiguous(self):
        ambiguous_install_path = 'out/f1'
        mod_info = self.create_module_info(modules=[
            supported_test_module(shared_libs=['libhello']),
            module(name='libhello', installed=[ambiguous_install_path]),
        ])

        with self.assertRaises(Exception):
            self.run_generator(mod_info)


class SharedLibPrebuiltTargetGenerationTest(GenerationTestFixture):
    """Tests for runtime dependency module prebuilt target generation."""

    def test_create_multi_config_target_symlinks(self):
        host_file1 = self.host_out_path.joinpath('a/b/f1')
        host_file2 = self.host_out_path.joinpath('a/c/f2')
        device_file1 = self.product_out_path.joinpath('a/b/f1')
        mod_info = self.create_module_info(modules=[
            supported_test_module(shared_libs=['libhello']),
            multi_config_module(
                name='libhello',
                installed=[str(host_file1), str(host_file2), str(device_file1)]
            )
        ])
        package_path = self.workspace_out_path

        self.run_generator(mod_info)

        self.assertSymlinkTo(
            package_path.joinpath('libhello/host/a/b/f1'), host_file1)
        self.assertSymlinkTo(
            package_path.joinpath('libhello/host/a/c/f2'), host_file2)
        self.assertSymlinkTo(
            package_path.joinpath('libhello/device/a/b/f1'), device_file1)

    def test_generate_for_host_only_shared_lib_dependency(self):
        mod_info = self.create_module_info(modules=[
            supported_test_module(shared_libs=['libhello']),
            host_module(name='libhello'),
        ])

        self.run_generator(mod_info)

        self.assertInBuildFile(
            '    files = select({\n'
            '        "//bazel/rules:host": glob(["libhello/host/**/*"]),\n'
            '    }),\n'
        )
        self.assertFileNotInWorkspace('libhello/device')

    def test_generate_for_device_only_shared_lib_dependency(self):
        mod_info = self.create_module_info(modules=[
            supported_test_module(shared_libs=['libhello']),
            device_module(name='libhello'),
        ])

        self.run_generator(mod_info)

        self.assertInBuildFile(
            '    files = select({\n'
            '        "//bazel/rules:device": glob(["libhello/device/**/*"]),\n'
            '    }),\n'
        )
        self.assertFileNotInWorkspace('libhello/host')


@mock.patch.dict('os.environ', {constants.ANDROID_BUILD_TOP:'/'})
def create_empty_module_info():
    with fake_filesystem_unittest.Patcher() as patcher:
        # pylint: disable=protected-access
        fake_temp_file_name = next(tempfile._get_candidate_names())
        patcher.fs.create_file(fake_temp_file_name, contents='{}')
        return module_info.ModuleInfo(module_file=fake_temp_file_name)


def create_module_info(modules=None):
    mod_info = create_empty_module_info()
    modules = modules or []

    for m in modules:
        mod_info.name_to_module_info[m['module_name']] = m

    return mod_info


def host_unit_test_module(**kwargs):
    return host_unit_suite(host_test_module(**kwargs))


# We use the below alias in situations where the actual type is irrelevant to
# the test as long as it is supported in Bazel mode.
supported_test_module = host_unit_test_module


def host_test_module(**kwargs):
    kwargs.setdefault('name', 'hello_world_test')
    return host_only_config(test_module(**kwargs))


def host_module(**kwargs):
    m = module(**kwargs)

    if 'installed' in kwargs:
        return m

    return host_only_config(m)


def device_module(**kwargs):
    m = module(**kwargs)

    if 'installed' in kwargs:
        return m

    return device_only_config(m)


def multi_config_module(**kwargs):
    m = module(**kwargs)

    if 'installed' in kwargs:
        return m

    return multi_config(m)


def test_module(**kwargs):
    kwargs.setdefault('name', 'hello_world_test')
    return test(module(**kwargs))


def module(name=None, path=None, shared_libs=None, installed=None):
    name = name or 'libhello'

    m = {}

    m['module_name'] = name
    m['path'] = [path or '']
    m['installed'] = installed or []
    m['test_class'] = []
    m['dependencies'] = []
    m['is_unit_test'] = 'false'
    m['shared_libs'] = shared_libs or []

    return m


def test(info):
    info['auto_test_config'] = ['true']
    return info


def host_unit_suite(info):
    info = test(info)
    info.setdefault('compatibility_suites', []).append('host-unit-tests')
    return info


def multi_config(info):
    name = info.get('module_name', 'lib')
    info['installed'] = [
        f'out/host/linux-x86/{name}/{name}.jar',
        f'out/product/vsoc_x86/{name}/{name}.apk',
    ]
    return info


def host_only_config(info):
    name = info.get('module_name', 'lib')
    info['installed'] = [
        f'out/host/linux-x86/{name}/{name}.jar',
    ]
    return info


def device_only_config(info):
    name = info.get('module_name', 'lib')
    info['installed'] = [
        f'out/product/vsoc_x86/{name}/{name}.jar',
    ]
    return info


class PackageTest(fake_filesystem_unittest.TestCase):
    """Tests for Package."""

    class FakeTarget(bazel_mode.Target):
        """Fake target used for tests."""

        def __init__(self, name, imports=None):
            self._name = name
            self._imports = imports or set()

        def name(self):
            return self._name

        def required_imports(self):
            return self._imports

        def write_to_build_file(self, f):
            f.write(f'{self._name}\n')


    def setUp(self):
        self.setUpPyfakefs()
        self.workspace_out_path = Path('/workspace_out_path')
        self.workspace_out_path.mkdir()

    def test_raise_when_adding_existing_target(self):
        target_name = '<fake_target>'
        package = bazel_mode.Package('p')
        package.add_target(self.FakeTarget(target_name))

        with self.assertRaises(Exception) as context:
            package.add_target(self.FakeTarget(target_name))

        self.assertIn(target_name, str(context.exception))

    def test_write_build_file_in_package_dir(self):
        package_path = 'abc/def'
        package = bazel_mode.Package(package_path)
        expected_path = self.workspace_out_path.joinpath(
            package_path, 'BUILD.bazel')

        package.generate(self.workspace_out_path)

        self.assertTrue(expected_path.exists())

    def test_write_load_statements_in_sorted_order(self):
        package = bazel_mode.Package('p')
        target1 = self.FakeTarget('target1', imports={
            bazel_mode.Import('z.bzl', 'symbol1'),
        })
        target2 = self.FakeTarget('target2', imports={
            bazel_mode.Import('a.bzl', 'symbol2'),
        })
        package.add_target(target1)
        package.add_target(target2)

        package.generate(self.workspace_out_path)

        self.assertIn('load("a.bzl", "symbol2")\nload("z.bzl", "symbol1")\n\n',
                      self.package_build_file_text(package))

    def test_write_load_statements_with_symbols_grouped_by_bzl(self):
        package = bazel_mode.Package('p')
        target1 = self.FakeTarget('target1', imports={
            bazel_mode.Import('a.bzl', 'symbol1'),
            bazel_mode.Import('a.bzl', 'symbol3'),
        })
        target2 = self.FakeTarget('target2', imports={
            bazel_mode.Import('a.bzl', 'symbol2'),
        })
        package.add_target(target1)
        package.add_target(target2)

        package.generate(self.workspace_out_path)

        self.assertIn('load("a.bzl", "symbol1", "symbol2", "symbol3")\n\n',
                      self.package_build_file_text(package))

    def test_write_targets_in_add_order(self):
        package = bazel_mode.Package('p')
        target1 = self.FakeTarget('target1')
        target2 = self.FakeTarget('target2')
        package.add_target(target2)  # Added out of order.
        package.add_target(target1)

        package.generate(self.workspace_out_path)

        self.assertIn('target2\n\ntarget1\n',
                      self.package_build_file_text(package))

    def test_generate_parent_package_when_nested_exists(self):
        parent_path = Path('parent')
        parent = bazel_mode.Package(parent_path.name)
        nested = bazel_mode.Package(parent_path.joinpath('nested'))
        nested.generate(self.workspace_out_path)

        parent.generate(self.workspace_out_path)

        self.assertTrue(self.workspace_out_path.joinpath(parent_path).is_dir())

    def package_build_file_text(self, package):
        return self.workspace_out_path.joinpath(package.path,
                                                'BUILD.bazel').read_text()


class DecorateFinderMethodTest(fake_filesystem_unittest.TestCase):
    """Tests for _decorate_find_method()."""

    def setUp(self):
        self.setUpPyfakefs()

    # pylint: disable=protected-access
    # TODO(b/197600827): Add self._env in Module_info instead of mocking
    #                    os.environ directly.
    @mock.patch.dict('os.environ', {constants.ANDROID_BUILD_TOP:'/'})
    def test_unit_test_runner_is_overridden(self):
        original_find_method = lambda obj, test_id:(
            self.create_single_test_infos(obj, test_id, test_name=MODULE_NAME,
                                          runner=ATEST_TF_RUNNER))
        mod_info = self.create_single_test_module_info(MODULE_NAME,
                                                  is_unit_test=True)
        new_find_method = bazel_mode._decorate_find_method(
            mod_info, original_find_method)

        test_infos = new_find_method('finder_obj', 'test_id')

        self.assertEqual(len(test_infos), 1)
        self.assertEqual(test_infos[0].test_runner, BAZEL_RUNNER)

    # pylint: disable=protected-access
    @mock.patch.dict('os.environ', {constants.ANDROID_BUILD_TOP:'/'})
    def test_not_unit_test_runner_is_preserved(self):
        original_find_method = lambda obj, test_id:(
            self.create_single_test_infos(obj, test_id, test_name=MODULE_NAME,
                                          runner=ATEST_TF_RUNNER))
        mod_info = self.create_single_test_module_info(
            MODULE_NAME, is_unit_test=False)
        new_find_method = bazel_mode._decorate_find_method(
            mod_info, original_find_method)

        test_infos = new_find_method('finder_obj', 'test_id')

        self.assertEqual(len(test_infos), 1)
        self.assertEqual(test_infos[0].test_runner, ATEST_TF_RUNNER)

    # pylint: disable=unused-argument
    def create_single_test_infos(self, obj, test_id, test_name=MODULE_NAME,
                                 runner=ATEST_TF_RUNNER):
        """Create list of test_info.TestInfo."""
        return [test_info.TestInfo(test_name, runner, MODULE_BUILD_TARGETS)]

    def create_single_test_module_info(self, module_name, is_unit_test=True):
        """Create module-info file with single module."""
        compatibility_suites = '["host-unit-tests"]'
        if not is_unit_test:
            compatibility_suites = "[]"
        unit_test_mod_info_content = ('{"%s": {"class": ["NATIVE_TESTS"],' +
                                      ' "compatibility_suites": %s }}') % (
                                          module_name, compatibility_suites)
        fake_temp_file_name = next(tempfile._get_candidate_names())
        self.fs.create_file(fake_temp_file_name,
                            contents=unit_test_mod_info_content)
        return module_info.ModuleInfo(module_file=fake_temp_file_name)


class BazelTestRunnerTest(unittest.TestCase):
    """Tests for BazelTestRunner."""

    def test_return_empty_build_reqs_when_no_test_infos(self):
        run_command = self.mock_run_command(side_effect=Exception(''))
        runner = self.create_bazel_test_runner(
            modules=[
                supported_test_module(name='test1', path='path1'),
            ],
            test_infos=[],
            run_command=run_command,
        )

        reqs = runner.get_test_runner_build_reqs()

        self.assertFalse(reqs)

    def test_query_bazel_test_targets_deps_for_build_reqs(self):
        run_command = self.mock_run_command()
        runner = self.create_bazel_test_runner(
            modules=[
                supported_test_module(name='test1', path='path1'),
                supported_test_module(name='test2', path='path2')
            ],
            test_infos = [
                test_info_of('test2'),
                test_info_of('test1'),  # Intentionally out of order.
            ],
            run_command=run_command,
        )

        runner.get_test_runner_build_reqs()

        call_args = run_command.call_args[0][0]
        self.assertIn(
            'deps(tests(//path1:test1_host + //path2:test2_host))',
            call_args,
        )

    def test_trim_whitespace_in_bazel_query_output(self):
        run_command = self.mock_run_command(
            return_value='\n'.join(['  test1  ', 'test2  ', '  ']))
        runner = self.create_bazel_test_runner(
            modules=[
                supported_test_module(name='test1', path='path1'),
            ],
            test_infos = [test_info_of('test1')],
            run_command=run_command,
        )

        reqs = runner.get_test_runner_build_reqs()

        self.assertSetEqual({'test1', 'test2'}, reqs)

    def test_generate_single_run_command(self):
        test_infos = [test_info_of('test1')]
        runner = self.create_bazel_test_runner_for_tests(test_infos)

        cmd = runner.generate_run_commands(test_infos, {})

        self.assertEqual(1, len(cmd))

    def test_generate_run_command_containing_targets(self):
        test_infos = [test_info_of('test1'), test_info_of('test2')]
        runner = self.create_bazel_test_runner_for_tests(test_infos)

        cmd = runner.generate_run_commands(test_infos, {})

        self.assertTokensIn(['//path:test1_host', '//path:test2_host'], cmd[0])

    def create_bazel_test_runner(self, modules, test_infos, run_command=None):
        return bazel_mode.BazelTestRunner(
            'result_dir',
            mod_info=create_module_info(modules),
            test_infos=test_infos,
            src_top=Path('/src'),
            workspace_path=Path('/src/workspace'),
            run_command=run_command or self.mock_run_command()
        )

    def create_bazel_test_runner_for_tests(self, test_infos):
        return self.create_bazel_test_runner(
            modules=[supported_test_module(name=t.test_name, path='path')
                     for t in test_infos],
            test_infos=test_infos
        )

    def mock_run_command(self, **kwargs):
        return mock.create_autospec(bazel_mode.default_run_command, **kwargs)

    def assertTokensIn(self, expected_tokens, s):
        tokens = shlex.split(s)
        for token in expected_tokens:
            self.assertIn(token, tokens)


def test_info_of(module_name):
    return test_info.TestInfo(module_name, BAZEL_RUNNER, [])


if __name__ == '__main__':
    unittest.main()
