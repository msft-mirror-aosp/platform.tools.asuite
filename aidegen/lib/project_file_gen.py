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
_ORDER_ENTRY = ('        <orderEntry type="module-library" exported="">'
                '<library><CLASSES><root url="jar://%s!/" /></CLASSES>'
                '<JAVADOC /><SOURCES /></library></orderEntry>\n')
_MODULE_ORDER_ENTRY = ('        <orderEntry type="module" '
                       'module-name="%s" />')
_MODULE_SECTION = ('            <module fileurl="file:///$PROJECT_DIR$/%s.iml"'
                   ' filepath="$PROJECT_DIR$/%s.iml" />')
_SUB_MODULES_SECTION = ('            <module fileurl="file:///%s" '
                        'filepath="%s" />')
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
_DEPENDENCIES = 'dependencies'
_DEPENDENCIES_IML = 'dependencies.iml'
_COPYRIGHT_FOLDER = 'copyright'
_COMPILE_XML = 'compiler.xml'
_MISC_XML = 'misc.xml'
_ANDROID_MANIFEST = 'AndroidManifest.xml'
_IML_EXTENSION = '.iml'
_FRAMEWORK_JAR = os.sep + 'framework.jar'
_HIGH_PRIORITY_JARS = [_FRAMEWORK_JAR]

# b/121256503: Prevent duplicated iml names from breaking IDEA.
# Use a map to cache in-using(already used) iml project file names.
_USED_NAME_CACHE = dict()

def get_unique_iml_name(abs_module_path):
    """Create a unique iml name if needed.

    If the iml name has been used already, prefix it with the
    parent_sub_folder_name to form a new unique name, and store iml name in
    _USED_NAME_CACHE as: { abs_module_path:unique_name }.

    Args:
        abs_module_path: Full module path string.

    Return:
        String: A unique iml name.
    """
    if abs_module_path in _USED_NAME_CACHE:
        return _USED_NAME_CACHE[abs_module_path]

    uniq_name = abs_module_path.strip(os.sep).split(os.sep)[-1]
    if any(uniq_name == name for name in _USED_NAME_CACHE.values()):
        parent_path = os.path.relpath(abs_module_path,
                                      constant.ANDROID_ROOT_PATH)
        sub_folders = parent_path.split(os.sep)
        zero_base_index = len(sub_folders) - 1
        # Compose the name by following logic. Take ['cts', 'tests', 'ui'] as
        # an example, if 'ui' is used, then try 'cts_ui', then try
        # 'cts_tests_ui'. And the worst case is cts_tests_ui, which must be an
        # unique one.
        while zero_base_index > 0:
            uniq_name = '_'.join([sub_folders[0],
                                  '_'.join(sub_folders[zero_base_index:])])
            zero_base_index = zero_base_index -1
            if uniq_name not in _USED_NAME_CACHE.values():
                break
    _USED_NAME_CACHE[abs_module_path] = uniq_name
    logging.debug('Unique name for module path of %s is %s.', abs_module_path,
                  uniq_name)
    return uniq_name


def _generate_intellij_project_file(project_info, iml_path_list=None):
    """Generates IntelliJ project files.

    Args:
        project_info: ProjectInfo instance.
        iml_path_list: A list of submodule iml paths.
    """
    source_dict = dict.fromkeys(
        list(project_info.source_path['source_folder_path']), False)
    source_dict.update(
        dict.fromkeys(list(project_info.source_path['test_folder_path']), True))
    project_info.iml_path, _ = _generate_iml(
        constant.ANDROID_ROOT_PATH, project_info.project_absolute_path,
        source_dict, list(project_info.source_path['jar_path']),
        project_info.project_relative_path)
    _generate_modules_xml(project_info.project_absolute_path, iml_path_list)
    _generate_vcs_xml(project_info.project_absolute_path)
    _copy_constant_project_files(project_info.project_absolute_path)


def generate_ide_project_files(projects):
    """Generate IDE project files by a list of ProjectInfo instances.

    For multiple modules case, we call _generate_intellij_project_file to
    generate iml file for submodules first and pass submodules' iml file paths
    as an argument to function _generate_intellij_project_file when we generate
    main module.iml file. In this way, we can add submodules' dependencies iml
    and their own iml file paths to main module's module.xml.

    Args:
        projects: A list of ProjectInfo instances.
    """
    # Initialization
    _USED_NAME_CACHE.clear()

    for project in projects[1:]:
        _generate_intellij_project_file(project)
    iml_paths = [project.iml_path for project in projects[1:]]
    _generate_intellij_project_file(projects[0], iml_paths or None)


def _read_file_content(path):
    """Read file's content.

    Args:
        path: Path of input file.

    Returns:
        String: Content of the file.
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
    dependencies = []
    # Reorder deps in the iml generated by IntelliJ by inserting priority jars.
    for jar_path in jar_dependencies:
        if any((jar_path.endswith(high_priority_jar))
               for high_priority_jar in _HIGH_PRIORITY_JARS):
            module_library += _ORDER_ENTRY % os.path.join(root_path, jar_path)
        else:
            dependencies.append(jar_path)

    for jar_path in dependencies:
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


def _handle_source_folder(root_path, content, source_dict, is_module):
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
        is_module: True if it is module iml, otherwise it is dependencies iml.

    Returns:
        String: Content with source folder handled.
    """
    source_list = list(source_dict.keys())
    source_list.sort()
    src_builder = []
    if is_module:
        content_url_list = _collect_content_url(source_list[:])
        for url in content_url_list:
            src_builder.append(_CONTENT_URL % os.path.join(root_path, url))
            for path, is_test_flag in sorted(source_dict.items()):
                if path.startswith(url):  # The same prefix would be grouped.
                    src_builder.append(_SOURCE_FOLDER % (os.path.join(
                        root_path, path), is_test_flag))
            src_builder.append(_END_CONTENT)
    else:
        for path, is_test_flag in sorted(source_dict.items()):
            path = os.path.join(root_path, path)
            src_builder.append(_CONTENT_URL % path)
            src_builder.append(_SOURCE_FOLDER % (path, is_test_flag))
            src_builder.append(_END_CONTENT)
    return content.replace(_SOURCE_TOKEN, ''.join(src_builder))


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


# pylint: disable=too-many-locals
def _generate_iml(root_path, module_path, source_dict, jar_dependencies,
                  relative_path):
    """Generate iml file.

    Args:
        root_path: Android source tree root path.
        module_path: Absolute path of the module.
        source_dict: A dictionary of sources path with a flag to distinguish the
                     path is test or source folder in IntelliJ.
                     e.g.
                     {'path_a': True, 'path_b': False}
        jar_dependencies: List of the jar path.
        relative_path: Relative path of the module.

    Returns:
        String: The absolute paths of module iml and dependencies iml.
    """
    template = _read_file_content(_TEMPLATE_IML_PATH)

    # Separate module and dependencies source folder
    project_source_dict = {}
    for source in list(source_dict):
        if source == relative_path or source.startswith(relative_path + os.sep):
            is_test = source_dict.get(source)
            source_dict.pop(source)
            project_source_dict.update({source: is_test})

    # Generate module iml.
    module_content = _handle_facet(template, module_path)
    module_content = _handle_source_folder(root_path, module_content,
                                           project_source_dict, True)
    # b/121256503: Prevent duplicated iml names from breaking IDEA.
    module_name = get_unique_iml_name(module_path)

    module_iml_path = os.path.join(module_path, module_name + _IML_EXTENSION)

    dep_name = _get_dependencies_name(module_name)
    dep_sect = _MODULE_ORDER_ENTRY % dep_name
    module_content = module_content.replace(_MODULE_DEP_TOKEN, dep_sect)
    _file_generate(module_iml_path, module_content)

    # Generate dependencies iml.
    dependencies_content = template.replace(_FACET_TOKEN, '')
    dependencies_content = _handle_source_folder(
        root_path, dependencies_content, source_dict, False)
    dependencies_content = _handle_module_dependency(
        root_path, dependencies_content, jar_dependencies)
    dependencies_iml_path = os.path.join(module_path, dep_name + _IML_EXTENSION)
    _file_generate(dependencies_iml_path, dependencies_content)
    logging.debug('Paired iml names are %s, %s', module_iml_path,
                  dependencies_iml_path)
    return module_iml_path, dependencies_iml_path


def _get_dependencies_name(module_name):
    """Get module's dependencies iml name which will be written in module.xml.

    Args:
        module_name: The name will be appended to "dependencies-".

    Returns:
        String: The joined dependencies iml file name, e.g. "dependencies-core"
    """
    return '-'.join([_DEPENDENCIES, module_name])


def _generate_modules_xml(module_path, iml_path_list=None):
    """Generate modules.xml file.

    IntelliJ uses modules.xml to import which modules should be loaded to
    project. Only in multiple modules case will we pass iml_path_list of
    submodules' dependencies and their iml file paths to add them into main
    module's module.xml file. The dependencies iml file names will be changed
    from original dependencies.iml to dependencies-[module_name].iml,
    e.g. dependencies-core.iml for core.iml.

    Args:
        module_path: Path of the module.
        iml_path_list: A list of submodule iml paths.
    """
    content = _read_file_content(_TEMPLATE_MODULES_PATH)

    # b/121256503: Prevent duplicated iml names from breaking IDEA.
    module_name = get_unique_iml_name(module_path)

    file_name = os.path.splitext(module_name)[0]
    dep_name = _get_dependencies_name(file_name)
    module_list = [
        _MODULE_SECTION % (module_name, module_name),
        _MODULE_SECTION % (dep_name, dep_name)
    ]
    if iml_path_list:
        for iml_path in iml_path_list:
            iml_dir, iml_name = os.path.split(iml_path)
            dep_file = _get_dependencies_name(iml_name)
            dep_path = os.path.join(iml_dir, dep_file)
            module_list.append(_SUB_MODULES_SECTION % (dep_path, dep_path))
            module_list.append(_SUB_MODULES_SECTION % (iml_path, iml_path))
    module = '\n'.join(module_list)
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
    content = _read_file_content(_TEMPLATE_VCS_PATH)
    content = content.replace(_VCS_TOKEN, _VCS_SECTION % module_path)
    target_path = os.path.join(module_path, _IDEA_FOLDER, _VCS_XML)
    _file_generate(target_path, content)
