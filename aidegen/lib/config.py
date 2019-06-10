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

"""Config helper class."""

import copy
import json
import logging
import os

from aidegen import constant
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
    # TODO: After the CL aosp/975948 is merged, revise the AIDEGEN_ROOT_PATH to
    #       common_util.get_aidegen_root_dir()
    _ENABLE_DEBUG_TEMPLATE_FILE = os.path.join(
        constant.AIDEGEN_ROOT_PATH, 'templates', _ENABLE_DEBUG_CONFIG_DIR,
        _ENABLE_DEBUG_CONFIG_FILE)
    _ENABLE_DEBUG_DIR = os.path.join(_CONFIG_DIR, _ENABLE_DEBUG_CONFIG_DIR)
    _ANDROID_MANIFEST_FILE_NAME = 'AndroidManifest.xml'
    _DIR_SRC = 'src'
    _DIR_GEN = 'gen'
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

    def _gen_empty_androidmanifest(self):
        """Generate an empty AndroidManifest.xml under enable debug dir."""
        _file = os.path.join(self._ENABLE_DEBUG_DIR,
                             self._ANDROID_MANIFEST_FILE_NAME)
        if not os.path.exists(_file):
            common_util.file_generate(_file, '')

    def _gen_enable_debugger_config(self, api_level):
        """Generate the enable_debugger.iml config file.

        Create the enable_debugger.iml if it doesn't exist.

        Args:
            api_level: An integer of API level.
        """
        if not os.path.exists(self.DEBUG_ENABLED_FILE_PATH):
            content = common_util.read_file_content(
                self._ENABLE_DEBUG_TEMPLATE_FILE).format(API_LEVEL=api_level)
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
            self._gen_empty_androidmanifest()
            self._gen_enable_debugger_config(api_level)
            return True
        except (IOError, OSError) as err:
            logging.warning(('Can\'t create the enable_debugger module in %s.\n'
                             '%s'), self._CONFIG_DIR, err)
            return False
