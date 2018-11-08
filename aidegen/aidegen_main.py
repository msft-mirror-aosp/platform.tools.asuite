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
    $ aidegen Settings
    or
    $ cd packages/apps/Settings;aidegen
"""

from __future__ import absolute_import

import argparse
import logging
import sys

from aidegen.lib.common_util import time_logged
from aidegen.lib.ide_util import launch_ide
from aidegen.lib.module_info_util import ModuleInfoUtil
from aidegen.lib.project_file_gen import generate_ide_project_file
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
        usage='aidegen [module_name or project_path]')
    parser.required = False
    parser.add_argument(
        'target',
        type=str,
        nargs='*',
        help=('Android module name or path.'
              'e.g. Settings or packages/apps/Settings'))
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Display DEBUG level logging.')
    return parser.parse_args(args)


def _configure_logging(verbose):
    """Configure the logger.

    Args:
        verbose: A boolean. If true, display DEBUG level logs.
    """
    log_format = ('%(asctime)s %(filename)s:%(lineno)s:%(levelname)s: '
                  '%(message)s')
    datefmt = '%Y-%m-%d %H:%M:%S'
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format=log_format, datefmt=datefmt)


def _check_module_exists(target, module_info):
    """Check if module or project path exists inside source tree.

    Args:
        target: A string user input from command line. It could be
                several cases such as:
                1. Module name, e.g. Settings
                2. Module path, e.g. packages/apps/Settings
                3. Relative path, e.g. ../../packages/apps/Settings
                4. Current directory, e.g. . or no argument
        module_info: A ModuleInfo class contains data of module-info.json.
    """
    rel_path, abs_path = ProjectInfo.get_related_path(target, module_info)
    if not abs_path.startswith(ProjectInfo.android_root_path):
        logging.error('%s is outside android root.', abs_path)
        sys.exit(1)
    if not module_info.get_module_names(rel_path):
        logging.error('No modules defined at %s.', rel_path)
        sys.exit(1)


@time_logged
def main(argv):
    """Main entry.

    Try to generates project files for using in IDE.

    Args:
        argv: A list of system arguments.
    """
    args = _parse_args(argv)
    _configure_logging(args.verbose)
    _check_module_exists(args.target, ModuleInfoUtil.atest_module_info)
    project = ProjectInfo(args, ModuleInfoUtil.atest_module_info)
    project.modules_info = ModuleInfoUtil().generate_module_info_json(
        project, args.verbose)
    project.dep_modules = project.get_dep_modules()
    locate_source(project, args.verbose)
    generate_ide_project_file(project)
    launch_ide(project.iml_path)


if __name__ == "__main__":
    main(sys.argv[1:])
