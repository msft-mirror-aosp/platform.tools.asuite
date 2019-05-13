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

import copy
import argparse
import logging
import os
import sys
import traceback

from aidegen import constant
from aidegen.lib import aidegen_metrics
from aidegen.lib import android_dev_os
from aidegen.lib import common_util
from aidegen.lib import eclipse_project_file_gen
from aidegen.lib import errors
from aidegen.lib import ide_util
from aidegen.lib import module_info
from aidegen.lib import project_config
from aidegen.lib import project_file_gen
from aidegen.lib import project_info

AIDEGEN_REPORT_LINK = ('To report the AIDEGen tool problem, please use this '
                       'link: https://goto.google.com/aidegen-bug')
_NO_LAUNCH_IDE_CMD = """
Can not find IDE in path: {}, you can:
    - add IDE executable to your $PATH
or  - specify the exact IDE executable path by "aidegen -p"
or  - specify "aidegen -n" to generate project file only
"""

_CONGRATULATION = common_util.COLORED_PASS('CONGRATULATION:')
_LAUNCH_SUCCESS_MSG = (
    'IDE launched successfully. Please check your IDE window.')
_IDE_CACHE_REMINDER_MSG = (
    'To prevent the existed IDE cache from impacting your IDE dependency '
    'analysis, please consider to clear IDE caches if necessary. To do that, in'
    ' IntelliJ IDEA, go to [File > Invalidate Caches / Restart...].')

_MAX_TIME = 1
_SKIP_BUILD_INFO_FUTURE = ''.join([
    'AIDEGen build time exceeds {} minute(s).\n'.format(_MAX_TIME),
    project_config.SKIP_BUILD_INFO.rstrip('.'), ' in the future.'
])
_INFO = common_util.COLORED_INFO('INFO:')
_SKIP_MSG = _SKIP_BUILD_INFO_FUTURE.format(
    common_util.COLORED_INFO('aidegen [ module(s) ] -s'))
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
        help=('Skip building jars or modules that create java files in build '
              'time, e.g. R/AIDL/Logtags.'))
    parser.add_argument(
        '-a',
        '--android-tree',
        dest='android_tree',
        action='store_true',
        help='Generate whole Android source tree project file for IDE.')
    return parser.parse_args(args)


def _get_ide_util_instance(args):
    """Get an IdeUtil class instance for launching IDE.

    Args:
        args: An argparse.Namespace class instance holding parsed args.

    Returns:
        An IdeUtil class instance.
    """
    if args.no_launch:
        return None
    ide_util_obj = ide_util.IdeUtil(args.ide_installed_path, args.ide[0],
                                    args.config_reset,
                                    (android_dev_os.AndroidDevOS.MAC ==
                                     android_dev_os.AndroidDevOS.get_os_type()))
    if not ide_util_obj.is_ide_installed():
        ipath = args.ide_installed_path or ide_util_obj.get_default_path()
        err = _NO_LAUNCH_IDE_CMD.format(ipath)
        logging.error(err)
        raise errors.IDENotExistError(err)
    return ide_util_obj


def _generate_project_files(projects):
    """Generate project files by IDE type.

    Args:
        projects: A list of ProjectInfo instances.
    """
    if (project_config.ProjectConfig.get_instance().ide_name == constant.
            IDE_ECLIPSE):
        eclipse_project_file_gen.EclipseConf.generate_ide_project_files(
            projects)
    else:
        project_file_gen.ProjectFileGenerator.generate_ide_project_files(
            projects)


def _launch_ide(ide_util_obj, project_absolute_path):
    """Launch IDE through ide_util instance.

    To launch IDE,
    1. Set IDE config.
    2. For IntelliJ, use .idea as open target is better than .iml file,
       because open the latter is like to open a kind of normal file.
    3. Show _LAUNCH_SUCCESS_MSG to remind users IDE being launched.

    Args:
        ide_util_obj: An ide_util instance.
        project_absolute_path: A string of project absolute path.
    """
    ide_util_obj.config_ide(project_absolute_path)
    ide_util_obj.launch_ide()
    print('\n{} {}\n'.format(_CONGRATULATION, _LAUNCH_SUCCESS_MSG))


def _check_native_projects(targets, ide):
    """Check if targets exist native projects.

    For native projects:
    1. Since IntelliJ doesn't support native projects any more, when targets
       exist native projects, we should separate them and launch them with
       CLion.
    2. Android Studio support native project and open CMakeLists.txt as its
       native project file as well. Its behavior is like IntelliJ: Java projects
       and native projects can't be launched in the same IDE and each IDE can
       only launch a single native project.

    Args:
        targets: A list of targets to be imported.
        ide: A key character of IDE to be launched.

    Returns:
        A tuple of a set of CMakeLists.txt relative paths and a set of build
        targets.
    """
    atest_module_info = module_info.AidegenModuleInfo.get_instance()
    cmake_file = common_util.get_cmakelists_path()
    if not os.path.isfile(cmake_file):
        common_util.generate_clion_projects_file()
    # TODO(b/140140401): Support Eclipse's native projects.
    if (constant.IDE_NAME_DICT[ide] == constant.IDE_ECLIPSE
            or not os.path.isfile(cmake_file)):
        return [], targets

    files = []
    with open(cmake_file, 'r') as infile:
        for line in infile:
            files.append(line.strip())

    ctargets = set()
    cmakelists = set()
    cwd = os.getcwd()
    for target in targets:
        rel_path, abs_path = common_util.get_related_paths(
            atest_module_info, target)
        if rel_path in files:
            ctargets.add(target)
            cmakelists.add(os.path.relpath(abs_path, cwd))
    for target in ctargets:
        targets.remove(target)
    return cmakelists, targets


def _launch_native_projects(ide_util_obj, args, cmakelists):
    """Launch native projects with IDE.

    If the target IDE is IntelliJ we should launch native projects with CLion.

    Args:
        ide_util_obj: An ide_util instance.
        args: An argparse.Namespace class instance holding parsed args.
        cmakelists: A list of CMakeLists.txt file paths.
    """
    native_ide_util_obj = ide_util_obj
    if constant.IDE_NAME_DICT[args.ide[0]] == constant.IDE_INTELLIJ:
        new_args = copy.deepcopy(args)
        new_args.ide[0] = 'c'
        native_ide_util_obj = _get_ide_util_instance(new_args)
    if native_ide_util_obj:
        _launch_ide(native_ide_util_obj, ' '.join(cmakelists))


def _create_and_launch_java_projects(ide_util_obj, targets):
    """Launch Android of Java(Kotlin) projects with IDE.

    Args:
        ide_util_obj: An ide_util instance.
        targets: A list of build targets.
    """
    projects = project_info.ProjectInfo.generate_projects(targets)
    project_info.ProjectInfo.multi_projects_locate_source(projects)
    _generate_project_files(projects)
    if ide_util_obj:
        _launch_ide(ide_util_obj, projects[0].project_absolute_path)


@common_util.time_logged(message=_TIME_EXCEED_MSG, maximum=_MAX_TIME)
def main_with_message(args):
    """Main entry with skip build message.

    Args:
        args: A list of system arguments.
    """
    aidegen_main(args)


@common_util.time_logged
def main_without_message(args):
    """Main entry without skip build message.

    Args:
        args: A list of system arguments.
    """
    aidegen_main(args)


# pylint: disable=broad-except
def main(argv):
    """Main entry.

    Show skip build message in aidegen main process if users command skip_build
    otherwise remind them to use it and include metrics supports.

    Args:
        argv: A list of system arguments.
    """
    exit_code = constant.EXIT_CODE_NORMAL
    try:
        args = _parse_args(argv)
        common_util.configure_logging(args.verbose)
        is_whole_android_tree = project_config.is_whole_android_tree(
            args.targets, args.android_tree)
        references = [constant.ANDROID_TREE] if is_whole_android_tree else []
        aidegen_metrics.starts_asuite_metrics(references)
        if args.skip_build:
            main_without_message(args)
        else:
            main_with_message(args)
    except BaseException as err:
        exit_code = constant.EXIT_CODE_EXCEPTION
        _, exc_value, exc_traceback = sys.exc_info()
        if isinstance(err, errors.AIDEgenError):
            exit_code = constant.EXIT_CODE_AIDEGEN_EXCEPTION
        # Filter out sys.Exit(0) case, which is not an exception case.
        if isinstance(err, SystemExit) and exc_value.code == 0:
            exit_code = constant.EXIT_CODE_NORMAL
        if exit_code is not constant.EXIT_CODE_NORMAL:
            error_message = str(exc_value)
            traceback_list = traceback.format_tb(exc_traceback)
            traceback_list.append(error_message)
            traceback_str = ''.join(traceback_list)
            aidegen_metrics.ends_asuite_metrics(exit_code, traceback_str,
                                                error_message)
            # print out the trackback message for developers to debug
            print(traceback_str)
            raise err
    finally:
        if exit_code is constant.EXIT_CODE_NORMAL:
            aidegen_metrics.ends_asuite_metrics(exit_code)
        print('\n{0} {1}\n\n{0} {2}\n'.format(_INFO, AIDEGEN_REPORT_LINK,
                                              _IDE_CACHE_REMINDER_MSG))


def aidegen_main(args):
    """AIDEGen main entry.

    Try to generate project files for using in IDE.

    Args:
        args: A list of system arguments.
    """
    # Pre-check for IDE relevant case, then handle dependency graph job.
    ide_util_obj = _get_ide_util_instance(args)
    project_config.ProjectConfig(args).init_environment()
    targets = project_config.ProjectConfig.get_instance().targets
    project_info.ProjectInfo.modules_info = module_info.AidegenModuleInfo()
    cmakelists, targets = _check_native_projects(targets, args.ide[0])
    if cmakelists:
        _launch_native_projects(ide_util_obj, args, cmakelists)
    if targets:
        _create_and_launch_java_projects(ide_util_obj, targets)


if __name__ == '__main__':
    main(sys.argv[1:])
