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

"""It is an AIDEGen sub task : launch IDE task!

Takes a project file path as input, after passing the needed check(file
existence, IDE type, etc.), launch the project in related IDE.

    Typical usage example:

    ide_util_obj = IdeUtil()
    if ide_util_obj.is_ide_installed():
        ide_util_obj.launch_ide(self, project_file)
"""

import glob
import logging
import os
import subprocess
import fnmatch

# TODO(albaltai): If needed, create a log file to replace /dev/null and to
#                 collect IDEA related usage metrics data.
_IGNORE_STD_OUT_ERR_CMD = '&>/dev/null'

# To confirm target is IDEA by VERIFYING folder existence.
_IDEA_FOLDER = '.idea'

# To confirm target is IDEA by project file extension.
_IML_EXTENSION = '.iml'

# Type of IDEs
_IDE_INTELLIJ = 'IntelliJ'
_IDE_ANDROID_STUDIO = 'Android Studio'


class IdeUtil():
    """Class offers a set of IDE launching utilities.

    For example:
        1. Check if IDE is installed.
        2. Launch an IDE.
    """

    def __init__(self, installed_path=None, ide='j'):
        self._installed_path = installed_path
        # TODO(b/118787088): create basic IDE project files for Eclipse
        self._ide = IdeStudio(installed_path) if ide == 's' else IdeIntelliJ(
            installed_path)

    def is_ide_installed(self):
        """Checks if the IDE is already installed.

        Returns:
            True if IDE is installed already, otherwise False.
        """
        return self._ide.is_ide_installed()

    def launch_ide(self, project_file):
        """Launches the relative IDE by opening the passed project file.

        Args:
            project_file: The full path of the IDE project file.
        """
        return self._ide.launch_ide(project_file)


class IdeIntelliJ():
    """Class offers a set of IntelliJ launching utilities.

    For example:
        1. Check if IntelliJ is installed.
        2. Launch an IntelliJ.
    """

    _INTELLIJ_EXE_FILE = 'idea.sh'

    # We use this string to determine whether the user has installed
    # intelliJ IDEA, and the reason is that, in linux, the launch script is
    # created by IDEA with specific path naming rule when installed,
    # i.e. /opt/intellij-*/bin/idea.sh.
    _CHECK_INTELLIJ_PATH = os.path.join('/opt/intellij-*/bin',
                                        _INTELLIJ_EXE_FILE)

    # In this version, if community edition(CE) exists, AIDEGen prefers IntelliJ
    # community edition(CE) over ultimate edition(UE).
    # TODO(albaltai): prompt user to select a preferred IDE version from all
    #                 installed versions.
    _LS_CE_PATH = os.path.join('/opt/intellij-ce-2*/bin', _INTELLIJ_EXE_FILE)
    _LS_UE_PATH = os.path.join('/opt/intellij-ue-2*/bin', _INTELLIJ_EXE_FILE)

    def __init__(self, installed_path=None):
        self._installed_path = _get_script_from_input_path(
            installed_path, self._INTELLIJ_EXE_FILE
        ) if installed_path else self._get_script_from_internal_path()

    def is_ide_installed(self):
        """Checks if IntelliJ is already installed.

        Returns:
            True if IntelliJ is installed already, otherwise False.
        """
        return bool(self._installed_path)

    def launch_ide(self, project_file):
        """Launches IntelliJ by opening the passed project file.

        Args:
            project_file: The full path of the IntelliJ project file.
        """
        _launch_ide(project_file, self._installed_path, _IDE_INTELLIJ)

    @classmethod
    def _get_script_from_internal_path(cls):
        """Get correct IntelliJ installed path from internal path.

        Locates the IntelliJ IDEA launch script path by following rule.

        1. If the community edition(CE) exists, use the newest CE version as
           target.
        2. If there's no CE version, launch the newest UE version if available.

        Returns:
            The sh full path, or None if no IntelliJ version is installed.
        """
        file_found = cls._get_intellij_version_path(cls._LS_CE_PATH)
        if not file_found:
            file_found = cls._get_intellij_version_path(cls._LS_UE_PATH)
        if file_found:
            logging.debug('IDE internal installed path: %s.', file_found)
        return file_found

    @staticmethod
    def _get_intellij_version_path(version_path):
        """Locates the IntelliJ IDEA launch script path by version.

        Args:
            version_path: IntelliJ CE or UE version launch script path.

        Returns:
            The sh full path, or None if no such IntelliJ version is installed.
        """
        ls_output = glob.glob(version_path)
        if ls_output:
            ls_output = sorted(ls_output, reverse=True)
            logging.debug(
                'Result for checking IntelliJ path %s after sorting:'
                '%s.', version_path, ls_output)
            return ls_output[0]
        return None


class IdeStudio():
    """Class offers a set of Android Studio launching utilities.

    For example:
        1. Check if Android Studio is installed.
        2. Launch an Android Studio.
    """

    _CHECK_STUDIO_PATH = '/opt/android-*/bin/studio.sh'
    _STUDIO_EXE_FILE = 'studio.sh'

    def __init__(self, installed_path=None):
        self._installed_path = _get_script_from_input_path(
            installed_path, self._STUDIO_EXE_FILE
        ) if installed_path else self._get_script_from_internal_path()

    def is_ide_installed(self):
        """Checks if Android Studio is already installed.

        Returns:
            True if Android Studio is installed already, otherwise False.
        """
        return bool(self._installed_path)

    def launch_ide(self, project_file):
        """Launches Android Studio by opening the passed project file.

        Args:
            project_file: The full path of the IntelliJ project file.
        """
        _launch_ide(project_file, self._installed_path, _IDE_ANDROID_STUDIO)

    @classmethod
    def _get_script_from_internal_path(cls):
        """Get the studio.sh script path from internal path.

        Returns:
            The studio.sh full path or None if no Android Studio is installed.
        """
        ls_output = glob.glob(cls._CHECK_STUDIO_PATH)
        ls_output = sorted(ls_output, reverse=True)
        if ls_output:
            logging.debug('Result for checking Android Studio after sort: %s.',
                          ls_output[0])
            return ls_output[0]
        logging.error('No Android Studio installed.')
        return None


def _run_ide_sh(installed_path, project_file):
    """Run IDE launching script with an IntelliJ project file path as argument.

    Args:
        installed_path: the IDE installed path.
        project_file: The path of IntelliJ IDEA project file.
    """
    assert installed_path, 'No suitable IDE installed.'
    logging.debug('Script path: %s, project file path: %s.', installed_path,
                  project_file)

    # Compose launch IDEA command to run as a new process and redirect output.
    run_sh_cmd = _get_run_ide_cmd(installed_path, project_file)
    logging.debug('Run commnad: %s to launch IDEA project file.', run_sh_cmd)
    try:
        subprocess.check_call(run_sh_cmd, shell=True)
    except subprocess.CalledProcessError as err:
        logging.error('Launch project file %s failed with error: %s.',
                      project_file, err)


def _walk_tree_find_ide_exe_file(top, ide_script_name):
    """Recursively descend the directory tree rooted at top and filter out the
       IDE executable script we need.

    Args:
        top: the tree root to be checked.
        ide_script_name: IDE file name such i.e. IdeIntelliJ._INTELLIJ_EXE_FILE.

    Returns:
        the IDE executable script file(s) found.
    """
    logging.info('Searching IDE script %s in path: %s.', ide_script_name, top)
    for root, _, files in os.walk(top):
        for file_ in fnmatch.filter(files, ide_script_name):
            yield os.path.join(root, file_)


def _get_run_ide_cmd(sh_path, project_file):
    """Get the command to launch IDE.

    Args:
        sh_path: The idea.sh path where IDE is installed.
        project_file: The path of IntelliJ IDEA project file.

    Returns:
        A string: The IDE launching command.
    """
    return ' '.join([sh_path, project_file, _IGNORE_STD_OUT_ERR_CMD, '&'])


def _get_script_from_file_path(input_path, ide_file_name):
    """Get IDE executable script file from input file path.

    Args:
        input_path: the file path to be checked.
        ide_file_name: the IDE executable script file name.

    Returns:
        An IDE executable script path if exists otherwise None.
    """
    if os.path.basename(input_path) == ide_file_name:
        files_found = glob.glob(input_path)
        if files_found:
            return sorted(files_found, reverse=True)[0]
    return None


def _get_script_from_dir_path(input_path, ide_file_name):
    """Get an IDE executable script file from input directory path.

    Args:
        input_path: the directory to be searched.
        ide_file_name: the IDE executable script file name.

    Returns:
        An IDE executable script path if exists otherwise None.
    """
    files_found = list(_walk_tree_find_ide_exe_file(input_path, ide_file_name))
    if files_found:
        return sorted(files_found, reverse=True)[0]
    return None


def _launch_ide(project_file, installed_path, ide_name):
    """Launches relative IDE by opening the passed project file.

    Args:
        project_file: The full path of the IDE project file.
        installed_path: The IDE executable script file path.
        ide_name: the IDE name is to be launched.
    """
    assert project_file, 'Empty file path is not allowed.'
    logging.info('Launch %s for project file path: %s.', ide_name, project_file)
    if _is_intellij_project(project_file):
        _run_ide_sh(installed_path, project_file)


def _is_intellij_project(project_file):
    """Checks if the path passed in is an IntelliJ project file.

    Args:
        project_file: The project file's full path.

    Returns:
        True if project_file is an IntelliJ project, False otherwise.
    """
    if not os.path.isfile(project_file):
        return False
    _, ext = os.path.splitext(os.path.basename(project_file))
    if ext and _IML_EXTENSION == ext.lower():
        path = os.path.dirname(project_file)
        logging.debug('Extracted path is: %s.', path)
        return os.path.isdir(os.path.join(path, _IDEA_FOLDER))
    return False


def _get_script_from_input_path(input_path, ide_file_name):
    """Get correct IntelliJ executable script path from input path.

    1. If input_path is a file, check if it is an IDE executable script file.
    2. It input_path is a directory, search if it contains IDE executable script
       file(s).

    Args:
        input_path: input path to be checked if it's an IDE executable
                    script.
        ide_file_name: the IDE executable script file name.

    Returns:
        IDE executable file(s) if exists otherwise None.
    """
    if not input_path:
        return None
    ide_path = ''
    if os.path.isfile(input_path):
        ide_path = _get_script_from_file_path(input_path, ide_file_name)
    if os.path.isdir(input_path):
        ide_path = _get_script_from_dir_path(input_path, ide_file_name)
    if ide_path:
        logging.debug('IDE installed path from user input: %s.', ide_path)
        return ide_path
    return None
