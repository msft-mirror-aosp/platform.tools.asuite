#!/usr/bin/env python3
#
# Copyright 2020 - The Android Open Source Project
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

"""Separate the sources from multiple projects."""

import os

from aidegen import constant
from aidegen.idea import iml
from aidegen.lib import common_util
from aidegen.lib import project_file_gen

_KEY_SOURCE_PATH = 'source_folder_path'
_KEY_TEST_PATH = 'test_folder_path'
_SOURCE_FOLDERS = [_KEY_SOURCE_PATH, _KEY_TEST_PATH]
_KEY_SRCJAR_PATH = 'srcjar_path'
_KEY_R_PATH = 'r_java_path'
_KEY_JAR_PATH = 'jar_path'
_FRAMEWORK_PATH = 'frameworks/base'
_FRAMEWORK_SRCJARS = 'framework_srcjars'


class ProjectSplitter:
    """Improves the projects.

    It's a specific solution to deal with the source folders in multiple
    project case. Since the IntelliJ does not allow duplicate source folders,
    AIDEGen needs to separate the source folders for each project. Single
    project or the whole repo tree project are not support in this class.

    Usage:
    project_splitter = ProjectSplitter(projects)

    # Find the dependencies between the projects.
    dependency_dict = project_splitter.get_dependencies()

    # Clear the source folders for each project.
    project_splitter.revise_source_folders()

    Attributes:
        _projects: A list of ProjectInfo.
        _all_srcs: A dictionary contains all sources of multiple projects.
                   e.g.
                   {
                       'module_name': 'test',
                       'path': ['path/to/module'],
                       'srcs': ['src_folder1', 'src_folder2'],
                       'tests': ['test_folder1', 'test_folder2']
                       'jars': ['jar1.jar'],
                       'srcjars': ['1.srcjar', '2.srcjar'],
                       'dependencies': ['framework_srcjars', 'base'],
                       'iml_name': '/abs/path/to/iml.iml'
                   }
        _framework_exist: A boolean, True if framework is one of the projects.
        _framework_iml: A string, the absolute path of the framework's iml.
    """
    def __init__(self, projects):
        """ProjectSplitter initialize.

        Args:
            projects: A list of ProjectInfo object.
        """
        self._projects = projects
        self._all_srcs = dict(projects[0].source_path)
        self._framework_iml = None
        self._framework_exist = any({p.project_relative_path == _FRAMEWORK_PATH
                                     for p in self._projects})
        if self._framework_exist:
            project_gen = project_file_gen.ProjectFileGenerator
            self._framework_iml = project_gen.get_unique_iml_name(
                os.path.join(common_util.get_android_root_dir(),
                             _FRAMEWORK_PATH))

    def revise_source_folders(self):
        """Resets the source folders of each project.

        There should be no duplicate source root path in IntelliJ. The issue
        doesn't happen in single project case. Once users choose multiple
        projects, there could be several same source paths of different
        projects. In order to prevent that, we should remove the source paths
        in dependencies.iml which are duplicate with the paths in [module].iml
        files.

        Steps to prevent the duplicate source root path in IntelliJ:
        1. Copy all sources from sub-projects to main project.
        2. Delete the source and test folders which are not under the
           sub-projects.
        3. Delete the sub-projects' source and test paths from the main project.
        """
        self._collect_all_srcs()
        self._keep_local_sources()
        self._remove_duplicate_sources()

    def _collect_all_srcs(self):
        """Copies all projects' sources to a dictionary."""
        for project in self._projects[1:]:
            for key, value in project.source_path.items():
                self._all_srcs[key].update(value)

    def _keep_local_sources(self):
        """Removes source folders which are not under the project's path.

        1. Remove the source folders which are not under the project.
        2. Remove the duplicate project's source folders from the _all_srcs.
        """
        for project in self._projects:
            srcs = project.source_path
            relpath = project.project_relative_path
            for key in _SOURCE_FOLDERS:
                srcs[key] = {s for s in srcs[key]
                             if common_util.is_source_under_relative_path(
                                 s, relpath)}
                self._all_srcs[key] -= srcs[key]

    def _remove_duplicate_sources(self):
        """Removes the duplicate source folders from each sub project.

        Priority processing with the longest path length, e.g.
        frameworks/base/packages/SettingsLib must have priority over
        frameworks/base.
        """
        for child in sorted(self._projects, key=lambda k: len(
                k.project_relative_path), reverse=True):
            for parent in self._projects:
                if parent is child:
                    continue
                if common_util.is_source_under_relative_path(
                        child.project_relative_path,
                        parent.project_relative_path):
                    for key in _SOURCE_FOLDERS:
                        parent.source_path[key] -= child.source_path[key]

    def get_dependencies(self):
        """Gets the dependencies between the projects.

        Check if the current project's source folder exists in other projects.
        If do, the current project is a dependency module to the other.
        """
        for project in self._projects:
            project.dependencies = [_FRAMEWORK_SRCJARS,
                                    constant.KEY_DEPENDENCIES]
            proj_path = project.project_relative_path
            srcs = (project.source_path[_KEY_SOURCE_PATH]
                    | project.source_path[_KEY_TEST_PATH])
            for dep_proj in self._projects:
                dep_path = dep_proj.project_relative_path
                _is_child = common_util.is_source_under_relative_path(dep_path,
                                                                      proj_path)
                _is_dep = any({s for s in srcs
                               if common_util.is_source_under_relative_path(
                                   s, dep_path)})
                if dep_proj is project or _is_child or not _is_dep:
                    continue
                project_gen = project_file_gen.ProjectFileGenerator
                dep = project_gen.get_unique_iml_name(os.path.join(
                    common_util.get_android_root_dir(), dep_path))
                project.dependencies.insert(1, dep)

    def gen_framework_srcjars_iml(self):
        """Generates the framework-srcjars.iml.

        Create the iml file with only the srcjars of module framework-all. These
        srcjars will be separated from the modules under frameworks/base.

        Returns:
            A string of the framework_srcjars.iml's absolute path.
        """
        mod = dict(self._projects[0].dep_modules[constant.FRAMEWORK_ALL])
        mod[constant.KEY_DEPENDENCIES] = [constant.KEY_DEPENDENCIES]
        mod[constant.KEY_IML_NAME] = _FRAMEWORK_SRCJARS
        if self._framework_exist:
            mod[constant.KEY_DEPENDENCIES].insert(0, self._framework_iml)
        framework_srcjars_iml = iml.IMLGenerator(mod)
        framework_srcjars_iml.create({constant.KEY_SRCJARS: True,
                                      constant.KEY_DEPENDENCIES: True})
        self._all_srcs[_KEY_SRCJAR_PATH] -= set(mod[constant.KEY_SRCJARS])
        return framework_srcjars_iml.iml_path

    def _gen_dependencies_iml(self):
        """Generates the dependencies.iml."""
        mod = {
            constant.KEY_SRCS: self._all_srcs[_KEY_SOURCE_PATH],
            constant.KEY_TESTS: self._all_srcs[_KEY_TEST_PATH],
            constant.KEY_JARS: self._all_srcs[_KEY_JAR_PATH],
            constant.KEY_SRCJARS: (self._all_srcs[_KEY_R_PATH]
                                   | self._all_srcs[_KEY_SRCJAR_PATH]),
            constant.KEY_DEPENDENCIES: [_FRAMEWORK_SRCJARS],
            constant.KEY_PATH: [self._projects[0].project_relative_path],
            constant.KEY_MODULE_NAME: constant.KEY_DEPENDENCIES,
            constant.KEY_IML_NAME: constant.KEY_DEPENDENCIES
        }
        if self._framework_exist:
            mod[constant.KEY_DEPENDENCIES].insert(0, self._framework_iml)
        dep_iml = iml.IMLGenerator(mod)
        dep_iml.create({constant.KEY_DEP_SRCS: True,
                        constant.KEY_SRCJARS: True,
                        constant.KEY_JARS: True,
                        constant.KEY_DEPENDENCIES: True})

    def gen_projects_iml(self):
        """Generates the projects' iml file."""
        project_gen = project_file_gen.ProjectFileGenerator
        for project in self._projects:
            mod_info = {
                constant.KEY_SRCS: project.source_path[_KEY_SOURCE_PATH],
                constant.KEY_TESTS: project.source_path[_KEY_TEST_PATH],
                constant.KEY_DEPENDENCIES: project.dependencies,
                constant.KEY_PATH: [project.project_relative_path],
                constant.KEY_MODULE_NAME: project.module_name,
                constant.KEY_IML_NAME: project_gen.get_unique_iml_name(
                    os.path.join(common_util.get_android_root_dir(),
                                 project.project_relative_path))
            }
            dep_iml = iml.IMLGenerator(mod_info)
            dep_iml.create({constant.KEY_SRCS: True,
                            constant.KEY_DEPENDENCIES: True})
            project.iml_path = dep_iml.iml_path
        self._gen_dependencies_iml()
