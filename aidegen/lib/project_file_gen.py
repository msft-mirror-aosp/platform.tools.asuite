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
"""It is an AIDEGen sub task : generate the project files.

This module generate IDE project files from templates.

    Typical usage example:

    generate_ide_project_file(project_info)
"""

import logging


def generate_ide_project_file(project_info):
    """Generate project files by IDE parameter in project_info.

     Args:
         project_info: ProjectInfo class.

     Returns:
         Boolean: True if IDE project files is created successfully.
     """
    return _generate_intellij_project_file(project_info)


def _generate_intellij_project_file(project_info):
    """Generate IntelliJ project files.

    TODO(b/112522635): Generate intelliJ project files.

    Args:
        project_info: ProjectInfo class.

    Returns:
        Boolean: True if intelliJ project files is created successfully.
    """
    logging.info("project path:%s", project_info.real_path)
    return True
