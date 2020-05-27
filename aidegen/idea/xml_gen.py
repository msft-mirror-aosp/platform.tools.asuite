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

"""Creates the xml files.

Usage example:
    vcs = XMLGenerator(module_path, 'vcs.xml')
    if not vcs.xml_obj:
        # Create the file directly.
        common_util.file_generate(vcs.xml_abspath, xml_content)
    else:
        # Add/remove elements to vcs.xml_obj by the methods of
        # ElementTree.Element object.
        vcs.xml_obj.append()
        vcs.xml_obj.makeelement()
        vcs.xml_obj.remove()
        # Update the XML content.
        vcs.create_xml()
"""

from __future__ import absolute_import

import os

from aidegen import constant
from aidegen import templates
from aidegen.lib import common_util
from aidegen.lib import xml_util

_GIT_PATH = '        <mapping directory="{GIT_DIR}" vcs="Git" />'


class XMLGenerator:
    """Creates the xml file.

    Attributes:
        _xml_abspath: A string of the XML's absolute path.
        _xml_obj: An ElementTree object.
    """

    def __init__(self, module_abspath, xml_name):
        """Initializes XMLGenerator.

        Args:
            module_abspath: A string of the module's absolute path.
            xml_name: A string of the xml file name.
        """
        self._xml_abspath = os.path.join(module_abspath, constant.IDEA_FOLDER,
                                         xml_name)
        self._xml_obj = None
        self.parse()

    def parse(self):
        """Parses the XML file to an ElementTree object."""
        if os.path.exists(self._xml_abspath):
            self._xml_obj = xml_util.parse_xml(self._xml_abspath)

    @property
    def xml_path(self):
        """Gets the xml absolute path."""
        return self._xml_abspath

    @property
    def xml_obj(self):
        """Gets the xml object."""
        return self._xml_obj

    def find_elements_by_name(self, element_type, name):
        """Finds the target elements by name attribute.

        Args:
            element_type: A string of element's type.
            name: A string of element's name.

        Return:
            List: ElementTree's element objects.
        """
        return [e for e in self._xml_obj.findall(element_type)
                if e.get('name') == name]

    def create_xml(self):
        """Creates the xml file."""
        common_util.file_generate(self._xml_abspath, common_util.to_pretty_xml(
            self._xml_obj.getroot()))


def gen_vcs_xml(module_path, git_paths):
    """Writes the git path into the .idea/vcs.xml.

    For main module, the vcs.xml should include all modules' git path.
    For the whole AOSP case, ignore creating the vcs.xml. Instead, add the
    ignored Git paths in the workspace.xml.

    Args:
        module_path: Path of the module.
        git_paths: A list of git paths.
    """
    git_mappings = [_GIT_PATH.format(GIT_DIR=p) for p in git_paths]
    vcs = XMLGenerator(module_path, 'vcs.xml')
    if module_path != common_util.get_android_root_dir() or not vcs.xml_obj:
        common_util.file_generate(vcs.xml_path, templates.XML_VCS.format(
            GIT_MAPPINGS='\n'.join(git_mappings)))
