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

"""Collect the source paths from dependency information."""

from __future__ import absolute_import

import glob
import logging
import os
import re

from aidegen import constant
from aidegen.lib import errors
from aidegen.lib import common_util
from aidegen.lib.common_util import COLORED_INFO
from atest import atest_utils
from atest import constants

# Parse package name from the package declaration line of a java.
# Group matches "foo.bar" of line "package foo.bar;" or "package foo.bar"
_PACKAGE_RE = re.compile(r'\s*package\s+(?P<package>[^(;|\s)]+)\s*', re.I)

_ANDROID_SUPPORT_PATH_KEYWORD = 'prebuilts/sdk/current/'
# File extensions
_JAR_EXT = '.jar'
_JAVA_EXT = '.java'
_KOTLIN_EXT = '.kt'
_SRCJAR_EXT = '.srcjar'

_TARGET_LIBS = [_JAR_EXT]
_TARGET_FILES = [_JAVA_EXT, _KOTLIN_EXT]
_JARJAR_RULES_FILE = 'jarjar-rules.txt'
_KEY_JARJAR_RULES = 'jarjar_rules'
_KEY_JARS = 'jars'
_KEY_TESTS = 'tests'
_NAME_AAPT2 = 'aapt2'
_TARGET_R_JAR = 'R.jar'
_TARGET_AAPT2_SRCJAR = _NAME_AAPT2 + _SRCJAR_EXT
_TARGET_BUILD_FILES = [_TARGET_AAPT2_SRCJAR, _TARGET_R_JAR]
_IGNORE_DIRS = [
    # The java files under this directory have to be ignored because it will
    # cause duplicated classes by libcore/ojluni/src/main/java.
    'libcore/ojluni/src/lambda/java'
]
_DIS_ROBO_BUILD_ENV_VAR = {'DISABLE_ROBO_RUN_TESTS': 'true'}
# When we use atest_utils.build(), it calls soong_ui.bash with whole path and
# some arguments, it should less than 200 characters. We use 200 as command
# buffer.
_CMD_LENGTH_BUFFER = 200
# For each argument, it need a space to separate following argument.
_BLANK_SIZE = 1


def multi_projects_locate_source(projects, verbose):
    """Locate the paths of dependent source folders and jar files with projects.

    Args:
        projects: A list of ProjectInfo instances. Information of a project such
                  as project relative path, project real path, project
                  dependencies.
        verbose: A boolean, if true displays full build output.
    """
    for project in projects:
        locate_source(project, verbose, project.config.depth,
                      project.config.ide_name,
                      build=not project.config.is_skip_build)


def locate_source(project, verbose, depth, ide_name, build=True):
    """Locate the paths of dependent source folders and jar files.

    Try to reference source folder path as dependent module unless the
    dependent module should be referenced to a jar file, such as modules have
    jars and jarjar_rules parameter.
    For example:
        Module: asm-6.0
            java_import {
                name: 'asm-6.0',
                host_supported: true,
                jars: ['asm-6.0.jar'],
            }
        Module: bouncycastle
            java_library {
                name: 'bouncycastle',
                ...
                target: {
                    android: {
                        jarjar_rules: 'jarjar-rules.txt',
                    },
                },
            }

    Args:
        project: A ProjectInfo instance. Information of a project such as
                 project relative path, project real path, project dependencies.
        verbose: A boolean, if true displays full build output.
        depth: An integer shows the depth of module dependency referenced by
               source. Zero means the max module depth.
        ide_name: A string stands for the IDE name, default is IntelliJ.
        build: A boolean default to true, if true skip building jar and srcjar
               files, otherwise build them.

    Example usage:
        project.source_path = locate_source(project, verbose, False)
        E.g.
            project.source_path = {
                'source_folder_path': ['path/to/source/folder1',
                                       'path/to/source/folder2', ...],
                'test_folder_path': ['path/to/test/folder', ...],
                'jar_path': ['path/to/jar/file1', 'path/to/jar/file2', ...]
            }
    """
    if not hasattr(project, 'dep_modules') or not project.dep_modules:
        raise errors.EmptyModuleDependencyError(
            'Dependent modules dictionary is empty.')
    dependencies = project.source_path
    rebuild_targets = set()
    for module_name, module_data in project.dep_modules.items():
        module = _generate_moduledata(module_name, module_data, ide_name,
                                      project.project_relative_path, depth)
        module.locate_sources_path()
        dependencies['source_folder_path'].update(module.src_dirs)
        dependencies['test_folder_path'].update(module.test_dirs)
        dependencies['r_java_path'].update(module.r_java_paths)
        _append_jars_as_dependencies(dependencies, module)
        if module.build_targets:
            rebuild_targets |= module.build_targets
    if rebuild_targets:
        if build:
            _batch_build_dependencies(verbose, rebuild_targets)
            locate_source(project, verbose, depth, ide_name, build=False)
        else:
            logging.warning('Jar or srcjar files build failed:\n\t%s.',
                            '\n\t'.join(rebuild_targets))


def _batch_build_dependencies(verbose, rebuild_targets):
    """Batch build the jar or srcjar files of the modules if they don't exist.

    Command line has the max length limit, MAX_ARG_STRLEN, and
    MAX_ARG_STRLEN = (PAGE_SIZE * 32).
    If the build command is longer than MAX_ARG_STRLEN, this function will
    separate the rebuild_targets into chunks with size less or equal to
    MAX_ARG_STRLEN to make sure it can be built successfully.

    Args:
        verbose: A boolean, if true displays full build output.
        rebuild_targets: A set of jar or srcjar files which do not exist.
    """
    logging.info('Ready to build the jar or srcjar files. Files count = %s',
                 str(len(rebuild_targets)))
    arg_max = os.sysconf("SC_PAGE_SIZE") * 32 - _CMD_LENGTH_BUFFER
    rebuild_targets = list(rebuild_targets)
    for start, end in iter(_separate_build_targets(
            rebuild_targets, arg_max)):
        _build_target(rebuild_targets[start: end], verbose)


def _build_target(targets, verbose):
    """Build the jar or srcjar files.

    Use -k to keep going when some targets can't be built or build failed.
    Use -j to speed up building.

    Args:
        targets: A list of jar or srcjar files which need to build.
        verbose: A boolean, if true displays full build output.
    """
    build_cmd = ['-k', '-j']
    build_cmd.extend(list(targets))
    if not atest_utils.build(build_cmd, verbose, _DIS_ROBO_BUILD_ENV_VAR):
        message = ('Build failed!\n{}\nAIDEGen will proceed but dependency '
                   'correctness is not guaranteed if not all targets being '
                   'built successfully.'.format('\n'.join(targets)))
        print('\n{} {}\n'.format(COLORED_INFO('Warning:'), message))


def _separate_build_targets(build_targets, max_length):
    """Separate the build_targets by limit the command size to max command
    length.

    Args:
        build_targets: A list to be separated.
        max_length: The max number of each build command length.

    Yields:
        The start index and end index of build_targets.
    """
    arg_len = 0
    first_item_index = 0
    for i, item in enumerate(build_targets):
        arg_len = arg_len + len(item) + _BLANK_SIZE
        if arg_len > max_length:
            yield first_item_index, i
            first_item_index = i
            arg_len = len(item) + _BLANK_SIZE
    if first_item_index < len(build_targets):
        yield first_item_index, len(build_targets)


def _generate_moduledata(module_name, module_data, ide_name, project_relpath,
                         depth):
    """Generate a module class to collect dependencies in IntelliJ or Eclipse.

    Args:
        module_name: Name of the module.
        module_data: A dictionary holding a module information.
        ide_name: A string stands for the IDE name.
        project_relpath: A string stands for the project's relative path.
        depth: An integer shows the depth of module dependency referenced by
               source. Zero means the max module depth.

    Returns:
        A ModuleData class.
    """
    if ide_name == constant.IDE_ECLIPSE:
        return EclipseModuleData(module_name, module_data, project_relpath)
    return ModuleData(module_name, module_data, depth)


def _append_jars_as_dependencies(dependent_data, module):
    """Add given module's jar files into dependent_data as dependencies.

    Args:
        dependent_data: A dictionary contains the dependent source paths and
                        jar files.
        module: A ModuleData instance.
    """
    if module.jar_files:
        dependent_data['jar_path'].update(module.jar_files)
        for jar in list(module.jar_files):
            dependent_data['jar_module_path'].update({jar: module.module_path})
    # Collecting the jar files of default core modules as dependencies.
    if constant.KEY_DEPENDENCIES in module.module_data:
        dependent_data['jar_path'].update([
            x for x in module.module_data[constant.KEY_DEPENDENCIES]
            if common_util.is_target(x, _TARGET_LIBS)
        ])


class ModuleData():
    """ModuleData class.

    Attributes:
        All following relative paths stand for the path relative to the android
        repo root.

        module_path: A string of the relative path to the module.
        src_dirs: A set to keep the unique source folder relative paths.
        test_dirs: A set to keep the unique test folder relative paths.
        jar_files: A set to keep the unique jar file relative paths.
        referenced_by_jar: A boolean to check if the module is referenced by a
                           jar file.
        build_targets: A set to keep the unique build target jar or srcjar file
                       relative paths which are ready to be rebuld.
        missing_jars: A set to keep the jar file relative paths if it doesn't
                      exist.
        specific_soong_path: A string of the relative path to the module's
                             intermediates folder under out/.
    """

    def __init__(self, module_name, module_data, depth):
        """Initialize ModuleData.

        Args:
            module_name: Name of the module.
            module_data: A dictionary holding a module information.
            depth: An integer shows the depth of module dependency referenced by
                   source. Zero means the max module depth.
            For example:
                {
                    'class': ['APPS'],
                    'path': ['path/to/the/module'],
                    'depth': 0,
                    'dependencies': ['bouncycastle', 'ims-common'],
                    'srcs': [
                        'path/to/the/module/src/com/android/test.java',
                        'path/to/the/module/src/com/google/test.java',
                        'out/soong/.intermediates/path/to/the/module/test/src/
                         com/android/test.srcjar'
                    ],
                    'installed': ['out/target/product/generic_x86_64/
                                   system/framework/framework.jar'],
                    'jars': ['settings.jar'],
                    'jarjar_rules': ['jarjar-rules.txt']
                }
        """
        assert module_name, 'Module name can\'t be null.'
        assert module_data, 'Module data of %s can\'t be null.' % module_name
        self.module_name = module_name
        self.module_data = module_data
        self._init_module_path()
        self._init_module_depth(depth)
        self.src_dirs = set()
        self.test_dirs = set()
        self.jar_files = set()
        self.r_java_paths = set()
        self.referenced_by_jar = False
        self.build_targets = set()
        self.missing_jars = set()
        self.specific_soong_path = os.path.join(
            'out/soong/.intermediates', self.module_path, self.module_name)

    def _is_app_module(self):
        """Check if the current module's class is APPS"""
        return self._check_key('class') and 'APPS' in self.module_data['class']

    def _is_target_module(self):
        """Check if the current module is a target module.

        A target module is the target project or a module under the
        target project and it's module depth is 0.
        For example: aidegen Settings framework
            The target projects are Settings and framework so they are also
            target modules. And the dependent module SettingsUnitTests's path
            is packages/apps/Settings/tests/unit so it also a target module.
        """
        return self.module_depth == 0

    def _collect_r_srcs_paths(self):
        """Collect the source folder of R.java.

        Check if the path of aapt2.srcjar or R.jar exists, which is the value of
        key "srcjars" in module_data. If the path of both 2 cases doesn't exist,
        build it onto an intermediates directory. Build system will finally copy
        the R.java from the intermediates directory to the central R directory
        after building successfully. So set the central R directory
        out/target/common/R as a default source folder in IntelliJ.

        Case of aapt2.srcjar:
            srcjar: out/target/common/obj/APPS/Settings_intermediates/
                    aapt2.srcjar
            After building the aapt2.srcjar successfully, the folder out/target/
            common/obj/APPS/Settings_intermediates/aapt2 will be generated and
            contain the R.java file of the module.

        Case of R.jar:
            srcjar: out/soong/.intermediates/packages/apps/Car/LensPicker/
                    CarLensPickerApp/android_common/gen/R.jar
            After building the R.jar successfully, the folder out/soong/
            .intermediates/packages/apps/Car/LensPicker/CarLensPickerApp/
            android_common/gen/aapt2/R will be generated and contain the R.java
            file of the module.

        Case of central R folder: out/target/common/R
            Build system will copy the R.java from the intermediates directory
            to the central R directory during the build.
        """
        if (self._is_app_module() and self._is_target_module() and
                self._check_key(constant.KEY_SRCJARS)):
            # Add the aapt2.srcjar or R.jar into build target when the source
            # folder of R.java doesn't exist.
            for srcjar in self.module_data[constant.KEY_SRCJARS]:
                r_dir = self._get_r_dir(srcjar)
                if r_dir:
                    if not os.path.exists(common_util.get_abs_path(r_dir)):
                        self.build_targets.add(srcjar)
                    # In case the central R folder been deleted, uses the
                    # intermediate folder as the dependency to R.java.
                    self.r_java_paths.add(r_dir)
        # Add the central R as a default source folder.
        self.r_java_paths.add(constant.CENTRAL_R_PATH)

    @staticmethod
    def _get_r_dir(srcjar):
        """Get the source folder of R.java.

        Args:
            srcjar: A file path string, the build target of the module to
                    generate R.java.

        Returns:
            A relative source folder path string, and return None if the target
            file name is not aapt2.srcjar or R.jar.
        """
        target_folder, target_file = os.path.split(srcjar)
        if target_file == _TARGET_AAPT2_SRCJAR:
            return os.path.join(target_folder, _NAME_AAPT2)
        if target_file == _TARGET_R_JAR:
            return os.path.join(target_folder, _NAME_AAPT2, 'R')
        return None

    def _init_module_path(self):
        """Inintialize self.module_path."""
        self.module_path = (self.module_data[constant.KEY_PATH][0]
                            if self._check_key(constant.KEY_PATH) else '')

    def _init_module_depth(self, depth):
        """Initialize module depth's settings.

        Set the module's depth from module info when user have -d parameter.
        Set the -d value from user input, default to 0.

        Args:
            depth: the depth to be set.
        """
        self.module_depth = (int(self.module_data[constant.KEY_DEPTH])
                             if depth else 0)
        self.depth_by_source = depth

    def _is_android_supported_module(self):
        """Determine if this is an Android supported module."""
        return self.module_path.startswith(_ANDROID_SUPPORT_PATH_KEYWORD)

    def _check_jarjar_rules_exist(self):
        """Check if jarjar rules exist."""
        return (_KEY_JARJAR_RULES in self.module_data and
                self.module_data[_KEY_JARJAR_RULES][0] == _JARJAR_RULES_FILE)

    def _check_jars_exist(self):
        """Check if jars exist."""
        return _KEY_JARS in self.module_data and self.module_data[_KEY_JARS]

    def _collect_srcs_paths(self):
        """Collect source folder paths in src_dirs from module_data['srcs']."""
        if self._check_key(constant.KEY_SRCS):
            scanned_dirs = set()
            for src_item in self.module_data[constant.KEY_SRCS]:
                src_dir = None
                src_item = os.path.relpath(src_item)
                if src_item.endswith(_SRCJAR_EXT):
                    self._append_jar_from_installed(self.specific_soong_path)
                elif common_util.is_target(src_item, _TARGET_FILES):
                    # Only scan one java file in each source directories.
                    src_item_dir = os.path.dirname(src_item)
                    if src_item_dir not in scanned_dirs:
                        scanned_dirs.add(src_item_dir)
                        src_dir = self._get_source_folder(src_item)
                else:
                    # To record what files except java and srcjar in the srcs.
                    logging.debug('%s is not in parsing scope.', src_item)
                if src_dir:
                    self._add_to_source_or_test_dirs(src_dir)

    def _check_key(self, key):
        """Check if key is in self.module_data and not empty.

        Args:
            key: the key to be checked.
        """
        return key in self.module_data and self.module_data[key]

    def _add_to_source_or_test_dirs(self, src_dir):
        """Add folder to source or test directories.

        Args:
            src_dir: the directory to be added.
        """
        if not any(path in src_dir for path in _IGNORE_DIRS):
            if self._is_test_module(src_dir):
                self.test_dirs.add(src_dir)
            else:
                self.src_dirs.add(src_dir)

    @staticmethod
    def _is_test_module(src_dir):
        """Check if the module path is a test module path.

        Args:
            src_dir: the directory to be checked.

        Returns:
            True if module path is a test module path, otherwise False.
        """
        return _KEY_TESTS in src_dir.split(os.sep)

    def _get_source_folder(self, java_file):
        """Parsing a java to get the package name to filter out source path.

        Args:
            java_file: A string, the java file with relative path.
                       e.g. path/to/the/java/file.java

        Returns:
            source_folder: A string of path to source folder(e.g. src/main/java)
                           or none when it failed to get package name.
        """
        abs_java_path = common_util.get_abs_path(java_file)
        if os.path.exists(abs_java_path):
            package_name = self._get_package_name(abs_java_path)
            if package_name:
                return self._parse_source_path(java_file, package_name)
        return None

    @staticmethod
    def _parse_source_path(java_file, package_name):
        """Parse the source path by filter out the package name.

        Case 1:
        java file: a/b/c/d/e.java
        package name: c.d
        The source folder is a/b.

        Case 2:
        java file: a/b/c.d/e.java
        package name: c.d
        The source folder is a/b.

        Case 3:
        java file: a/b/c/d/e.java
        package name: x.y
        The source folder is a/b/c/d.

        Case 4:
        java file: a/b/c.d/e/c/d/f.java
        package name: c.d
        The source folder is a/b/c.d/e.

        Case 5:
        java file: a/b/c.d/e/c.d/e/f.java
        package name: c.d.e
        The source folder is a/b/c.d/e.

        Args:
            java_file: A string of the java file relative path.
            package_name: A string of the java file's package name.

        Returns:
            A string, the source folder path.
        """
        java_file_name = os.path.basename(java_file)
        pattern = r'%s/%s$' % (package_name, java_file_name)
        search_result = re.search(pattern, java_file)
        if search_result:
            return java_file[:search_result.start()].strip(os.sep)
        return os.path.dirname(java_file)

    @staticmethod
    def _get_package_name(abs_java_path):
        """Get the package name by parsing a java file.

        Args:
            abs_java_path: A string of the java file with absolute path.
                           e.g. /root/path/to/the/java/file.java

        Returns:
            package_name: A string of package name.
        """
        package_name = None
        with open(abs_java_path) as data:
            for line in data.read().splitlines():
                match = _PACKAGE_RE.match(line)
                if match:
                    package_name = match.group('package')
                    break
        return package_name

    def _append_jar_file(self, jar_path):
        """Append a path to the jar file into self.jar_files if it's exists.

        Args:
            jar_path: A path supposed to be a jar file.

        Returns:
            Boolean: True if jar_path is an existing jar file.
        """
        if common_util.is_target(jar_path, _TARGET_LIBS):
            self.referenced_by_jar = True
            if os.path.isfile(common_util.get_abs_path(jar_path)):
                self.jar_files.add(jar_path)
            else:
                self.missing_jars.add(jar_path)
            return True
        return False

    def _append_jar_from_installed(self, specific_dir=None):
        """Append a jar file's path to the list of jar_files with matching
        path_prefix.

        There might be more than one jar in "installed" parameter and only the
        first jar file is returned. If specific_dir is set, the jar file must be
        under the specific directory or its sub-directory.

        Args:
            specific_dir: A string of path.
        """
        if self._check_key(constant.KEY_INSTALLED):
            for jar in self.module_data[constant.KEY_INSTALLED]:
                if specific_dir and not jar.startswith(specific_dir):
                    continue
                if self._append_jar_file(jar):
                    break

    def _set_jars_jarfile(self):
        """Append prebuilt jars of module into self.jar_files.

        Some modules' sources are prebuilt jar files instead of source java
        files. The jar files can be imported into IntelliJ as a dependency
        directly. There is only jar file name in self.module_data['jars'], it
        has to be combined with self.module_data['path'] to append into
        self.jar_files.
        For example:
        'asm-6.0': {
            'jars': [
                'asm-6.0.jar'
            ],
            'path': [
                'prebuilts/misc/common/asm'
            ],
        },
        Path to the jar file is prebuilts/misc/common/asm/asm-6.0.jar.
        """
        if self._check_key(_KEY_JARS):
            for jar_name in self.module_data[_KEY_JARS]:
                if self._check_key(constant.KEY_INSTALLED):
                    self._append_jar_from_installed()
                else:
                    jar_path = os.path.join(self.module_path, jar_name)
                    jar_abs = common_util.get_abs_path(jar_path)
                    if not os.path.isfile(
                            jar_abs) and jar_name.endswith('prebuilt.jar'):
                        rel_path = self._get_jar_path_from_prebuilts(jar_name)
                        if rel_path:
                            jar_path = rel_path
                    self._append_jar_file(jar_path)

    @staticmethod
    def _get_jar_path_from_prebuilts(jar_name):
        """Get prebuilt jar file from prebuilts folder.

        If the prebuilt jar file we get from method _set_jars_jarfile() does not
        exist, we should search the prebuilt jar file in prebuilts folder.
        For example:
        'platformprotos': {
            'jars': [
                'platformprotos-prebuilt.jar'
            ],
            'path': [
                'frameworks/base'
            ],
        },
        We get an incorrect path: 'frameworks/base/platformprotos-prebuilt.jar'
        If the file does not exist, we should search the file name from
        prebuilts folder. If we can get the correct path from 'prebuilts', we
        can replace it with the incorrect path.

        Args:
            jar_name: The prebuilt jar file name.

        Return:
            A relative prebuilt jar file path if found, otherwise None.
        """
        rel_path = ''
        search = os.sep.join(
            [constant.ANDROID_ROOT_PATH, 'prebuilts/**', jar_name])
        results = glob.glob(search, recursive=True)
        if results:
            jar_abs = results[0]
            rel_path = os.path.relpath(
                jar_abs, os.environ.get(constants.ANDROID_BUILD_TOP, os.sep))
        return rel_path

    def locate_sources_path(self):
        """Locate source folders' paths or jar files."""
        if self.module_depth > self.depth_by_source:
            self._append_jar_from_installed(self.specific_soong_path)
        else:
            if self._is_android_supported_module():
                self._append_jar_from_installed()
            elif self._check_jarjar_rules_exist():
                self._append_jar_from_installed(self.specific_soong_path)
            elif self._check_jars_exist():
                self._set_jars_jarfile()
            self._collect_srcs_paths()
            # If there is no source/tests folder of the module, reference the
            # module by jar.
            if not self.src_dirs and not self.test_dirs:
                self._append_jar_from_installed()
            self._collect_r_srcs_paths()
        if self.referenced_by_jar and self.missing_jars:
            self.build_targets |= self.missing_jars


class EclipseModuleData(ModuleData):
    """Deal with modules data for Eclipse

    Only project target modules use source folder type and the other ones use
    jar as their source. We'll combine both to establish the whole project's
    dependencies. If the source folder used to build dependency jar file exists
    in Android, we should provide the jar file path as <linkedResource> item in
    source data.
    """

    def __init__(self, module_name, module_data, project_relpath):
        """Initialize EclipseModuleData.

        Only project target modules apply source folder type, so set the depth
        of module referenced by source to 0.

        Args:
            module_name: String type, name of the module.
            module_data: A dictionary contains a module information.
            project_relpath: A string stands for the project's relative path.
        """
        super().__init__(module_name, module_data, depth=0)
        self.is_project = common_util.is_project_path_relative_module(
            module_data, project_relpath)

    def locate_sources_path(self):
        """Locate source folders' paths or jar files.

        Only collect source folders for the project modules and collect jar
        files for the other dependent modules.
        """
        if self.is_project:
            self._locate_project_source_path()
        else:
            self._locate_jar_path()
        if self.referenced_by_jar and self.missing_jars:
            self.build_targets |= self.missing_jars

    def _locate_project_source_path(self):
        """Locate the source folder paths of the project module.

        A project module is the target modules or paths that users key in
        aidegen command. Collecting the source folders is necessary for
        developers to edit code. And also collect the central R folder for the
        dependency of resources.
        """
        self._collect_srcs_paths()
        self._collect_r_srcs_paths()

    def _locate_jar_path(self):
        """Locate the jar path of the module.

        Use jar files for dependency modules for Eclipse. Collect the jar file
        path with different cases.
        """
        if self._check_jarjar_rules_exist():
            self._append_jar_from_installed(self.specific_soong_path)
        elif self._check_jars_exist():
            self._set_jars_jarfile()
        else:
            self._append_jar_from_installed()
