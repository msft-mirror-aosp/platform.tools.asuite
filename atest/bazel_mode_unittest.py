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

import io
import shutil
import tempfile
import unittest

from unittest import mock
from pathlib import Path
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


class WorkspaceGeneratorTest(fake_filesystem_unittest.TestCase):
    """Tests for WorkspaceGenerator."""

    def setUp(self):
        self.setUpPyfakefs()

        self.src_root_path = Path('/src')

        self.out_dir_path = self.src_root_path.joinpath('out')
        self.out_dir_path.mkdir(parents=True)

        self.product_out_path = self.out_dir_path.joinpath('product')
        self.host_out_path = self.out_dir_path.joinpath('host')
        self.workspace_out_path = self.out_dir_path.joinpath('workspace')

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
        workspace_generator = self.create_workspace_generator()
        workspace_generator.generate()
        workspace_stat = workspace_generator.workspace_out_path.stat()

        workspace_generator = self.create_workspace_generator()
        workspace_generator.generate()

        new_workspace_stat = workspace_generator.workspace_out_path.stat()
        self.assertEqual(workspace_stat, new_workspace_stat)

    def test_not_regenerate_worksapce_when_module_only_touched(self):
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

        mod_info_file_path =  workspace_generator.mod_info.mod_info_file_path
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
        some_file = workspace_generator.workspace_out_path.joinpath("some_file")
        some_file.touch()
        self.assertTrue(some_file.is_file())

        # Remove the md5 file to regenerate workspace.
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

    def test_raise_when_prerequisite_module_not_in_module_info(self):
        module_name = 'libhello'
        gen = self.create_workspace_generator(
            prerequisites=[module_name], modules=[])

        with self.assertRaises(Exception) as context:
            gen.generate()

        self.assertIn(module_name, str(context.exception))

    def test_raise_when_prerequisite_module_missing_path(self):
        module_name = 'libhello'
        module = self.create_module(module_name)
        module.get('path').clear()
        gen = self.create_workspace_generator(
            prerequisites=[module_name], modules=[module])

        with self.assertRaises(Exception) as context:
            gen.generate()

        self.assertIn(module_name, str(context.exception))

    def test_write_build_file_in_package_dir(self):
        module_name = 'libhello'
        module_path = 'example/tests'
        module = self.create_module(module_name)
        module['path'] = [module_path]
        gen = self.create_workspace_generator(
            prerequisites=[module_name], modules=[module])
        expected_path = self.workspace_out_path.joinpath(module_path,
                                                         'BUILD.bazel')

        gen.generate()

        self.assertTrue(expected_path.is_file())

    def test_generate_host_unit_test_module(self):
        module = self.create_host_unit_test_module()
        gen = self.create_workspace_generator(modules=[module])
        expected_path = self.expected_package_path(module)

        gen.generate()

        self.assertTrue(expected_path.is_dir())

    def test_not_generate_non_host_unit_test_module(self):
        module = self.create_host_unit_test_module()
        module['compatibility_suites'].clear()
        gen = self.create_workspace_generator(modules=[module])
        expected_path = self.expected_package_path(module)

        gen.generate()

        self.assertFalse(expected_path.is_dir())

    def test_not_generate_non_testable_host_unit_test_module(self):
        module = self.create_host_unit_test_module()
        module['auto_test_config'].clear()
        gen = self.create_workspace_generator(modules=[module])
        expected_path = self.expected_package_path(module)

        gen.generate()

        self.assertFalse(expected_path.is_dir())

    def test_generate_shared_lib_for_dependent_target(self):
        lib_module_name = 'libhello'
        lib_module = self.create_module(lib_module_name)
        module = self.create_host_unit_test_module()
        module['shared_libs'] = [lib_module_name]
        gen = self.create_workspace_generator(modules=[module, lib_module])

        gen.generate()

        self.assertInModuleBuildFile(f'name = "{lib_module_name}"',
                                     lib_module)

    def test_not_generate_uninstalled_shared_lib_target(self):
        lib_module_name = 'libhello'
        lib_module = self.create_module(lib_module_name)
        lib_module['installed'] = []
        module = self.create_host_unit_test_module()
        module['shared_libs'] = [lib_module_name]
        gen = self.create_workspace_generator(modules=[module, lib_module])
        expected_path = self.expected_package_path(lib_module)

        gen.generate()

        self.assertFalse(expected_path.joinpath('BUILD.bazel').is_file())

    def create_workspace_generator(self, prerequisites=None, mod_info=None,
                                   modules=None):
        prerequisites = prerequisites or []
        mod_info = mod_info or self.create_empty_module_info()
        modules = modules or []

        for m in modules:
            mod_info.name_to_module_info[m['module_name']] = m

        generator = bazel_mode.WorkspaceGenerator(
            self.src_root_path,
            self.workspace_out_path,
            self.product_out_path,
            self.host_out_path,
            self.out_dir_path,
            mod_info
        )

        generator.prerequisite_modules = prerequisites

        return generator

    # pylint: disable=protected-access
    @mock.patch.dict('os.environ', {constants.ANDROID_BUILD_TOP:'/'})
    def create_empty_module_info(self):
        fake_temp_file_name = next(tempfile._get_candidate_names())
        self.fs.create_file(fake_temp_file_name, contents='{}')
        return module_info.ModuleInfo(module_file=fake_temp_file_name)

    def create_module(self, name='libhello'):
        module = {}

        module["module_name"] = name
        module['path'] = ['src/%s' % name]
        module['installed'] = [str(self.host_out_path.joinpath(name))]
        module["test_class"] = []
        module["dependencies"] = []
        module["is_unit_test"] = 'false'

        return module


    def create_host_unit_test_module(self, name='hello_test'):
        module = self.create_module(name)

        module['compatibility_suites'] = ["host-unit-tests"]
        module['auto_test_config'] = ["true"]

        return module

    def expected_package_path(self, module):
        return self.workspace_out_path.joinpath(module['path'][0])

    def assertSymlinkTo(self, symlink_path, target_path):
        self.assertEqual(symlink_path.resolve(strict=False), target_path)

    def assertInModuleBuildFile(self, compare_str, module):
        module_build_file = self.expected_package_path(module).joinpath(
            'BUILD.bazel')
        self.assertTrue(module_build_file.is_file())
        self.assertIn(compare_str, module_build_file.read_text())


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


class DevicelessTestTargetTest(unittest.TestCase):
    """Tests for DevicelessTestTarget."""

    def test_create_for_test_target(self):
        module_name = 'hello_test'
        target = bazel_mode.DevicelessTestTarget.create(
            module_name + '_host', 'package_name', module_name)
        f = io.StringIO()

        target.write_to_build_file(f)

        self.assertIn(
            'tradefed_deviceless_test(\n'
            '    name = "hello_test_host",\n'
            '    test = ":hello_test",\n'
            ')',
            f.getvalue())


class SoongPrebuiltTargetTest(fake_filesystem_unittest.TestCase):
    """Tests for SoongPrebuiltTarget."""

    def setUp(self):
        self.setUpPyfakefs()

        self.src_root_path = Path('/src')

        self.out_dir_path = self.src_root_path.joinpath('out')
        self.out_dir_path.mkdir(parents=True)

        self.product_out_path = self.out_dir_path.joinpath('product')
        self.host_out_path = self.out_dir_path.joinpath('host')
        self.workspace_out_path = self.out_dir_path.joinpath('workspace')

        # TODO: Remove SoongPrebuiltTarget's dependency on the generator.
        self.gen = self.create_workspace_generator()

    def test_raise_when_module_missing_install_path(self):
        module_name = 'libhello'
        module = self.create_module(module_name)
        module['installed'].clear()

        with self.assertRaises(Exception) as context:
            bazel_mode.SoongPrebuiltTarget.create(self.gen, module)

        self.assertIn(module_name, str(context.exception))

    def test_raise_when_module_install_path_for_other_config(self):
        invalid_install_path = str(self.out_dir_path.parent.joinpath('other'))
        module = self.create_module('libhello')
        module['installed'] = [invalid_install_path]

        with self.assertRaises(Exception) as context:
            bazel_mode.SoongPrebuiltTarget.create(self.gen, module)

        self.assertIn(invalid_install_path, str(context.exception))

    def test_raise_when_module_install_path_ambiguous(self):
        module_name = 'libhello'
        module = self.create_module(module_name)
        module['installed'] = [
            str(self.out_dir_path.joinpath('f1')),
        ]

        with self.assertRaises(Exception):
            bazel_mode.SoongPrebuiltTarget.create(self.gen, module)

    def test_write_multi_config_target(self):
        module_name = 'libhello'
        module = self.create_module(module_name)
        module['installed'] = [
            str(self.host_out_path.joinpath(module_name)),
            str(self.product_out_path.joinpath(module_name)),
        ]
        target = self.create_target(module)
        f = io.StringIO()

        target.write_to_build_file(f)

        self.assertIn(
            'soong_prebuilt(\n'
            '    name = "libhello",\n'
            '    files = select({\n'
            '        "//bazel/rules:device": glob(["libhello/device/**/*"]),\n'
            '        "//bazel/rules:host": glob(["libhello/host/**/*"]),\n'
            '    }),\n'
            '    module_name = "libhello",\n'
            ')\n',
            f.getvalue())

    def test_not_write_device_condition_for_host_module(self):
        module_name = 'libhello'
        module = self.create_module(module_name)
        module['installed'] = [
            str(self.host_out_path.joinpath(module_name)),
        ]
        target = self.create_target(module)
        f = io.StringIO()

        target.write_to_build_file(f)

        self.assertNotIn('"//bazel/rules:device"', f.getvalue())

    def test_not_write_host_condition_for_device_module(self):
        module_name = 'libhello'
        module = self.create_module(module_name)
        module['installed'] = [
            str(self.product_out_path.joinpath(module_name)),
        ]
        target = self.create_target(module)
        f = io.StringIO()

        target.write_to_build_file(f)

        self.assertNotIn('"//bazel/rules:host"', f.getvalue())

    def test_create_multi_config_target_symlinks(self):
        module_name = 'libhello'
        module = self.create_module(module_name)
        host_file1 = self.host_out_path.joinpath('a/b/f1')
        host_file2 = self.host_out_path.joinpath('a/c/f2')
        device_file1 = self.product_out_path.joinpath('a/b/f1')
        module['installed'] = [
            str(host_file1),
            str(host_file2),
            str(device_file1),
        ]
        target = self.create_target(module)
        module_out_path = self.out_dir_path.joinpath(module_name)

        target.create_filesystem_layout(self.out_dir_path)

        self.assertSymlinkTo(
            module_out_path.joinpath('host/a/b/f1'), host_file1)
        self.assertSymlinkTo(
            module_out_path.joinpath('host/a/c/f2'), host_file2)
        self.assertSymlinkTo(
            module_out_path.joinpath('device/a/b/f1'), device_file1)

    def test_not_create_device_symlinks_for_host_module(self):
        module_name = 'libhello'
        module = self.create_module(module_name)
        module['installed'] = [
            str(self.host_out_path.joinpath('a/b/f1')),
        ]
        target = self.create_target(module)
        module_out_path = self.out_dir_path.joinpath(module_name)

        target.create_filesystem_layout(self.out_dir_path)

        self.assertFalse(module_out_path.joinpath('device').exists())

    def test_not_create_host_symlinks_for_device_module(self):
        module_name = 'libhello'
        module = self.create_module(module_name)
        module['installed'] = [
            str(self.product_out_path.joinpath('a/b/f1')),
        ]
        target = self.create_target(module)
        module_out_path = self.out_dir_path.joinpath(module_name)

        target.create_filesystem_layout(self.out_dir_path)

        self.assertFalse(module_out_path.joinpath('host').exists())

    def test_create_symlinks_to_testcases_for_test_module(self):
        module_name = 'hello_test'
        module = self.create_module(module_name)
        module['installed'] = [
            str(self.host_out_path.joinpath('a/b/f1')),
            str(self.product_out_path.joinpath('a/b/f1')),
        ]
        target = self.create_target(module, test_module=True)
        module_out_path = self.out_dir_path.joinpath(module_name)

        target.create_filesystem_layout(self.out_dir_path)

        self.assertSymlinkTo(
            module_out_path.joinpath(f'host/testcases/{module_name}'),
            self.host_out_path.joinpath(f'testcases/{module_name}'))
        self.assertSymlinkTo(
            module_out_path.joinpath(f'device/testcases/{module_name}'),
            self.product_out_path.joinpath(f'testcases/{module_name}'))

    def test_not_create_device_symlinks_for_host_test_module(self):
        module_name = 'hello_test'
        module = self.create_module(module_name)
        module['installed'] = [
            str(self.host_out_path.joinpath('a/b/f1')),
        ]
        target = self.create_target(module, test_module=True)
        module_out_path = self.out_dir_path.joinpath(module_name)

        target.create_filesystem_layout(self.out_dir_path)

        self.assertFalse(module_out_path.joinpath('device').exists())

    def test_not_create_host_symlinks_for_device_test_module(self):
        module_name = 'hello_test'
        module = self.create_module(module_name)
        module['installed'] = [
            str(self.product_out_path.joinpath('a/b/f1')),
        ]
        target = self.create_target(module, test_module=True)
        module_out_path = self.out_dir_path.joinpath(module_name)

        target.create_filesystem_layout(self.out_dir_path)

        self.assertFalse(module_out_path.joinpath('host').exists())

    def test_write_multi_config_runtime_deps(self):
        lib1_name = 'libhello'
        lib1_module = self.create_module(lib1_name)
        lib1_module['installed'] = [
            str(self.host_out_path.joinpath(lib1_name)),
            str(self.product_out_path.joinpath(lib1_name)),
        ]
        lib2_name = 'libhello2'
        lib2_module = self.create_module(lib2_name)
        lib2_module['installed'] = [
            str(self.product_out_path.joinpath(lib2_name)),
        ]
        module_name = 'hello_test'
        module = self.create_module(module_name)
        target = self.create_target(
            module, runtime_dep_targets=[self.create_target(lib1_module),
                                         self.create_target(lib2_module)])
        f = io.StringIO()

        target.write_to_build_file(f)

        self.assertIn(
            '    runtime_deps = select({\n'
            '        "//bazel/rules:device": [\n'
            '            "//src/libhello2:libhello2",\n'
            '            "//src/libhello:libhello",\n'
            '        ],\n'
            '        "//bazel/rules:host": [\n'
            '            "//src/libhello:libhello",\n'
            '        ],\n'
            '    }),\n',
            f.getvalue())

    def test_write_runtime_deps_in_order(self):
        lib1_name = '1_libhello'
        lib1_module = self.create_module(lib1_name)
        lib2_name = '2_libhello'
        lib2_module = self.create_module(lib2_name)
        module_name = 'hello_test'
        module = self.create_module(module_name)
        target = self.create_target(
            module, runtime_dep_targets=[self.create_target(lib1_module),
                                         self.create_target(lib2_module)])
        f = io.StringIO()

        target.write_to_build_file(f)

        self.assertIn(
            '    runtime_deps = select({\n'
            '        "//bazel/rules:host": [\n'
            '            "//src/1_libhello:1_libhello",\n'
            '            "//src/2_libhello:2_libhello",\n'
            '        ],\n'
            '    }),',
            f.getvalue())

    def test_not_write_device_condition_for_host_runtime_deps(self):
        lib1_name = 'libhello'
        lib1_module = self.create_module(lib1_name)
        lib1_module['installed'] = [
            str(self.host_out_path.joinpath(lib1_name)),
        ]
        module_name = 'hello_test'
        module = self.create_module(module_name)
        target = self.create_target(
            module, runtime_dep_targets=[self.create_target(lib1_module)])
        f = io.StringIO()

        target.write_to_build_file(f)

        self.assertNotIn(
            '"//bazel/rules:device":',
            f.getvalue())

    def test_not_write_host_condition_for_device_runtime_deps(self):
        lib1_name = 'libhello'
        lib1_module = self.create_module(lib1_name)
        lib1_module['installed'] = [
            str(self.product_out_path.joinpath(lib1_name)),
        ]
        module_name = 'hello_test'
        module = self.create_module(module_name)
        target = self.create_target(
            module, runtime_dep_targets=[self.create_target(lib1_module)])
        f = io.StringIO()

        target.write_to_build_file(f)

        self.assertNotIn(
            '"//bazel/rules:host": [\'//src/libhello:libhello\'],',
            f.getvalue())

    def assertSymlinkTo(self, symlink_path, target_path):
        self.assertEqual(symlink_path.resolve(strict=False), target_path)

    def create_workspace_generator(self):
        mod_info = self.create_empty_module_info()

        generator = bazel_mode.WorkspaceGenerator(
            self.src_root_path,
            self.workspace_out_path,
            self.product_out_path,
            self.host_out_path,
            self.out_dir_path,
            mod_info
        )

        generator.prerequisite_prebuilts = []

        return generator

    # pylint: disable=protected-access
    @mock.patch.dict('os.environ', {constants.ANDROID_BUILD_TOP:'/'})
    def create_empty_module_info(self):
        fake_temp_file_name = next(tempfile._get_candidate_names())
        self.fs.create_file(fake_temp_file_name, contents='{}')
        return module_info.ModuleInfo(module_file=fake_temp_file_name)

    def create_module(self, name):
        module = {}

        module["module_name"] = name
        module['path'] = ['src/%s' % name]
        module['installed'] = [str(self.host_out_path.joinpath(name))]
        module["test_class"] = []
        module["dependencies"] = []
        module["is_unit_test"] = 'false'

        return module

    def create_target(self, module, test_module=False,
                      runtime_dep_targets=None):
        return bazel_mode.SoongPrebuiltTarget.create(
            self.gen, module,
            module['path'][0],
            test_module=test_module,
            runtime_dep_targets=runtime_dep_targets
        )


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
        mod_info = self.create_single_test_module_info(MODULE_NAME,
                                                  is_unit_test=False)
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
        set_as_unit_test = 'true'
        if not is_unit_test:
            set_as_unit_test = 'false'
        unit_test_mod_info_content = ('{"%s": {"class": ["NATIVE_TESTS"],' +
                                      ' "is_unit_test": "%s" }}') % (
                                          module_name, set_as_unit_test)
        fake_temp_file_name = next(tempfile._get_candidate_names())
        self.fs.create_file(fake_temp_file_name,
                            contents=unit_test_mod_info_content)
        return module_info.ModuleInfo(module_file=fake_temp_file_name)


if __name__ == '__main__':
    unittest.main()
