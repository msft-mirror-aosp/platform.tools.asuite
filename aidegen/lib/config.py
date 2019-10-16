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

"""Config class."""

import copy
import json
import logging
import os
import re

from aidegen.lib import common_util


class AidegenConfig():
    """Class manages AIDEGen's configurations.

    Attributes:
        _config: A dict contains the aidegen config.
        _config_backup: A dict contains the aidegen config.
    """

    # Constants of AIDEGen config
    _DEFAULT_CONFIG_FILE = 'aidegen.config'
    _CONFIG_DIR = os.path.join(
        os.path.expanduser('~'), '.config', 'asuite', 'aidegen')
    _CONFIG_FILE_PATH = os.path.join(_CONFIG_DIR, _DEFAULT_CONFIG_FILE)

    # Constants of enable debugger
    _ENABLE_DEBUG_CONFIG_DIR = 'enable_debugger'
    _ENABLE_DEBUG_CONFIG_FILE = 'enable_debugger.iml'
    _ENABLE_DEBUG_DIR = os.path.join(_CONFIG_DIR, _ENABLE_DEBUG_CONFIG_DIR)
    _ANDROID_MANIFEST_FILE_NAME = 'AndroidManifest.xml'
    _DIR_SRC = 'src'
    _DIR_GEN = 'gen'
    _ANDROIDMANIFEST_CONTENT = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
          android:versionCode="1"
          android:versionName="1.0" >
</manifest>
    """
    # The xml template for enabling debugger.
    _XML_ENABLE_DEBUGGER = """<?xml version="1.0" encoding="UTF-8"?>
<module type="JAVA_MODULE" version="4">
  <component name="FacetManager">
    <facet type="android" name="Android">
      <configuration>
        <proGuardCfgFiles />
      </configuration>
    </facet>
  </component>
  <component name="NewModuleRootManager" inherit-compiler-output="true">
    <exclude-output />
    <content url="file://$MODULE_DIR$">
      <sourceFolder url="file://$MODULE_DIR$/src" isTestSource="false" />
      <sourceFolder url="file://$MODULE_DIR$/gen" isTestSource="false" generated="true" />
    </content>
    <orderEntry type="jdk" jdkName="Android API {API_LEVEL} Platform" jdkType="Android SDK" />
    <orderEntry type="sourceFolder" forTests="false" />
  </component>
</module>
"""
    DEBUG_ENABLED_FILE_PATH = os.path.join(_ENABLE_DEBUG_DIR,
                                           _ENABLE_DEBUG_CONFIG_FILE)

    def __init__(self):
        self._config = {}
        self._config_backup = {}
        self._create_config_folder()

    def __enter__(self):
        self._load_aidegen_config()
        self._config_backup = copy.deepcopy(self._config)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._save_aidegen_config()

    @property
    def preferred_version(self):
        """AIDEGen configuration getter.

        Returns:
            The preferred verson item of configuration data if exists, otherwise
            None.
        """
        return self._config.get('preferred_version', '')

    @preferred_version.setter
    def preferred_version(self, preferred_version):
        """AIDEGen configuration setter.

        Args:
            preferred_version: A string, user's preferred version to be set.
        """
        self._config['preferred_version'] = preferred_version

    def _load_aidegen_config(self):
        """Load data from configuration file."""
        if os.path.exists(self._CONFIG_FILE_PATH):
            try:
                with open(self._CONFIG_FILE_PATH, 'r') as cfg_file:
                    self._config = json.load(cfg_file)
            except ValueError as err:
                info = '{} format is incorrect, error: {}'.format(
                    self._CONFIG_FILE_PATH, err)
                logging.info(info)
            except IOError as err:
                logging.error(err)
                raise

    def _save_aidegen_config(self):
        """Save data to configuration file."""
        if self._is_config_modified():
            with open(self._CONFIG_FILE_PATH, 'w') as cfg_file:
                json.dump(self._config, cfg_file, indent=4)

    def _is_config_modified(self):
        """Check if configuration data is modified."""
        return any(key for key in self._config if not key in self._config_backup
                   or self._config[key] != self._config_backup[key])

    def _create_config_folder(self):
        """Create the config folder if it doesn't exist."""
        if not os.path.exists(self._CONFIG_DIR):
            os.makedirs(self._CONFIG_DIR)

    def _gen_enable_debug_sub_dir(self, dir_name):
        """Generate a dir under enable debug dir.

        Args:
            dir_name: A string of the folder name.
        """
        _dir = os.path.join(self._ENABLE_DEBUG_DIR, dir_name)
        if not os.path.exists(_dir):
            os.makedirs(_dir)

    def _gen_androidmanifest(self):
        """Generate an AndroidManifest.xml under enable debug dir.

        Once the AndroidManifest.xml does not exist or file size is zero,
        AIDEGen will generate it with default content to prevent the red
        underline error in IntelliJ.
        """
        _file = os.path.join(self._ENABLE_DEBUG_DIR,
                             self._ANDROID_MANIFEST_FILE_NAME)
        if not os.path.exists(_file) or os.stat(_file).st_size == 0:
            common_util.file_generate(_file, self._ANDROIDMANIFEST_CONTENT)

    def _gen_enable_debugger_config(self, api_level):
        """Generate the enable_debugger.iml config file.

        Create the enable_debugger.iml if it doesn't exist.

        Args:
            api_level: An integer of API level.
        """
        if not os.path.exists(self.DEBUG_ENABLED_FILE_PATH):
            content = self._XML_ENABLE_DEBUGGER.format(API_LEVEL=api_level)
            common_util.file_generate(self.DEBUG_ENABLED_FILE_PATH, content)

    def create_enable_debugger_module(self, api_level):
        """Create the enable_debugger module.

        1. Create two empty folders named src and gen.
        2. Create an empty file named AndroidManifest.xml
        3. Create the enable_denugger.iml.

        Args:
            api_level: An integer of API level.

        Returns: True if successfully generate the enable debugger module,
                 otherwise False.
        """
        try:
            self._gen_enable_debug_sub_dir(self._DIR_SRC)
            self._gen_enable_debug_sub_dir(self._DIR_GEN)
            self._gen_androidmanifest()
            self._gen_enable_debugger_config(api_level)
            return True
        except (IOError, OSError) as err:
            logging.warning(('Can\'t create the enable_debugger module in %s.\n'
                             '%s'), self._CONFIG_DIR, err)
            return False


class IdeaProperties():
    """Class manages IntelliJ's idea.properties attribute.

    Class Attributes:
        _PROPERTIES_FILE: The property file name of IntelliJ.
        _KEY_FILESIZE: The key name of the maximun file size.
        _FILESIZE_LIMIT: The value to be set as the max file size.
        _RE_SEARCH_FILESIZE: A regular expression to find the current max file
                             size.
        _PROPERTIES_CONTENT: The default content of idea.properties to be
                             generated.

    Attributes:
        idea_file: The absolute path of the idea.properties.
                   For example:
                   In Linux, it is ~/.IdeaIC2019.1/config/idea.properties.
                   In Mac, it is ~/Library/Preferences/IdeaIC2019.1/
                   idea.properties.
    """

    # Constants of idea.properties
    _PROPERTIES_FILE = 'idea.properties'
    _KEY_FILESIZE = 'idea.max.intellisense.filesize'
    _FILESIZE_LIMIT = 100000
    _RE_SEARCH_FILESIZE = r'%s\s?=\s?(?P<value>\d+)' % _KEY_FILESIZE
    _PROPERTIES_CONTENT = """# custom IntelliJ IDEA properties

#-------------------------------------------------------------------------------
# Maximum size of files (in kilobytes) for which IntelliJ IDEA provides coding
# assistance. Coding assistance for large files can affect editor performance
# and increase memory consumption.
# The default value is 2500.
#-------------------------------------------------------------------------------
idea.max.intellisense.filesize=100000
"""

    def __init__(self, config_dir):
        """IdeaProperties initialize.

        Args:
            config_dir: The absolute dir of the idea.properties.
        """
        self.idea_file = os.path.join(config_dir, self._PROPERTIES_FILE)

    def _set_default_idea_properties(self):
        """Create the file idea.properties."""
        common_util.file_generate(self.idea_file, self._PROPERTIES_CONTENT)

    def _reset_max_file_size(self):
        """Reset the max file size value in the idea.properties."""
        updated_flag = False
        properties = common_util.read_file_content(self.idea_file).splitlines()
        for index, line in enumerate(properties):
            res = re.search(self._RE_SEARCH_FILESIZE, line)
            if res and int(res['value']) < self._FILESIZE_LIMIT:
                updated_flag = True
                properties[index] = '%s=%s' % (self._KEY_FILESIZE,
                                               str(self._FILESIZE_LIMIT))
        if updated_flag:
            common_util.file_generate(self.idea_file, '\n'.join(properties))

    def set_max_file_size(self):
        """Set the max file size parameter in the idea.properties."""
        if not os.path.exists(self.idea_file):
            self._set_default_idea_properties()
        else:
            self._reset_max_file_size()
