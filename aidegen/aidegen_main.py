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
"""AIDEgen

This CLI generates project files for using in IntelliJ, such as:
    - iml
    - .idea/compiler.xml
    - .idea/misc.xml
    - .idea/modules.xml
    - .idea/vcs.xml
    - .idea/.name
    - .idea/copyright/Apache_2.xml
    - .idea/copyright/progiles_settings.xml

- Sample usage:
    - Change directory to AOSP root first.
    $ cd /user/home/aosp/
    - Generating project files under packages/apps/Settings folder.
    $ aidegen packages/apps/Settings
    or
    $ cd packages/apps/Settings;aidegen
"""

from __future__ import absolute_import

import argparse
import sys

from aidegen.lib.project_info import ProjectInfo
from aidegen.lib.source_locator import locate_source


def _parse_args(args):
    """Parse command line arguments.

    Args:
        args: A list of arguments.

    Returns:
        An argparse.Namespace class instance holding parsed args.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="aidegen {project_path}")
    parser.required = False
    parser.add_argument(
        "project_path",
        type=str,
        help="Android module path, e.g. packages/apps/Settings.")
    return parser.parse_args(args)


def generate_module_info_json(project):
    """Generate module dependency information.

    TODO(bralee@): Remove this function when lib.module_info_util is ready.

    Args:
        project: ProjectInfo class.
    """
    project.module_dependency = {}


def generate_ide_project_file(project):
    """Generate project files used for IDE tool.

    TODO(shinwang@): Remove this function when lib.project_file_gen is ready.

    Args:
        project: ProjectInfo class.

    Returns:
        Boolean: True if IDE project files are created successfully.
    """
    project.is_generate_ide_project_file = True
    return project.is_generate_ide_project_file


def launch_ide(project):
    """Launch IDE.

    TODO(albaltai@): Remove this function when lib.ide_util is ready.

    Args:
        project: ProjectInfo class.
    """
    project.launch_ide_successfully = True


def main(argv):
    """Main entry.

    Try to generates project files for using in IDE.

    Args:
        argv: A list of system arguments.
    """
    args = _parse_args(argv)
    project = ProjectInfo(args)
    generate_module_info_json(project)
    locate_source(project)
    if generate_ide_project_file(project):
        launch_ide(project)


if __name__ == "__main__":
    main(sys.argv[1:])
