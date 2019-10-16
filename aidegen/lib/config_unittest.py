#!/usr/bin/env python3
#
# Copyright 2019, The Android Open Source Project
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

"""Unittests for AidegenConfig class."""

import os
import shutil
import tempfile
import unittest
from unittest import mock

from aidegen.lib import config
from aidegen.lib import common_util


# pylint: disable=protected-access
class AidegenConfigUnittests(unittest.TestCase):
    """Unit tests for config.py"""

    @mock.patch('logging.info')
    @mock.patch('logging.error')
    @mock.patch('builtins.open')
    @mock.patch('os.path.exists')
    def test_load_aidegen_config(self, mock_exists, mock_open, mock_error,
                                 mock_info):
        """Test _load_aidegen_config."""
        mock_exists.return_value = True
        cfg = config.AidegenConfig()
        mock_open.side_effect = IOError()
        with self.assertRaises(IOError):
            cfg._load_aidegen_config()
            self.assertTrue(mock_error.called)
            self.assertFalse(mock_info.called)
        mock_open.reset()
        mock_open.side_effect = ValueError()
        cfg._load_aidegen_config()
        self.assertTrue(mock_info.called)

    @mock.patch('json.dump')
    @mock.patch('builtins.open')
    @mock.patch.object(config.AidegenConfig, '_is_config_modified')
    def test_save_aidegen_config(self, mock_is_modified, mock_open, mock_dump):
        """Test _save_aidegen_config."""
        mock_is_modified.return_value = False
        cfg = config.AidegenConfig()
        cfg._save_aidegen_config()
        self.assertFalse(mock_open.called)
        self.assertFalse(mock_dump.called)
        mock_is_modified.return_value = True
        cfg._save_aidegen_config()
        self.assertTrue(mock_open.called)
        self.assertTrue(mock_dump.called)

    @mock.patch('logging.warning')
    @mock.patch.object(config.AidegenConfig, '_gen_enable_debugger_config')
    @mock.patch.object(config.AidegenConfig, '_gen_empty_androidmanifest')
    @mock.patch.object(config.AidegenConfig, '_gen_enable_debug_sub_dir')
    def test_create_enable_debugger(self, mock_debug, mock_empty, mock_enable,
                                    mock_warning):
        """Test create_enable_debugger_module."""
        cfg = config.AidegenConfig()
        mock_debug.side_effect = IOError()
        self.assertFalse(cfg.create_enable_debugger_module(0))
        self.assertTrue(mock_warning.called)
        mock_debug.side_effect = OSError()
        self.assertFalse(cfg.create_enable_debugger_module(0))
        self.assertTrue(mock_warning.called)
        mock_empty.side_effect = IOError()
        self.assertFalse(cfg.create_enable_debugger_module(0))
        self.assertTrue(mock_warning.called)
        mock_empty.side_effect = OSError()
        self.assertFalse(cfg.create_enable_debugger_module(0))
        self.assertTrue(mock_warning.called)
        mock_enable.side_effect = IOError()
        self.assertFalse(cfg.create_enable_debugger_module(0))
        self.assertTrue(mock_warning.called)
        mock_enable.side_effect = OSError()
        self.assertFalse(cfg.create_enable_debugger_module(0))
        self.assertTrue(mock_warning.called)

    @mock.patch.object(common_util, 'file_generate')
    @mock.patch('os.path.exists')
    def test_gen_enable_debugger_config(self, mock_exists, mock_gen):
        """Test _gen_enable_debugger_config."""
        cfg = config.AidegenConfig()
        mock_exists.return_value = True
        cfg._gen_enable_debugger_config(0)
        self.assertFalse(mock_gen.called)
        mock_exists.return_value = False
        cfg._gen_enable_debugger_config(0)
        self.assertTrue(mock_gen.called)

    @mock.patch('os.stat')
    @mock.patch.object(common_util, 'file_generate')
    @mock.patch('os.path.exists')
    def test_gen_empty_androidmanifest(self, mock_exists, mock_gen, mock_stat):
        """Test _gen_empty_androidmanifest."""
        cfg = config.AidegenConfig()
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 1
        cfg._gen_empty_androidmanifest()
        self.assertFalse(mock_gen.called)
        mock_exists.return_value = True
        mock_stat.return_value.st_size = 0
        cfg._gen_empty_androidmanifest()
        self.assertTrue(mock_gen.called)
        mock_exists.return_value = False
        cfg._gen_empty_androidmanifest()
        self.assertTrue(mock_gen.called)

    @mock.patch('os.makedirs')
    @mock.patch('os.path.exists')
    def test_create_config_folder(self, mock_exists, mock_makedirs):
        """Test _create_config_folder."""
        cfg = config.AidegenConfig()
        mock_exists.return_value = True
        cfg._create_config_folder()
        self.assertFalse(mock_makedirs.called)
        mock_exists.return_value = False
        cfg._create_config_folder()
        self.assertTrue(mock_makedirs.called)


class IdeaPropertiesUnittests(unittest.TestCase):
    """Unit tests for IdeaProperties class."""

    _CONFIG_DIR = None

    def setUp(self):
        """Prepare the testdata related path."""
        IdeaPropertiesUnittests._CONFIG_DIR = tempfile.mkdtemp()

    def tearDown(self):
        """Clear the testdata related path."""
        shutil.rmtree(IdeaPropertiesUnittests._CONFIG_DIR)

    def test_set_default_properties(self):
        """Test creating the idea.properties with default content."""
        cfg = config.IdeaProperties(IdeaPropertiesUnittests._CONFIG_DIR)
        cfg._set_default_idea_properties()
        expected_data = cfg._PROPERTIES_CONTENT.format(
            KEY_FILE_SIZE=cfg._KEY_FILESIZE,
            VALUE_FILE_SIZE=cfg._FILESIZE_LIMIT)
        generated_file = os.path.join(IdeaPropertiesUnittests._CONFIG_DIR,
                                      cfg._PROPERTIES_FILE)
        generated_content = common_util.read_file_content(generated_file)
        self.assertEqual(expected_data, generated_content)

    @mock.patch.object(common_util, 'read_file_content')
    def test_reset_max_file_size(self, mock_content):
        """Test reset the file size limit when it's smaller than 100000."""
        mock_content.return_value = ('# custom IntelliJ IDEA properties\n'
                                     'idea.max.intellisense.filesize=5000')
        expected_data = ('# custom IntelliJ IDEA properties\n'
                         'idea.max.intellisense.filesize=100000')
        cfg = config.IdeaProperties(IdeaPropertiesUnittests._CONFIG_DIR)
        cfg._reset_max_file_size()
        generated_file = os.path.join(IdeaPropertiesUnittests._CONFIG_DIR,
                                      cfg._PROPERTIES_FILE)
        with open(generated_file) as properties_file:
            generated_content = properties_file.read()
        self.assertEqual(expected_data, generated_content)

    @mock.patch.object(common_util, 'file_generate')
    @mock.patch.object(common_util, 'read_file_content')
    def test_no_reset_max_file_size(self, mock_content, mock_gen_file):
        """Test when the file size is larger than 100000."""
        mock_content.return_value = ('# custom IntelliJ IDEA properties\n'
                                     'idea.max.intellisense.filesize=110000')
        cfg = config.IdeaProperties(IdeaPropertiesUnittests._CONFIG_DIR)
        cfg._reset_max_file_size()
        self.assertFalse(mock_gen_file.called)

    @mock.patch.object(config.IdeaProperties, '_reset_max_file_size')
    @mock.patch.object(config.IdeaProperties, '_set_default_idea_properties')
    @mock.patch('os.path.exists')
    def test_set_idea_properties_called(self, mock_file_exists,
                                        mock_set_default,
                                        mock_reset_file_size):
        """Test _set_default_idea_properties() method is called."""
        mock_file_exists.return_value = False
        cfg = config.IdeaProperties(IdeaPropertiesUnittests._CONFIG_DIR)
        cfg.set_max_file_size()
        self.assertTrue(mock_set_default.called)
        self.assertFalse(mock_reset_file_size.called)

    @mock.patch.object(config.IdeaProperties, '_reset_max_file_size')
    @mock.patch.object(config.IdeaProperties, '_set_default_idea_properties')
    @mock.patch('os.path.exists')
    def test_reset_properties_called(self, mock_file_exists, mock_set_default,
                                     mock_reset_file_size):
        """Test _reset_max_file_size() method is called."""
        mock_file_exists.return_value = True
        cfg = config.IdeaProperties(IdeaPropertiesUnittests._CONFIG_DIR)
        cfg.set_max_file_size()
        self.assertFalse(mock_set_default.called)
        self.assertTrue(mock_reset_file_size.called)

if __name__ == '__main__':
    unittest.main()
