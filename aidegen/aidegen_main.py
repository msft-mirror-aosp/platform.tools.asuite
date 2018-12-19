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
from aidegen.lib.common_util import COLORED_INFO
from aidegen.lib.common_util import time_logged
from aidegen.lib.common_util import get_related_paths
from aidegen.lib.errors import FakeModuleError
from aidegen.lib.errors import IDENotExistError
from aidegen.lib.errors import NoModuleDefinedInModuleInfoError
from aidegen.lib.errors import ProjectOutsideAndroidRootError
from aidegen.lib.errors import ProjectPathNotExistError
from aidegen.lib.ide_util import IdeUtil
from aidegen.lib.metrics import log_usage
from aidegen.lib.project_file_gen import generate_ide_project_files
from aidegen.lib.project_info import ProjectInfo
from aidegen.lib.source_locator import multi_projects_locate_source
from atest import module_info

AIDEGEN_REPORT_LINK = ('To report the AIDEGen tool problem, please use this '
                       'link: https://goto.google.com/aidegen-bug')
_SKIP_BUILD_INFO = ('If you are sure the related modules and dependencies have '
                    'been already built, please try to use command {} to skip '
                    'the building process.')
_MAX_TIME = 1
_SKIP_BUILD_INFO_FUTURE = ''.join([
    'AIDEGen build time exceeds {} minute(s).\n'.format(_MAX_TIME),
    _SKIP_BUILD_INFO.rstrip('.'), ' in the future.'
])
_SKIP_BUILD_CMD = '$ ANDROID_HOST_OUT/bin/aidegen {} -s'
_INFO = COLORED_INFO('INFO:')
_SKIP_MSG = _SKIP_BUILD_INFO_FUTURE.format(
    COLORED_INFO('$ ANDROID_HOST_OUT/bin/aidegen [ module(s) ] -s'))
_TIME_EXCEED_MSG = '\n{} {}\n'.format(_INFO, _SKIP_MSG)


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
        help='Launch IDE type, j: IntelliJ, s: Android Studio, e: Eclipse.')
    parser.add_argument(
        '-p',
        '--ide-path',
        dest='ide_installed_path',
        help='IDE installed path.')
    parser.add_argument(
        '-n', '--no_launch', action='store_true', help='Do not launch IDE.')
    parser.add_argument(
        '-r',
        '--config-reset',
        dest='config_reset',
        action='store_true',
        help='Reset all saved configurations, e.g., preferred IDE version.')
    parser.add_argument(
        '-s',
        '--skip-build',
        dest='skip_build',
        action='store_true',
        help='Skip building jar or AIDL files.')
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


def _check_modules(atest_module_info, targets):
    """Check if all targets are valid build targets or project paths containing
       build targets.

    The rules:
        1. If the module doesn't exist in android root, sys.exit(1).
        2. If module is not a directory, sys.exit(1).
        3. If it contains any build target continue checking, else:
           1) If it's android root, continue checking.
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
    """
    for target in targets:
        rel_path, abs_path = get_related_paths(atest_module_info, target)
        if not abs_path:
            err = '{} is a fake module.'.format(target)
            logging.error(err)
            raise FakeModuleError(err)
        if not abs_path.startswith(constant.ANDROID_ROOT_PATH):
            err = '{} is outside android root.'.format(abs_path)
            logging.error(err)
            raise ProjectOutsideAndroidRootError(err)
        if not os.path.isdir(abs_path):
            err = 'The path {} doesn\'t exist.'.format(rel_path)
            logging.error(err)
            raise ProjectPathNotExistError(err)
        if (not has_build_target(atest_module_info, rel_path)
                and abs_path != constant.ANDROID_ROOT_PATH):
            err = 'No modules defined at {}.'.format(rel_path)
            logging.error(err)
            raise NoModuleDefinedInModuleInfoError(err)


def has_build_target(atest_module_info, rel_path):
    """Determine if a relative path contains buildable module.

    Args:
        atest_module_info: A ModuleInfo instance contains data of
                           module-info.json.
        rel_path: The module path relative to android root.

    Returns:
        True if the relative path contains a build target, otherwise false.
    """
    return any(
        mod_path.startswith(rel_path)
        for mod_path in atest_module_info.path_to_module_info)


@time_logged(message=_TIME_EXCEED_MSG, maximum=_MAX_TIME)
def main(argv):
    """Main entry.

    Try to generates project files for using in IDE.

    Args:
        argv: A list of system arguments.
    """
    log_usage()
    args = _parse_args(argv)
    _configure_logging(args.verbose)
    if not args.skip_build:
        msg = _SKIP_BUILD_INFO.format(
            COLORED_INFO(_SKIP_BUILD_CMD.format(' '.join(args.targets))))
        print('\n{} {}\n'.format(_INFO, msg))
    atest_module_info = module_info.ModuleInfo()
    _check_modules(atest_module_info, args.targets)
    ide_util_obj = IdeUtil(args.ide_installed_path, args.ide[0],
                           args.config_reset)
    if not ide_util_obj.is_ide_installed():
        err = ('Can not find IDE in path: {}, please add it to your $PATH or '
               'provide the exact executable IDE script path by "aidegen -p" '
               'command.').format(args.ide_installed_path)
        logging.error(err)
        raise IDENotExistError(err)
    projects = ProjectInfo.generate_projects(atest_module_info, args.targets,
                                             args.verbose)
    multi_projects_locate_source(projects, args.verbose, args.depth,
                                 args.skip_build)
    generate_ide_project_files(projects)
    if not args.no_launch:
        ide_util_obj.launch_ide(projects[0].iml_path)


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    finally:
        print('\n{} {}\n'.format(_INFO, AIDEGEN_REPORT_LINK))
