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
    $ aidegen -p packages/apps/Settings
    or
    $ aidegen -m Settings
    or
    $ cd packages/apps/Settings;aidegen
"""

from __future__ import absolute_import

import argparse
import sys

from aidegen.lib.ide_util import launch_ide
from aidegen.lib.module_info_util import ModuleInfoUtil
from aidegen.lib.project_file_gen import generate_ide_project_file
from aidegen.lib.project_info import ProjectInfo
from aidegen.lib.source_locator import locate_source
from atest import module_info


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
        usage='aidegen [-p project_path] [-m module_name]')
    parser.required = False
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-p', '--path', type=str, dest='project_path',
                       help='Android module path, '
                            'e.g. packages/apps/Settings.')
    group.add_argument('-m', '--module_name', type=str, dest='module_name',
                       help='Android module name, e.g. Settings')
    return parser.parse_args(args)


def main(argv):
    """Main entry.

    Try to generates project files for using in IDE.

    Args:
        argv: A list of system arguments.
    """
    args = _parse_args(argv)
    mod_info = module_info.ModuleInfo()
    project = ProjectInfo(args, mod_info)
    module_obj = ModuleInfoUtil()
    project.modules_info = module_obj.generate_module_info_json(
        project.project_relative_path)
    project.dep_modules = project.get_dep_modules()
    locate_source(project)
    generate_ide_project_file(project)
    launch_ide(project.iml_path)


if __name__ == "__main__":
    main(sys.argv[1:])
