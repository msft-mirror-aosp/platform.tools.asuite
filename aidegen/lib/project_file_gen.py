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

from aidegen import constant

# FACET_SECTION is a part of iml, which defines the framework of the project.
_FACET_SECTION = '''\
    <facet type="android" name="Android">
        <configuration />
    </facet>'''
_SOURCE_FOLDER = ('            <sourceFolder url='
                  '"file://%s" isTestSource="%s" />\n')
_CONTENT_URL = '        <content url="file://%s">\n'
_END_CONTENT = '        </content>\n'
_ORDER_ENTRY = ('    <orderEntry type="module-library"><library>'
                '<CLASSES><root url="jar://%s!/" /></CLASSES>'
                '<JAVADOC /><SOURCES /></library></orderEntry>\n')
_MODULE_SECTION = ('            <module fileurl="file:///$PROJECT_DIR$/%s.iml"'
                   ' filepath="$PROJECT_DIR$/%s.iml" />')
_VCS_SECTION = '        <mapping directory="%s" vcs="Git" />'
_FACET_TOKEN = '@FACETS@'
_SOURCE_TOKEN = '@SOURCES@'
_MODULE_DEP_TOKEN = '@MODULE_DEPENDENCIES@'
_MODULE_TOKEN = '@MODULES@'
_VCS_TOKEN = '@VCS@'
_JAVA_FILE_PATTERN = '%s/*.java'
_ROOT_DIR = constant.ROOT_DIR
_IDEA_DIR = os.path.join(_ROOT_DIR, 'templates/idea')
_TEMPLATE_IML_PATH = os.path.join(_ROOT_DIR, 'templates/module-template.iml')
_IDEA_FOLDER = '.idea'
_MODULES_XML = 'modules.xml'
_VCS_XML = 'vcs.xml'
_TEMPLATE_MODULES_PATH = os.path.join(_IDEA_DIR, _MODULES_XML)
_TEMPLATE_VCS_PATH = os.path.join(_IDEA_DIR, _VCS_XML)
_COPYRIGHT_FOLDER = 'copyright'
_COMPILE_XML = 'compiler.xml'
_MISC_XML = 'misc.xml'
_ANDROID_MANIFEST = 'AndroidManifest.xml'


def generate_ide_project_file(project_info):
    """Generates project files by IDE parameter in project_info.

    Args:
        project_info: ProjectInfo class.
    """
    _generate_intellij_project_file(project_info)


def _generate_intellij_project_file(project_info):
    """Generates IntelliJ project files.

    Args:
        project_info: ProjectInfo class.
    """
    source_dict = dict.fromkeys(
        list(project_info.source_path['source_folder_path']), False)
    source_dict.update(dict.fromkeys(
        list(project_info.source_path['test_folder_path']), True))
    project_info.iml_path = _generate_iml(
        project_info.android_root_path, project_info.project_absolute_path,
        source_dict,
        list(project_info.source_path['jar_path']))
    _generate_modules_xml(project_info.project_absolute_path)
    _generate_vcs_xml(project_info.project_absolute_path)
    _copy_constant_project_files(project_info.project_absolute_path)


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
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    with open(path, 'w') as target:
        target.write(content)


def _copy_constant_project_files(target_path):
    """Copy project files to target path with error handling.

    This function would copy compiler.xml, misc.xml and copyright folder
    to target folder. Since these files aren't mandatory in IntelliJ, it
    only logs when an IOError occurred.

    Args:
        target_path: Path of target file.
    """
    target_copyright_path = os.path.join(target_path, _IDEA_FOLDER,
                                         _COPYRIGHT_FOLDER)
    try:
        # Existing copyright folder needs to be removed first.
        # Otherwise it would raise IOError.
        if os.path.exists(target_copyright_path):
            shutil.rmtree(target_copyright_path)
        shutil.copytree(
            os.path.join(_IDEA_DIR, _COPYRIGHT_FOLDER), target_copyright_path)
        shutil.copy(
            os.path.join(_IDEA_DIR, _COMPILE_XML),
            os.path.join(target_path, _IDEA_FOLDER, _COMPILE_XML))
        shutil.copy(
            os.path.join(_IDEA_DIR, _MISC_XML),
            os.path.join(target_path, _IDEA_FOLDER, _MISC_XML))
    except IOError as err:
        logging.warning('%s can\'t copy the project files\n %s', target_path,
                        err)


def _handle_facet(content, path):
    """Handle facet part of iml.

    If the module is an Android app, which contains AndroidManifest.xml, it
    should have a facet of android, otherwise we don't need facet in iml.

    Args:
        content: String content of iml.
        path: Path of the module.

    Returns:
        String: Content with facet handled.
    """
    facet = ''
    if os.path.isfile(os.path.join(path, _ANDROID_MANIFEST)):
        facet = _FACET_SECTION
    return content.replace(_FACET_TOKEN, facet)


def _handle_module_dependency(root_path, content, jar_dependencies):
    """Handle module dependency part of iml.

    Args:
        root_path: Android source tree root path.
        content: String content of iml.
        jar_dependencies: List of the jar path.

    Returns:
        String: Content with module dependency handled.
    """
    module_library = ''
    for jar_path in sorted(jar_dependencies):
        module_library += _ORDER_ENTRY % os.path.join(root_path, jar_path)
    return content.replace(_MODULE_DEP_TOKEN, module_library)


def _collect_content_url(sorted_path_list):
    """Collect the content url from a given sorted source path list.

    In iml, it uses content tag to group the source folders.
    e.g.
    <content url="file://$MODULE_DIR$/a">
        <sourceFolder url="file://$MODULE_DIR$/a/b" isTestSource="False" />
        <sourceFolder url="file://$MODULE_DIR$/a/test" isTestSource="True" />
        <sourceFolder url="file://$MODULE_DIR$/a/d/e" isTestSource="False" />
    </content>
    The content url is the common prefix of the source path. However, we can't
    get the information of content url from dependencies. In this function,
    it compares each source folder to get the content url list.

    Args:
        sorted_path_list: The source path list which has been sorted.

    Returns:
        The list of content url.
    """
    content_url_list = []
    sorted_path_list.append('')
    pattern = sorted_path_list.pop(0)
    for path in sorted_path_list:
        common_prefix = os.path.commonpath([pattern, path])
        if common_prefix == '':
            content_url_list.append(pattern)
            pattern = path
        else:
            pattern = common_prefix
    return content_url_list


def _handle_source_folder(root_path, content, source_dict):
    """Handle source folder part of iml.

    It would make the source folder group by content.
    e.g.
    <content url="file://$MODULE_DIR$/a">
        <sourceFolder url="file://$MODULE_DIR$/a/b" isTestSource="False" />
        <sourceFolder url="file://$MODULE_DIR$/a/test" isTestSource="True" />
        <sourceFolder url="file://$MODULE_DIR$/a/d/e" isTestSource="False" />
    </content>

    Args:
        root_path: Android source tree root path.
        content: String content of iml.
        source_dict: A dictionary of sources path with a flag to identify the
                     path is test or source folder in IntelliJ.
                     e.g.
                     {'path_a': True, 'path_b': False}

    Returns:
        String: Content with source folder handled.
    """
    src_list = []
    source_list = list(source_dict.keys())
    source_list.sort()
    content_url_list = _collect_content_url(source_list[:])
    for url in content_url_list:
        src_list.append(_CONTENT_URL % os.path.join(root_path, url))
        for path, is_test_flag in sorted(source_dict.items()):
            if path.startswith(url):  # The same prefix would be grouped.
                src_list.append(_SOURCE_FOLDER % (
                    os.path.join(root_path, path), is_test_flag))
        src_list.append(_END_CONTENT)
    return content.replace(_SOURCE_TOKEN, ''.join(src_list))


def _trim_same_root_source(source_list):
    """Trim the source which has the same root.

    The source list may contain lots of duplicate sources.
    For example:
    a/b, a/b/c, a/b/d
    We only need to import a/b in iml, this function is used to trim useless
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


def _generate_iml(root_path, module_path, source_dict, jar_dependencies):
    """Generate iml file.

    Args:
        root_path: Android source tree root path.
        module_path: Path of the module.
        source_dict: A dictionary of sources path with a flag to distinguish the
                     path is test or source folder in IntelliJ.
                     e.g.
                     {'path_a': True, 'path_b': False}
        jar_dependencies: List of the jar path.

    Returns:
        String: The absolute path of iml.
    """
    content = _read_template(_TEMPLATE_IML_PATH)
    content = _handle_facet(content, module_path)
    content = _handle_source_folder(root_path, content, source_dict)
    content = _handle_module_dependency(root_path, content, jar_dependencies)
    module_name = module_path.split(os.sep)[-1]
    target_path = os.path.join(module_path, module_name + '.iml')
    _file_generate(target_path, content)
    return target_path


def _generate_modules_xml(module_path):
    """Generate modules.xml file.

    IntelliJ use modules.xml to import which modules should be loaded to
    project. Since we are using a single project file, it will only contain the
    module itself.

    Args:
        module_path: Path of the module.
    """
    content = _read_template(_TEMPLATE_MODULES_PATH)
    module_name = module_path.split(os.sep)[-1]
    module = _MODULE_SECTION % (module_name, module_name)
    content = content.replace(_MODULE_TOKEN, module)
    target_path = os.path.join(module_path, _IDEA_FOLDER, _MODULES_XML)
    _file_generate(target_path, content)


def _generate_vcs_xml(module_path):
    """Generate vcs.xml file.

    IntelliJ use vcs.xml to record version control software's information.
    Since we are using a single project file, it will only contain the
    module itself.

    Args:
        module_path: Path of the module.
    """
    content = _read_template(_TEMPLATE_VCS_PATH)
    content = content.replace(_VCS_TOKEN, _VCS_SECTION % module_path)
    target_path = os.path.join(module_path, _IDEA_FOLDER, _VCS_XML)
    _file_generate(target_path, content)
