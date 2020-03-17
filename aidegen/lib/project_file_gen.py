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

    Usage example:
    projects: A list of ProjectInfo instances.
    ProjectFileGenerator.generate_ide_project_file(projects)
"""

import logging
import os
import pathlib
import shutil

from aidegen import constant
from aidegen import templates
from aidegen.lib import common_util
from aidegen.lib import project_config

# FACET_SECTION is a part of iml, which defines the framework of the project.
_FACET_SECTION = '''\
    <facet type="android" name="Android">
        <configuration />
    </facet>'''
_SOURCE_FOLDER = ('            <sourceFolder url='
                  '"file://%s" isTestSource="%s" />\n')
_EXCLUDE_ITEM = '            <excludeFolder url="file://%s" />\n'
_CONTENT_URL = '        <content url="file://%s">\n'
_END_CONTENT = '        </content>\n'
_SRCJAR_URL = ('%s<content url="jar://{SRCJAR}">\n'
               '%s<sourceFolder url="jar://{SRCJAR}" isTestSource="False" />\n'
               '%s</content>') % (' ' * 8, ' ' * 12, ' ' * 8)
_ORDER_ENTRY = ('        <orderEntry type="module-library" exported="">'
                '<library><CLASSES><root url="jar://%s!/" /></CLASSES>'
                '<JAVADOC /><SOURCES /></library></orderEntry>\n')
_MODULE_ORDER_ENTRY = ('        <orderEntry type="module" '
                       'module-name="%s" />')
_MODULE_SECTION = ('            <module fileurl="file:///$PROJECT_DIR$/%s.iml"'
                   ' filepath="$PROJECT_DIR$/%s.iml" />')
_SUB_MODULES_SECTION = ('            <module fileurl="file:///{IML}" '
                        'filepath="{IML}" />')
_VCS_SECTION = '        <mapping directory="%s" vcs="Git" />'
_FACET_TOKEN = '@FACETS@'
_SOURCE_TOKEN = '@SOURCES@'
_SRCJAR_TOKEN = '@SRCJAR@'
_MODULE_DEP_TOKEN = '@MODULE_DEPENDENCIES@'
_MODULE_TOKEN = '@MODULES@'
_ENABLE_DEBUGGER_MODULE_TOKEN = '@ENABLE_DEBUGGER_MODULE@'
_VCS_TOKEN = '@VCS@'
_JAVA_FILE_PATTERN = '%s/*.java'
_IDEA_FOLDER = '.idea'
_MODULES_XML = 'modules.xml'
_VCS_XML = 'vcs.xml'
_DEPENDENCIES_IML = 'dependencies.iml'
_COPYRIGHT_FOLDER = 'copyright'
_CODE_STYLE_FOLDER = 'codeStyles'
_APACHE_2_XML = 'Apache_2.xml'
_PROFILES_SETTINGS_XML = 'profiles_settings.xml'
_CODE_STYLE_CONFIG_XML = 'codeStyleConfig.xml'
_PROJECT_XML = 'Project.xml'
_COMPILE_XML = 'compiler.xml'
_MISC_XML = 'misc.xml'
_CONFIG_JSON = 'config.json'
_ANDROID_MANIFEST = 'AndroidManifest.xml'
_IML_EXTENSION = '.iml'
_FRAMEWORK_JAR = os.sep + 'framework.jar'
_HIGH_PRIORITY_JARS = [_FRAMEWORK_JAR]
# Temporarily exclude test-dump and src_stub folders to prevent symbols from
# resolving failure by incorrect reference. These two folders should be removed
# after b/136982078 is resolved.
_EXCLUDE_FOLDERS = ['.idea', '.repo', 'art', 'bionic', 'bootable', 'build',
                    'dalvik', 'developers', 'device', 'hardware', 'kernel',
                    'libnativehelper', 'pdk', 'prebuilts', 'sdk', 'system',
                    'toolchain', 'tools', 'vendor', 'out',
                    'art/tools/ahat/src/test-dump',
                    'cts/common/device-side/device-info/src_stub']
_GIT_FOLDER_NAME = '.git'
# Support gitignore by symbolic link to aidegen/data/gitignore_template.
_GITIGNORE_FILE_NAME = '.gitignore'
_GITIGNORE_REL_PATH = 'tools/asuite/aidegen/data/gitignore_template'
_GITIGNORE_ABS_PATH = os.path.join(common_util.get_android_root_dir(),
                                   _GITIGNORE_REL_PATH)
# Support code style by symbolic link to aidegen/data/AndroidStyle_aidegen.xml.
_CODE_STYLE_REL_PATH = 'tools/asuite/aidegen/data/AndroidStyle_aidegen.xml'
_CODE_STYLE_SRC_PATH = os.path.join(common_util.get_android_root_dir(),
                                    _CODE_STYLE_REL_PATH)


class ProjectFileGenerator:
    """Project file generator.

    Class attributes:
        _USED_NAME_CACHE: A dict to cache already used iml project file names
                          and prevent duplicated iml names from breaking IDEA.

    Attributes:
        project_info: A instance of ProjectInfo.
    """
    # b/121256503: Prevent duplicated iml names from breaking IDEA.
    # Use a map to cache in-using(already used) iml project file names.
    _USED_NAME_CACHE = dict()

    def __init__(self, project_info):
        """ProjectFileGenerator initialize.

        Args:
            project_info: A instance of ProjectInfo.
        """
        self.project_info = project_info

    @classmethod
    def get_unique_iml_name(cls, abs_module_path):
        """Create a unique iml name if needed.

        If the name of last sub folder is used already, prefixing it with prior
        sub folder names as a candidate name. If finally, it's unique, storing
        in _USED_NAME_CACHE as: { abs_module_path:unique_name }. The cts case
        and UX of IDE view are the main reasons why using module path strategy
        but not name of module directly. Following is the detailed strategy:
        1. While loop composes a sensible and shorter name, by checking unique
           to finish the loop and finally add to cache.
           Take ['cts', 'tests', 'app', 'ui'] an example, if 'ui' isn't
           occupied, use it, else try 'cts_ui', then 'cts_app_ui', the worst
           case is whole three candidate names are occupied already.
        2. 'Else' for that while stands for no suitable name generated, so
           trying 'cts_tests_app_ui' directly. If it's still non unique, e.g.,
           module path cts/xxx/tests/app/ui occupied that name already,
           appending increasing sequence number to get a unique name.

        Args:
            abs_module_path: The absolute module path string.

        Return:
            String: A unique iml name.
        """
        if abs_module_path in cls._USED_NAME_CACHE:
            return cls._USED_NAME_CACHE[abs_module_path]

        uniq_name = abs_module_path.strip(os.sep).split(os.sep)[-1]
        if any(uniq_name == name for name in cls._USED_NAME_CACHE.values()):
            parent_path = os.path.relpath(abs_module_path,
                                          common_util.get_android_root_dir())
            sub_folders = parent_path.split(os.sep)
            zero_base_index = len(sub_folders) - 1
            # Start compose a sensible, shorter and unique name.
            while zero_base_index > 0:
                uniq_name = '_'.join(
                    [sub_folders[0], '_'.join(sub_folders[zero_base_index:])])
                zero_base_index = zero_base_index - 1
                if uniq_name not in cls._USED_NAME_CACHE.values():
                    break
            else:
                # b/133393638: To handle several corner cases.
                uniq_name_base = parent_path.strip(os.sep).replace(os.sep, '_')
                i = 0
                uniq_name = uniq_name_base
                while uniq_name in cls._USED_NAME_CACHE.values():
                    i = i + 1
                    uniq_name = '_'.join([uniq_name_base, str(i)])
        cls._USED_NAME_CACHE[abs_module_path] = uniq_name
        logging.debug('Unique name for module path of %s is %s.',
                      abs_module_path, uniq_name)
        return uniq_name

    def _generate_source_section(self, sect_name, is_test):
        """Generate specific section of the project file.

        Args:
            sect_name: The section name, e.g. source_folder_path is for source
                       folder section.
            is_test: A boolean, True if it's the test section else False.

        Returns:
            A dict contains the source folder's contents of project file.
        """
        return dict.fromkeys(
            list(self.project_info.source_path[sect_name]), is_test)

    def generate_intellij_project_file(self, iml_path_list=None):
        """Generates IntelliJ project file.

        Args:
            iml_path_list: An optional list of submodule's iml paths, the
                           default value is None.
        """
        source_dict = self._generate_source_section('source_folder_path', False)
        source_dict.update(
            self._generate_source_section('test_folder_path', True))
        self.project_info.iml_path, _ = self._generate_iml(source_dict)
        self.project_info.git_path = self._get_project_git_path()
        if self.project_info.is_main_project:
            self._generate_modules_xml(iml_path_list)
            self._copy_constant_project_files()

    @classmethod
    def generate_ide_project_files(cls, projects):
        """Generate IDE project files by a list of ProjectInfo instances.

        For multiple modules case, we call _generate_intellij_project_file to
        generate iml file for submodules first and pass submodules' iml file
        paths as an argument to function _generate_intellij_project_file when we
        generate main module.iml file. In this way, we can add submodules'
        dependencies iml and their own iml file paths to main module's
        module.xml.

        Args:
            projects: A list of ProjectInfo instances.
        """
        # Initialization
        cls._USED_NAME_CACHE.clear()
        _merge_all_shared_source_paths(projects)
        for project in projects[1:]:
            ProjectFileGenerator(project).generate_intellij_project_file()
        iml_paths = [project.iml_path for project in projects[1:]]
        ProjectFileGenerator(
            projects[0]).generate_intellij_project_file(iml_paths)
        _merge_project_vcs_xmls(projects)

    def _copy_constant_project_files(self):
        """Copy project files to target path with error handling.

        This function would copy compiler.xml, misc.xml, codeStyles folder and
        copyright folder to target folder. Since these files aren't mandatory in
        IntelliJ, it only logs when an IOError occurred.
        """
        target_path = self.project_info.project_absolute_path
        idea_dir = os.path.join(target_path, _IDEA_FOLDER)
        copyright_dir = os.path.join(idea_dir, _COPYRIGHT_FOLDER)
        code_style_dir = os.path.join(idea_dir, _CODE_STYLE_FOLDER)
        common_util.file_generate(
            os.path.join(idea_dir, _COMPILE_XML), templates.XML_COMPILER)
        common_util.file_generate(
            os.path.join(idea_dir, _MISC_XML), templates.XML_MISC)
        common_util.file_generate(
            os.path.join(copyright_dir, _APACHE_2_XML), templates.XML_APACHE_2)
        common_util.file_generate(
            os.path.join(copyright_dir, _PROFILES_SETTINGS_XML),
            templates.XML_PROFILES_SETTINGS)
        common_util.file_generate(
            os.path.join(code_style_dir, _CODE_STYLE_CONFIG_XML),
            templates.XML_CODE_STYLE_CONFIG)
        code_style_target_path = os.path.join(code_style_dir, _PROJECT_XML)
        if os.path.exists(code_style_target_path):
            os.remove(code_style_target_path)
        try:
            shutil.copy2(_CODE_STYLE_SRC_PATH, code_style_target_path)
        except (OSError, SystemError) as err:
            logging.warning('%s can\'t copy the project files\n %s',
                            code_style_target_path, err)
        # Create .gitignore if it doesn't exist.
        _generate_git_ignore(target_path)
        # Create config.json for Asuite plugin
        lunch_target = common_util.get_lunch_target()
        if lunch_target:
            common_util.file_generate(
                os.path.join(idea_dir, _CONFIG_JSON), lunch_target)

    def _handle_facet(self, content):
        """Handle facet part of iml.

        If the module is an Android app, which contains AndroidManifest.xml, it
        should have a facet of android, otherwise we don't need facet in iml.

        Args:
            content: String content of iml.

        Returns:
            String: Content with facet handled.
        """
        facet = ''
        facet_path = self.project_info.project_absolute_path
        if os.path.isfile(os.path.join(facet_path, _ANDROID_MANIFEST)):
            facet = _FACET_SECTION
        return content.replace(_FACET_TOKEN, facet)

    @staticmethod
    def _handle_module_dependency(content, jar_dependencies):
        """Handle module dependency part of iml.

        Args:
            content: String content of iml.
            jar_dependencies: List of the jar path.

        Returns:
            String: Content with module dependency handled.
        """
        root_path = common_util.get_android_root_dir()
        module_library = ''
        dependencies = []
        # Reorder deps in the iml generated by IntelliJ by inserting priority
        # jars.
        for jar_path in jar_dependencies:
            if any((jar_path.endswith(high_priority_jar))
                   for high_priority_jar in _HIGH_PRIORITY_JARS):
                module_library += _ORDER_ENTRY % os.path.join(
                    root_path, jar_path)
            else:
                dependencies.append(jar_path)

        # IntelliJ indexes jars as dependencies from iml by the ascending order.
        # Without sorting, the order of jar list changes everytime. Sort the jar
        # list to keep the jar dependencies in consistency. It also can help us
        # to discover potential issues like duplicated classes.
        for jar_path in sorted(dependencies):
            module_library += _ORDER_ENTRY % os.path.join(root_path, jar_path)
        return content.replace(_MODULE_DEP_TOKEN, module_library)

    def _is_project_relative_source(self, source):
        """Check if the relative path of a file is a source relative path.

        Check if the file path starts with the relative path or the relative is
        an Android source tree root path.

        Args:
            source: The file path to be checked.

        Returns:
            True if the file is a source relative path, otherwise False.
        """
        relative_path = self.project_info.project_relative_path
        abs_path = common_util.get_abs_path(relative_path)
        if common_util.is_android_root(abs_path):
            return True
        if common_util.is_source_under_relative_path(source, relative_path):
            return True
        return False

    def _handle_source_folder(self, content, source_dict, is_module):
        """Handle source folder part of iml.

        It would make the source folder group by content.
        e.g.
        <content url="file://$MODULE_DIR$/a">
            <sourceFolder url="file://$MODULE_DIR$/a/b" isTestSource="False"/>
            <sourceFolder url="file://$MODULE_DIR$/a/test" isTestSource="True"/>
            <sourceFolder url="file://$MODULE_DIR$/a/d/e" isTestSource="False"/>
        </content>

        Args:
            content: String content of iml.
            source_dict: A dictionary of sources path with a flag to identify
                         the path is test or source folder in IntelliJ.
                         e.g.
                         {'path_a': True, 'path_b': False}
            is_module: True if it is module iml, otherwise it is dependencies
                       iml.

        Returns:
            String: Content with source folder handled.
        """
        root_path = common_util.get_android_root_dir()
        relative_path = self.project_info.project_relative_path

        src_builder = []
        if is_module:
            # Set the content url to module's path since it's the iml of target
            # project which only has it's sub-folders in source_list.
            src_builder.append(
                _CONTENT_URL % os.path.join(root_path, relative_path))
            for path, is_test_flag in sorted(source_dict.items()):
                if self._is_project_relative_source(path):
                    src_builder.append(_SOURCE_FOLDER % (os.path.join(
                        root_path, path), is_test_flag))
            # If relative_path empty, it is Android root. When handling root
            # module, we add the exclude folders to speed up indexing time.
            if not relative_path:
                src_builder.extend(_get_exclude_content(root_path))
            src_builder.append(_END_CONTENT)
        else:
            for path, is_test_flag in sorted(source_dict.items()):
                path = os.path.join(root_path, path)
                src_builder.append(_CONTENT_URL % path)
                src_builder.append(_SOURCE_FOLDER % (path, is_test_flag))
                src_builder.append(_END_CONTENT)
        return content.replace(_SOURCE_TOKEN, ''.join(src_builder))

    @staticmethod
    def _handle_srcjar_folder(content, srcjar_paths=None):
        """Handle the aapt2.srcjar and R.jar content for iml.

        Example for setting the aapt2.srcjar or R.jar as a source folder in
        IntelliJ.
        e.g.
        <content url="jar://$MODULE_DIR$/aapt2.srcjar!/">
            <sourceFolder url="jar://$MODULE_DIR$/aapt2.srcjar!/"
                          isTestSource="False"/>
        </content>
        <content url="jar://$MODULE_DIR$/R.jar!/">
            <sourceFolder url="jar://$MODULE_DIR$/R.jar!/"
                          isTestSource="False"/>
        </content>

        Args:
            content: String content of iml.
            srcjar_paths: A set of srcjar paths, default value is None.

        Returns:
            String: Content with srcjar folder handled.
        """
        srcjar_urls = []
        if srcjar_paths:
            for srcjar_dir in sorted(srcjar_paths):
                srcjar_urls.append(_SRCJAR_URL.format(SRCJAR=os.path.join(
                    common_util.get_android_root_dir(), srcjar_dir)))
        if srcjar_urls:
            return content.replace(_SRCJAR_TOKEN, '\n'.join(srcjar_urls))
        return content.replace(_SRCJAR_TOKEN + '\n', '')

    # pylint: disable=too-many-locals
    def _generate_iml(self, source_dict):
        """Generate iml file.

        Args:
            source_dict: A dictionary of sources path with a flag to distinguish
                         the path is test or source folder in IntelliJ.
                         e.g.
                         {'path_a': True, 'path_b': False}

        Returns:
            String: The absolute paths of module iml and dependencies iml.
        """
        module_path = self.project_info.project_absolute_path
        jar_dependencies = list(self.project_info.source_path['jar_path'])
        # Separate module and dependencies source folder
        project_source_dict = {}
        for source in list(source_dict):
            if self._is_project_relative_source(source):
                is_test = source_dict.get(source)
                source_dict.pop(source)
                project_source_dict.update({source: is_test})

        # Generate module iml.
        module_content = self._handle_facet(templates.FILE_IML)
        module_content = self._handle_source_folder(module_content,
                                                    project_source_dict, True)
        module_content = self._handle_srcjar_folder(
            module_content, self.project_info.source_path['srcjar_path'])
        # b/121256503: Prevent duplicated iml names from breaking IDEA.
        module_name = self.get_unique_iml_name(module_path)

        module_iml_path = os.path.join(module_path,
                                       module_name + _IML_EXTENSION)

        dep_sect = _MODULE_ORDER_ENTRY % constant.KEY_DEPENDENCIES
        module_content = module_content.replace(_MODULE_DEP_TOKEN, dep_sect)
        common_util.file_generate(module_iml_path, module_content)

        # Only generate the dependencies.iml in the main module's folder.
        dependencies_iml_path = None
        if self.project_info.is_main_project:
            dependencies_content = templates.FILE_IML.replace(_FACET_TOKEN, '')
            dependencies_content = self._handle_source_folder(
                dependencies_content, source_dict, False)
            dependencies_content = self._handle_srcjar_folder(
                dependencies_content,
                self.project_info.source_path['srcjar_path'])
            dependencies_content = self._handle_module_dependency(
                dependencies_content, jar_dependencies)
            dependencies_iml_path = os.path.join(
                module_path, constant.KEY_DEPENDENCIES + _IML_EXTENSION)
            common_util.file_generate(dependencies_iml_path,
                                      dependencies_content)
            logging.debug('Paired iml names are %s, %s', module_iml_path,
                          dependencies_iml_path)
        # The dependencies_iml_path is use for removing the file itself in
        # unittest.
        return module_iml_path, dependencies_iml_path

    def _generate_modules_xml(self, iml_path_list=None):
        """Generate modules.xml file.

        IntelliJ uses modules.xml to import which modules should be loaded to
        project. In multiple modules case, we will pass iml_path_list of
        submodules' dependencies and their iml file paths to add them into main
        module's module.xml file. The dependencies.iml file contains all shared
        dependencies source folders and jar files.

        Args:
            iml_path_list: A list of submodule iml paths.
        """
        module_path = self.project_info.project_absolute_path

        # b/121256503: Prevent duplicated iml names from breaking IDEA.
        module_name = self.get_unique_iml_name(module_path)

        if iml_path_list is not None:
            module_list = [
                _MODULE_SECTION % (module_name, module_name),
                _MODULE_SECTION % (constant.KEY_DEPENDENCIES,
                                   constant.KEY_DEPENDENCIES)
            ]
            for iml_path in iml_path_list:
                module_list.append(_SUB_MODULES_SECTION.format(IML=iml_path))
        else:
            module_list = [
                _MODULE_SECTION % (module_name, module_name)
            ]
        module = '\n'.join(module_list)
        content = self._remove_debugger_token(templates.XML_MODULES)
        content = content.replace(_MODULE_TOKEN, module)
        target_path = os.path.join(module_path, _IDEA_FOLDER, _MODULES_XML)
        common_util.file_generate(target_path, content)

    def _remove_debugger_token(self, content):
        """Remove the token _ENABLE_DEBUGGER_MODULE_TOKEN.

        Remove the token _ENABLE_DEBUGGER_MODULE_TOKEN in 2 cases:
        1. Sub projects don't need to be filled in the enable debugger module
           so we remove the token here. For the main project, the enable
           debugger module will be appended if it exists at the time launching
           IDE.
        2. When there is no need to launch IDE.

        Args:
            content: The content of module.xml.

        Returns:
            String: The content of module.xml.
        """
        if (not project_config.ProjectConfig.get_instance().is_launch_ide or
                not self.project_info.is_main_project):
            content = content.replace(_ENABLE_DEBUGGER_MODULE_TOKEN, '')
        return content

    def _get_project_git_path(self):
        """Get the project's git path.

        Return:
            String: A module's git path.
        """
        module_path = self.project_info.project_absolute_path
        # When importing whole Android repo, it shouldn't add vcs.xml,
        # because IntelliJ doesn't handle repo as a version control.
        if module_path == common_util.get_android_root_dir():
            return None
        git_path = module_path
        while not os.path.isdir(os.path.join(git_path, _GIT_FOLDER_NAME)):
            git_path = str(pathlib.Path(git_path).parent)
            if git_path == os.sep:
                logging.warning('%s can\'t find its .git folder', module_path)
                return None
        return git_path


def _get_exclude_content(root_path):
    """Get the exclude folder content list.

    It returns the exclude folders content list.
    e.g.
    ['<excludeFolder url="file://a/.idea" />',
    '<excludeFolder url="file://a/.repo" />']

    Args:
        root_path: Android source file path.

    Returns:
        String: exclude folder content list.
    """
    exclude_items = []
    for folder in _EXCLUDE_FOLDERS:
        folder_path = os.path.join(root_path, folder)
        if os.path.isdir(folder_path):
            exclude_items.append(_EXCLUDE_ITEM % folder_path)
    return exclude_items


def _trim_same_root_source(source_list):
    """Trim the source which has the same root.

    The source list may contain lots of duplicate sources.
    For example:
    a/b, a/b/c, a/b/d
    We only need to import a/b in iml, this function is used to trim redundant
    sources.

    Args:
        source_list: Sorted list of the sources.

    Returns:
        List: The trimmed source list.
    """
    tmp_source_list = [source_list[0]]
    for src_path in source_list:
        if ''.join([tmp_source_list[-1],
                    os.sep]) not in ''.join([src_path, os.sep]):
            tmp_source_list.append(src_path)
    return sorted(tmp_source_list)


def _write_vcs_xml(module_path, git_paths):
    """Write the git path into vcs.xml.

    For main module, the vcs.xml should include all modules' git path.
    For submodules, there is only one git path in vcs.xml.

    Args:
        module_path: Path of the module.
        git_paths: A list of git path.
    """
    _vcs_content = '\n'.join([_VCS_SECTION % p for p in git_paths if p])
    content = templates.XML_VCS.replace(_VCS_TOKEN, _vcs_content)
    target_path = os.path.join(module_path, _IDEA_FOLDER, _VCS_XML)
    common_util.file_generate(target_path, content)


def _merge_project_vcs_xmls(projects):
    """Merge sub projects' git paths into main project's vcs.xml.

    After all projects' vcs.xml are generated, collect the git path of each
    projects and write them into main project's vcs.xml.

    Args:
        projects: A list of ProjectInfo instances.
    """
    main_project_absolute_path = projects[0].project_absolute_path
    if main_project_absolute_path == common_util.get_android_root_dir():
        git_paths = list(_get_all_git_path(main_project_absolute_path))
    else:
        git_paths = [project.git_path for project in projects]
    _write_vcs_xml(main_project_absolute_path, git_paths)


def _get_all_git_path(root_path):
    """Traverse all subdirectories to get all git folder's path.

    Args:
        root_path: A string of path to traverse.

    Yields:
        A git folder's path.
    """
    for dir_path, dir_names, _ in os.walk(root_path):
        if _GIT_FOLDER_NAME in dir_names:
            yield dir_path


def _generate_git_ignore(target_folder):
    """Generate .gitignore file.

    In target_folder, if there's no .gitignore file, uses symlink() to generate
    one to hide project content files from git.

    Args:
        target_folder: An absolute path string of target folder.
    """
    # TODO(b/133639849): Provide a common method to create symbolic link.
    # TODO(b/133641803): Move out aidegen artifacts from Android repo.
    try:
        gitignore_abs_path = os.path.join(target_folder, _GITIGNORE_FILE_NAME)
        rel_target = os.path.relpath(gitignore_abs_path, os.getcwd())
        rel_source = os.path.relpath(_GITIGNORE_ABS_PATH, target_folder)
        logging.debug('Relative target symlink path: %s.', rel_target)
        logging.debug('Relative ignore_template source path: %s.', rel_source)
        if not os.path.exists(gitignore_abs_path):
            os.symlink(rel_source, rel_target)
    except OSError as err:
        logging.error('Not support to run aidegen on Windows.\n %s', err)


def _filter_out_source_paths(source_paths, module_relpaths):
    """Filter out the source paths which belong to the target module.

    The source_paths is a union set of all source paths of all target modules.
    For generating the dependencies.iml, we only need the source paths outside
    the target modules.

    Args:
        source_paths: A set contains the source folder paths.
        module_relpaths: A list, contains the relative paths of target modules
                         except the main module.

    Returns: A set of source paths.
    """
    return {x for x in source_paths if not any(
        {common_util.is_source_under_relative_path(x, y)
         for y in module_relpaths})}


def _merge_all_shared_source_paths(projects):
    """Merge all source paths and jar paths into main project.

    There should be no duplicate source root path in IntelliJ. The issue doesn't
    happen in single project case. Once users choose multiple projects, there
    could be several same source paths of different projects. In order to
    prevent that, we should remove the source paths in dependencies.iml which
    are duplicate with the paths in [module].iml files.

    Args:
        projects: A list of ProjectInfo instances.
    """
    main_project = projects[0]
    # Merge all source paths of sub projects into main project.
    for project in projects[1:]:
        main_project.source_path['source_folder_path'].update(
            project.source_path['source_folder_path'])
        main_project.source_path['test_folder_path'].update(
            project.source_path['test_folder_path'])
        main_project.source_path['jar_path'].update(
            project.source_path['jar_path'])
    # Filter duplicate source/test paths from dependencies.iml.
    sub_projects_relpaths = {p.project_relative_path for p in projects[1:]}
    main_project.source_path['source_folder_path'] = _filter_out_source_paths(
        main_project.source_path['source_folder_path'], sub_projects_relpaths)
    main_project.source_path['test_folder_path'] = _filter_out_source_paths(
        main_project.source_path['test_folder_path'], sub_projects_relpaths)


def update_enable_debugger(module_path, enable_debugger_module_abspath=None):
    """Append the enable_debugger module's info in modules.xml file.

    Args:
        module_path: A string of the folder path contains IDE project content,
                     e.g., the folder contains the .idea folder.
        enable_debugger_module_abspath: A string of the im file path of enable
                                        debugger module.
    """
    replace_string = ''
    if enable_debugger_module_abspath:
        replace_string = _SUB_MODULES_SECTION.format(
            IML=enable_debugger_module_abspath)
    target_path = os.path.join(module_path, _IDEA_FOLDER, _MODULES_XML)
    content = common_util.read_file_content(target_path)
    content = content.replace(_ENABLE_DEBUGGER_MODULE_TOKEN, replace_string)
    common_util.file_generate(target_path, content)
