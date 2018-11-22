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
import os
import sys

from aidegen import constant
from aidegen.lib.common_util import time_logged
from aidegen.lib.common_util import get_related_paths
from aidegen.lib.ide_util import IdeUtil
from aidegen.lib.metrics import log_usage
from aidegen.lib.project_file_gen import generate_ide_project_files
from aidegen.lib.project_info import ProjectInfo
from aidegen.lib.source_locator import multi_projects_locate_source
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
        usage=('aidegen [module_name1 module_name2... '
               'project_path1 project_path2...]'))
    parser.required = False
    parser.add_argument(
        'targets',
        type=str,
        nargs='*',
        default=[''],
        help=('Android module name or path.'
              'e.g. Settings or packages/apps/Settings'))
    parser.add_argument(
        '-d',
        '--depth',
        type=int,
        choices=range(10),
        default=0,
        help='The depth of module referenced by source.')
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        help='Display DEBUG level logging.')
    parser.add_argument(
        '-i',
        '--ide',
        default=['j'],
        help='Launch IDE type, j: IntelliJ, s: Android Studio.')
    parser.add_argument(
        '-p',
        '--ide-path',
        dest='ide_installed_path',
        help='IDE installed path.')
    parser.add_argument(
        '-n',
        '--no_launch',
        action='store_true',
        help='Do not launch IDE.')
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


def _get_modules(atest_module_info, targets):
    """Get module or project path for Atest to build.

    The rules:
        1. If the module doesn't exist in android root, sys.exit(1).
        2. If module is not a directory, sys.exit(1).
        3. If it contains any build target, return its relative path, else:
           1) If it's android root, return target, it will build whole tree.
           2) If none of above, sys.exit(1)

    Args:
        atest_module_info: A ModuleInfo instance contains data of
                           module-info.json.
        targets: A list of target modules or project paths from user input, when
                 locating the target, project with matched module name of the
                 target has a higher priority than project path. It could be
                 several cases such as:
                 1. Module name, e.g. Settings
                 2. Module path, e.g. packages/apps/Settings
                 3. Relative path, e.g. ../../packages/apps/Settings
                 4. Current directory, e.g. . or no argument

    Returns:
        An iterator of correct module names or project paths.
    """
    for target in targets:
        rel_path, abs_path = get_related_paths(atest_module_info, target)
        if not abs_path.startswith(constant.ANDROID_ROOT_PATH):
            logging.error('%s is outside android root.', abs_path)
            sys.exit(1)
        if not os.path.isdir(abs_path):
            logging.error('The path %s doesn\'t exist.', rel_path)
            sys.exit(1)
        if has_build_target(atest_module_info, rel_path):
            yield rel_path
        else:
            if abs_path == constant.ANDROID_ROOT_PATH:
                yield target
            else:
                logging.error('No modules defined at %s.', rel_path)
                sys.exit(1)


def has_build_target(atest_module_info, rel_path):
    """Determine if a relative path contains buildable module.

    Args:
        atest_module_info: A ModuleInfo instance contains data of
                           module-info.json.
        rel_path: The module path relative to android root.

    Returns:
        True if the relative path contains a build target, otherwise false.
    """
    return any(mod_path.startswith(rel_path)
               for mod_path in atest_module_info.path_to_module_info)


@time_logged
def main(argv):
    """Main entry.

    Try to generates project files for using in IDE.

    Args:
        argv: A list of system arguments.
    """
    log_usage()
    args = _parse_args(argv)
    _configure_logging(args.verbose)
    atest_module_info = module_info.ModuleInfo()
    args.targets = list(_get_modules(atest_module_info, args.targets))
    ide_util_obj = IdeUtil(args.ide_installed_path, args.ide[0])
    if not ide_util_obj.is_ide_installed():
        logging.error(('Can not find IDE in path: %s, please add it to your '
                       '$PATH or provide the exact executable IDE script path '
                       'by "aidegen -p" command.'), args.ide_installed_path)
        sys.exit(1)
    projects = ProjectInfo.generate_projects(atest_module_info, args.targets,
                                             args.verbose)
    multi_projects_locate_source(projects, args.verbose, args.depth)
    generate_ide_project_files(projects)
    if not args.no_launch:
        ide_util_obj.launch_ide(projects[0].iml_path)


if __name__ == '__main__':
    main(sys.argv[1:])
