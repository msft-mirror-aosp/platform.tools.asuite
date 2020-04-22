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

"""Creates the iml file for each module.

This class is used to create the iml file for each module. So far, only generate
the create_srcjar() for the framework-all module.

Usage example:
    modules_info = project_info.ProjectInfo.modules_info
    mod_info = modules_info.name_to_module_info['module']
    iml = IMLGenerator(mod_info)
    iml.create()
"""

from __future__ import absolute_import

import os

from aidegen import constant
from aidegen import templates
from aidegen.lib import common_util


class IMLGenerator:
    """Creates the iml file for each module.

    Attributes:
        _mod_info: A dictionary of the module's data from module-info.json.
        _iml_path: A string of the module's iml absolute path.
        _srcjar_urls: A list of srcjar urls.
    """

    def __init__(self, mod_info):
        """Initializes IMLGenerator.

        Args:
            mod_info: A dictionary of the module's data from module-info.json.
        """
        self._mod_info = mod_info
        self._iml_path = os.path.join(common_util.get_android_root_dir(),
                                      mod_info[constant.KEY_PATH][0],
                                      mod_info[constant.KEY_MODULE_NAME]
                                      + '.iml')
        self._srcjar_urls = []

    @property
    def iml_path(self):
        """Gets the iml path."""
        return self._iml_path

    def create(self, create_content):
        """Creates the iml file.

        Create the iml file with specific part of sources.
        e.g. {'srcjars': True}

        Args:
            create_content: A dict to set which part of sources will be created.
        """
        if create_content[constant.KEY_SRCJARS]:
            self._generate_srcjars()
        if self._srcjar_urls:
            self._create_iml()

    def _generate_srcjars(self):
        """Generates the srcjar urls."""
        for srcjar in self._mod_info[constant.KEY_SRCJARS]:
            self._srcjar_urls.append(templates.SRCJAR.format(
                SRCJAR=os.path.join(common_util.get_android_root_dir(),
                                    srcjar)))

    def _create_iml(self):
        """Creates the iml file."""
        content = templates.IML.format(SRCJARS=''.join(self._srcjar_urls))
        common_util.file_generate(self._iml_path, content)
