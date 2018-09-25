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
        </configuration>
    </facet>'''
_SOURCE_FOLDER = ('            <sourceFolder url="file://$MODULE_DIR$/%s"'
                  ' isTestSource="%s" />\n')
_CONTENT_URL = '        <content url="file://$MODULE_DIR$/%s">\n'
_END_CONTENT = '        </content>\n'
_ORDER_ENTRY = (
    '    <orderEntry type="module-library"><library>'
    '<CLASSES><root url="jar://$MODULE_DIR$/%s!/"/></CLASSES><JAVADOC/>'
    '<SOURCES/></library></orderEntry>\n')
_FACET_TOKEN = '@FACETS@'
_SOURCE_TOKEN = '@SOURCES@'
_MODULE_DEP_TOKEN = '@MODULE_DEPENDENCIES@'
_JAVA_FILE_PATTERN = '%s/*.java'
_ROOT_DIR = constant.ROOT_DIR
_IDEA_DIR = os.path.join(_ROOT_DIR, 'templates/idea')
_TEMPLATE_IML_PATH = os.path.join(_ROOT_DIR, 'templates/module-template.iml')
_COPYRIGHT_FOLDER = 'copyright'
_COMPILE_XML = 'compiler.xml'
_MISC_XML = 'misc.xml'
_ANDROID_MANIFEST = 'AndroidManifest.xml'


def generate_ide_project_file(project_info):
    """Generate project files by IDE parameter in project_info.

    Args:
        project_info: ProjectInfo class.

    Returns:
        Boolean: True if IDE project files is created successfully.
    """
    return _generate_intellij_project_file(project_info)


def _generate_intellij_project_file(project_info):
    """Generate IntelliJ project files.

    TODO(b/112522635): Generate intelliJ project files.

    Args:
        project_info: ProjectInfo class.

    Returns:
        Boolean: True if intelliJ project files is created successfully.
    """
    logging.info('project path:%s', project_info.project_absolute_path)
    return True


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
    with open(path, 'w') as target:
        target.write(content)


def _copy_constant_project_files(target_path):
    """Copy project files to target path with error handling.

    This function would copy compiler.xml, misc.xml and copyright folder
    to target folder. Since these files aren't mandatory in IntelliJ, I
    only log it when IOError occurred.

    Args:
        target_path: Path of target file.
    """
    target_copyright_path = os.path.join(target_path, _COPYRIGHT_FOLDER)
    try:
        # Existing copyright folder needs to be removed first.
        # Otherwise it would incur IOError.
        if os.path.exists(target_copyright_path):
            shutil.rmtree(target_copyright_path)
        shutil.copytree(
            os.path.join(_IDEA_DIR, _COPYRIGHT_FOLDER), target_copyright_path)
        shutil.copy(
            os.path.join(_IDEA_DIR, _COMPILE_XML),
            os.path.join(target_path, _COMPILE_XML))
        shutil.copy(
            os.path.join(_IDEA_DIR, _MISC_XML),
            os.path.join(target_path, _MISC_XML))
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


def _handle_module_dependency(content, jar_dependencies):
    """Handle module dependency part of iml.

    Args:
        content: String content of iml.
        jar_dependencies: List of the jar path.

    Returns:
        String: Content with module dependency handled.
    """
    module_library = ''
    for jar_path in jar_dependencies:
        module_library += _ORDER_ENTRY % jar_path
    return content.replace(_MODULE_DEP_TOKEN, module_library)


def _collect_content_url(sorted_path_list):
    """Collect the content url from given sorted source path list.

    In iml, it uses content tag to group the source folders.
    e.g.
    <content url...>
        <sourceFolder...>
        <sourceFolder...>
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
        common_prefix = os.path.commonprefix([pattern, path])
        if common_prefix == '':
            content_url_list.append(os.path.dirname(pattern))
            pattern = path
        else:
            pattern = common_prefix
    return content_url_list


def _handle_source_folder(content, source_list):
    """Handle source folder part of iml.

    It would make the source folder group by content.
    e.g.
    <content...>
        <sourceFolder...>
        <sourceFolder...>
    </content>

    Args:
        content: String content of iml.
        source_list: List of the sources.

    Returns:
        String: Content with source folder handled.
    """
    source_list.sort()
    content_url_list = _collect_content_url(source_list[:])
    source = ''
    for url in content_url_list:
        source += _CONTENT_URL % url
        for path in source_list:
            if path.startswith(url):  # The same prefix would be grouped.
                source += _SOURCE_FOLDER % (path, str('test' in path))
                # If the path contains "test" is should be test source.
        source += _END_CONTENT
    return content.replace(_SOURCE_TOKEN, source)


def _generate_iml(module_path, source_list, jar_dependencies):
    """Generate iml file.

    Args:
        module_path: Path of the module.
        source_list: List of the sources.
        jar_dependencies: List of the jar path.
    """
    content = _read_template(_TEMPLATE_IML_PATH)
    content = _handle_facet(content, module_path)
    content = _handle_source_folder(content, source_list)
    content = _handle_module_dependency(content, jar_dependencies)
    module_name = module_path.split(os.sep)[-1]
    target_path = os.path.join(module_path, module_name + '.iml')
    _file_generate(target_path, content)
