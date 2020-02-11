#!/usr/bin/env python3
#
# Copyright 2019 - The Android Open Source Project
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

"""native_module_info

Module Info class used to hold cached module_bp_cc_deps.json.
"""

import os

from aidegen import constant
from aidegen.lib import common_util
from aidegen.lib import module_info

_CLANG = 'clang'
_CPPLANG = 'clang++'
_MODULES = 'modules'


class NativeModuleInfo(module_info.AidegenModuleInfo):
    """Class that offers fast/easy lookup for module related details.

    Class Attributes:
        c_lang_path: Make C files compiler path.
        cpp_lang_path: Make C++ files compiler path.
    """

    c_lang_path = ''
    cpp_lang_path = ''

    def __init__(self, force_build=False, module_file=None):
        """Initialize the NativeModuleInfo object.

        Load up the module_bp_cc_deps.json file and initialize the helper vars.
        """
        if not module_file:
            module_file = common_util.get_blueprint_json_path(
                constant.BLUEPRINT_CC_JSONFILE_NAME)
        if not os.path.isfile(module_file):
            force_build = True
        super().__init__(force_build, module_file)

    def _load_module_info_file(self, force_build, module_file):
        """Load the module file.

        Args:
            force_build: Boolean to indicate if we should rebuild the
                         module_info file regardless if it's created or not.
            module_file: String of path to file to load up. Used for testing.

        Returns:
            Tuple of module_info_target and dict of json.
        """
        if force_build:
            self._discover_mod_file_and_target(True)
        mod_info = common_util.get_json_dict(module_file)
        NativeModuleInfo.c_lang_path = mod_info.get(_CLANG, '')
        NativeModuleInfo.cpp_lang_path = mod_info.get(_CPPLANG, '')
        name_to_module_info = mod_info.get(_MODULES, {})
        root_dir = common_util.get_android_root_dir()
        module_info_target = os.path.relpath(module_file, root_dir)
        return module_info_target, name_to_module_info

    def get_module_names_in_targets_paths(self, targets):
        """Gets module names exist in native_module_info.

        Args:
            targets: A list of build targets to be checked.

        Returns:
            A list of native projects' names if native projects exist otherwise
            return None.
        """
        projects = []
        for target in targets:
            if target == constant.WHOLE_ANDROID_TREE_TARGET:
                print('Do not deal with whole source tree in native projects.')
                continue
            rel_path, _ = common_util.get_related_paths(self, target)
            for path in self.path_to_module_info:
                if path.startswith(rel_path):
                    projects.extend(self.get_module_names(path))
        return projects

    def is_suite_in_compatibility_suites(self, suite, mod_info):
        raise NotImplementedError()

    def get_testable_modules(self, suite=None):
        raise NotImplementedError()

    def is_testable_module(self, mod_info):
        raise NotImplementedError()

    def has_test_config(self, mod_info):
        raise NotImplementedError()

    def get_robolectric_test_name(self, module_name):
        raise NotImplementedError()

    def is_robolectric_test(self, module_name):
        raise NotImplementedError()

    def is_auto_gen_test_config(self, module_name):
        raise NotImplementedError()

    def is_robolectric_module(self, mod_info):
        raise NotImplementedError()

    def is_native_test(self, module_name):
        raise NotImplementedError()
