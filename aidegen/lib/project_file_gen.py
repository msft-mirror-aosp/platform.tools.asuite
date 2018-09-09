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
import os
import shutil
import sys

# FACET_SECTION is a part of iml, which defines the framework of the project.
_FACET_SECTION = \
    """    <facet type="android" name="Android">\n""" \
    """        </configuration>\n""" \
    """    </facet>"""
_ROOT_DIR = os.path.dirname(sys.modules['__main__'].__file__)
_IDEA_DIR = os.path.join(_ROOT_DIR, "templates/idea")
_COPYRIGHT_FOLDER = "copyright"
_COMPILE_XML = "compiler.xml"
_MISC_XML = "misc.xml"


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


def _read_template(path):
    """Read the template.

    Args:
        path: Path of template file.

    Returns:
        String: Content of the template.
    """
    with open(path) as template:
        return template.read()


def _file_generate(path, content):
    """Generate file from content.

    Args:
        path: Path of target file.
        content: String content of file.
    """
    with open(path, "w") as target:
        target.write(content)


def _copy_constant_project_files(target_path):
    """Copy project files to target path with error handling.

    This function would copy compiler.xml, misc.xml and copyright folder
    to target folder. Since these files aren't mandatory in IntelliJ, I
    only log it when IOError occurred.

    Args:
        target_path: Path of target file.
    """
    target_copyright_path = os.path.join(target_path, _COPYRIGHT_FOLDER)
    try:
        # Existing copyright folder needs to be removed first.
        # Otherwise it would incur IOError.
        if os.path.exists(target_copyright_path):
            shutil.rmtree(target_copyright_path)
        shutil.copytree(
            os.path.join(_IDEA_DIR, _COPYRIGHT_FOLDER), target_copyright_path)
        shutil.copy(
            os.path.join(_IDEA_DIR, _COMPILE_XML),
            os.path.join(target_path, _COMPILE_XML))
        shutil.copy(
            os.path.join(_IDEA_DIR, _MISC_XML),
            os.path.join(target_path, _MISC_XML))
    except IOError as err:
        logging.warning("%s can't copy the project files\n %s", target_path,
                        err)
