#!/usr/bin/env python3
#
# Copyright 2019 - The Android Open Source Project
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

"""It is an AIDEGen sub task: generate the .project file for Eclipse."""

import os

from aidegen import constant
from aidegen.lib import common_util


class EclipseConf():
    """Class to generate project file under the module path for Eclipse.

    Attributes:
        module_abspath: The absolute path of the target project.
        module_name: The name of the target project.
        jar_module_paths: A dict records a mapping of jar file and module path.
        r_java_paths: A list contains the relative folder paths of the R.java
                      files.
        project_file: The absolutely path of .project file.
        template_project_content: A string of a template project_file content.
        project_content: A string ready to be written into project_file.
    """
    # Constants of .project file
    _TEMPLATE_PROJECT_FILE = os.path.join(constant.AIDEGEN_ROOT_PATH,
                                          'templates/eclipse/project.xml')
    _PROJECT_LINK = ('                <link><name>{}</name><type>2</type>'
                     '<location>{}</location></link>\n')
    _PROJECT_FILENAME = '.project'

    def __init__(self, project):
        """Initialize class.

        Args:
            project: A ProjectInfo instance.
        """
        self.module_abspath = project.project_absolute_path
        self.module_name = project.module_name
        self.jar_module_paths = project.source_path['jar_module_path']
        self.r_java_paths = list(project.source_path['r_java_path'])
        # Related value for generating .project.
        self.project_file = os.path.join(self.module_abspath,
                                         self._PROJECT_FILENAME)
        self.template_project_content = common_util.read_file_content(
            self._TEMPLATE_PROJECT_FILE)
        self.project_content = ''

    def _gen_r_link(self):
        """Generate the link resources of the R paths.

        E.g.
            <link>
                <name>dependencies/out/target/common/R</name>
                <type>2</type>
                <location>{ANDROID_ROOT_PATH}/out/target/common/R</location>
            </link>

        Returns: A set contains R paths link resources strings.
        """
        return {self._gen_link(rpath) for rpath in self.r_java_paths}

    def _gen_src_links(self, relpaths):
        """Generate the link resources from relpaths.

        Args:
            relpaths: A list of module paths which are relative to
                      ANDROID_BUILD_TOP.
                      e.g. ['relpath/to/module1', 'relpath/to/module2', ...]

        Returns: A set includes all unique link resources.
        """
        return {self._gen_link(relpath) for relpath in relpaths}

    @classmethod
    def _gen_link(cls, relpath):
        """Generate a link resource from a relative path.

         E.g.
            <link>
                <name>dependencies/path/to/relpath</name>
                <type>2</type>
                <location>/absolute/path/to/relpath</location>
            </link>

        Args:
            relpath: A string of a relative path to Android_BUILD_TOP.

        Returns: A string of link resource.
        """
        alias_name = os.path.join(constant.KEY_DEP, relpath)
        abs_path = os.path.join(constant.ANDROID_ROOT_PATH, relpath)
        return cls._PROJECT_LINK.format(alias_name, abs_path)

    def _create_project_content(self):
        """Create the project file .project under the module."""
        # links is a set to save unique link resources.
        links = self._gen_src_links(self.jar_module_paths.values())
        links.update(self._gen_r_link())
        self.project_content = self.template_project_content.format(
            PROJECTNAME=self.module_name,
            LINKEDRESOURCES=''.join(sorted(list(links))))

    def generate_project_file(self):
        """Generate .project file of the target module."""
        self._create_project_content()
        common_util.file_generate(self.project_file, self.project_content)
