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

from aidegen.lib.config import AidegenConfig

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
_IDE_ECLIPSE = 'Eclipse'


class IdeUtil():
    """Class offers a set of IDE launching utilities.

    For example:
        1. Check if IDE is installed.
        2. Launch an IDE.
    """

    def __init__(self, installed_path=None, ide='j', config_reset=False):
        self._ide = self._get_ide(installed_path, ide, config_reset)

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

    @staticmethod
    def _get_ide(installed_path=None, ide='j', config_reset=False):
        """Get IDE to be launched according to the ide input.

        Args:
            installed_path: The IDE installed path to be checked.
            ide: A key character of IDE to be launched. Default ide='j' is to
                 launch IntelliJ.
            config_reset: A boolean, if true reset configuration data.

        Returns:
            A corresponding IDE instance.
        """
        if ide == 'e':
            return IdeEclipse(installed_path)
        if ide == 's':
            return IdeStudio(installed_path)
        return IdeIntelliJ(installed_path, config_reset)


class IdeBase():
    """Base class of IDE.

    For example:
        1. Check if IntelliJ is installed.
        2. Launch an IntelliJ.
    """

    def __init__(self, installed_path=None, config_reset=False):
        self._installed_path = installed_path
        self.config_reset = config_reset
        self.name = ''

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
        _launch_ide(project_file, self._installed_path, self.name)


class IdeIntelliJ(IdeBase):
    """Class offers a set of IntelliJ launching utilities.

    For example:
        1. Check if IntelliJ is installed.
        2. Launch an IntelliJ.
    """

    # We use this string to determine whether the user has installed
    # intelliJ IDEA, and the reason is that, in linux, the launch script is
    # created by IDEA with specific path naming rule when installed,
    # i.e. /opt/intellij-*/bin/idea.sh.
    _INTELLIJ_EXE_FILE = 'idea.sh'
    _CHECK_INTELLIJ_PATH = os.path.join('/opt/intellij-*/bin',
                                        _INTELLIJ_EXE_FILE)
    _LS_CE_PATH = os.path.join('/opt/intellij-ce-2*/bin', _INTELLIJ_EXE_FILE)
    _LS_UE_PATH = os.path.join('/opt/intellij-ue-2*/bin', _INTELLIJ_EXE_FILE)

    def __init__(self, installed_path=None, config_reset=False):
        super().__init__(installed_path, config_reset)
        self.name = _IDE_INTELLIJ
        if installed_path:
            self._installed_path = _get_script_from_input_path(
                installed_path, self._INTELLIJ_EXE_FILE)
        else:
            self._installed_path = self._get_script_from_internal_path(
                config_reset)

    @classmethod
    def _get_script_from_internal_path(cls, config_reset=False):
        """Get correct IntelliJ installed path from internal path.

        Locates the IntelliJ IDEA launch script path by following rule.

        1. If config file recorded user's preference version, load it.
        2. If config file didn't record, search them form default path if there
           are more than one version, ask user and record it.

        Args:
            config_reset: A boolean, if true reset configuration data.

        Returns:
            The sh full path, or None if no IntelliJ version is installed.
        """
        found = None
        cefiles = _get_intellij_version_path(cls._LS_CE_PATH)
        uefiles = _get_intellij_version_path(cls._LS_UE_PATH)
        all_versions = cls._get_all_versions(cefiles, uefiles)
        if len(all_versions) > 1:
            with AidegenConfig() as aconf:
                if not config_reset and aconf.preferred_version in all_versions:
                    found = aconf.preferred_version
                if not found:
                    found = _ask_preference(all_versions)
                    aconf.preferred_version = found
        elif all_versions:
            found = all_versions[0]
        if found:
            logging.debug('IDE internal installed path: %s.', found)
        return found

    @classmethod
    def _get_all_versions(cls, cefiles, uefiles):
        """Get all versions of launch script files.

        Args:
            cefiles: CE version launch script paths.
            uefiles: UE version launch script paths.

        Returns:
            A list contains all versions of launch script files.
        """
        all_versions = []
        if cefiles:
            all_versions.extend(cefiles)
        if uefiles:
            all_versions.extend(uefiles)
        return all_versions


class IdeStudio(IdeBase):
    """Class offers a set of Android Studio launching utilities.

    For example:
        1. Check if Android Studio is installed.
        2. Launch an Android Studio.
    """

    _CHECK_STUDIO_PATH = '/opt/android-*/bin/studio.sh'
    _STUDIO_EXE_FILE = 'studio.sh'

    def __init__(self, installed_path=None, config_reset=False):
        super().__init__(installed_path, config_reset)
        self.name = _IDE_ANDROID_STUDIO
        if installed_path:
            self._installed_path = _get_script_from_input_path(
                installed_path, self._STUDIO_EXE_FILE)
        else:
            self._installed_path = _get_script_from_internal_path(
                self._CHECK_STUDIO_PATH, _IDE_ANDROID_STUDIO)


class IdeEclipse(IdeBase):
    """Class offers a set of Eclipse launching utilities.

    For example:
        1. Check if Eclipse is installed.
        2. Launch an Eclipse.
    """

    _CHECK_ECLIPSE_PATH = '/opt/eclipse*/eclipse'
    _ECLIPSE_EXE_FILE = 'eclipse'

    def __init__(self, installed_path=None, config_reset=False):
        super().__init__(installed_path, config_reset)
        self.name = _IDE_ECLIPSE
        if installed_path:
            self._installed_path = _get_script_from_input_path(
                installed_path, self._ECLIPSE_EXE_FILE)
        else:
            self._installed_path = _get_script_from_internal_path(
                self._CHECK_ECLIPSE_PATH, _IDE_ECLIPSE)


def _get_script_from_internal_path(ide_path, ide_name):
    """Get the studio.sh script path from internal path.

    Args:
        ide_path: The IDE installed path to be checked.
        ide_name: The IDE name.

    Returns:
        The IDE full path or None if no Android Studio or Eclipse is installed.
    """
    ls_output = glob.glob(ide_path)
    ls_output = sorted(ls_output, reverse=True)
    if ls_output:
        logging.debug('Result for checking %s after sort: %s.', ide_name,
                      ls_output[0])
        return ls_output[0]
    logging.error('No %s installed.', ide_name)
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


def _get_intellij_version_path(version_path):
    """Locates the IntelliJ IDEA launch script path by version.

    Args:
        version_path: IntelliJ CE or UE version launch script path.

    Returns:
        The sh full path, or None if no such IntelliJ version is installed.
    """
    ls_output = glob.glob(version_path)
    if not ls_output:
        return None
    ls_output = sorted(ls_output, reverse=True)
    logging.debug('Result for checking IntelliJ path %s after sorting:%s.',
                  version_path, ls_output)
    return ls_output


def _ask_preference(all_versions):
    """Ask users which version they prefer.

    Args:
        all_versions: A list of all CE and UE version launch script paths.

    Returns:
        An users selected version.
    """
    info = ''
    for i, sfile in enumerate(all_versions, 1):
        item = '\t{}. {}\n'.format(str(i), sfile)
        info = ''.join([info, item])
    query = ('You installed two versions of IntelliJ:\n{}'
             'Please select one.\t').format(info)
    return _select_intellij_version(query, all_versions)


def _select_intellij_version(query, all_versions):
    """Select one from different IntelliJ versions users installed.

    Args:
        query: The query message.
        all_versions: A list of all CE and UE version launch script paths.
    """
    all_numbers = []
    for i in range(len(all_versions)):
        all_numbers.append(str(i + 1))
    input_data = input(query)
    while not input_data in all_numbers:
        input_data = input('Please select a number:\t')
    return all_versions[int(input_data) - 1]
