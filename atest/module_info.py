# Copyright 2018, The Android Open Source Project
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

"""
Module Info class used to hold cached module-info.json.
"""

# pylint: disable=line-too-long

import json
import logging
import os
import shutil
import sys
import tempfile
import time

import atest_utils
import constants

from metrics import metrics

# JSON file generated by build system that lists all buildable targets.
_MODULE_INFO = 'module-info.json'
# JSON file generated by build system that lists dependencies for java.
_JAVA_DEP_INFO = 'module_bp_java_deps.json'
# JSON file generated by build system that lists dependencies for cc.
_CC_DEP_INFO = 'module_bp_cc_deps.json'
# JSON file generated by atest merged the content from module-info,
# module_bp_java_deps.json, and module_bp_cc_deps.
_MERGED_INFO = 'atest_merged_dep.json'

class ModuleInfo:
    """Class that offers fast/easy lookup for Module related details."""

    def __init__(self, force_build=False, module_file=None):
        """Initialize the ModuleInfo object.

        Load up the module-info.json file and initialize the helper vars.

        Args:
            force_build: Boolean to indicate if we should rebuild the
                         module_info file regardless if it's created or not.
            module_file: String of path to file to load up. Used for testing.
        """
        module_info_target, name_to_module_info = self._load_module_info_file(
            force_build, module_file)
        self.name_to_module_info = name_to_module_info
        self.module_info_target = module_info_target
        self.path_to_module_info = self._get_path_to_module_info(
            self.name_to_module_info)
        self.root_dir = os.environ.get(constants.ANDROID_BUILD_TOP)

    @staticmethod
    def _discover_mod_file_and_target(force_build):
        """Find the module file.

        Args:
            force_build: Boolean to indicate if we should rebuild the
                         module_info file regardless if it's created or not.

        Returns:
            Tuple of module_info_target and path to module file.
        """
        logging.debug('Probing and validating module info...')
        module_info_target = None
        root_dir = os.environ.get(constants.ANDROID_BUILD_TOP, '/')
        out_dir = os.environ.get(constants.ANDROID_PRODUCT_OUT, root_dir)
        module_file_path = os.path.join(out_dir, _MODULE_INFO)

        # Check if the user set a custom out directory by comparing the out_dir
        # to the root_dir.
        if out_dir.find(root_dir) == 0:
            # Make target is simply file path no-absolute to root
            module_info_target = os.path.relpath(module_file_path, root_dir)
        else:
            # If the user has set a custom out directory, generate an absolute
            # path for module info targets.
            logging.debug('User customized out dir!')
            module_file_path = os.path.join(
                os.environ.get(constants.ANDROID_PRODUCT_OUT), _MODULE_INFO)
            module_info_target = module_file_path
        # Make sure module-info exist and could be load properly.
        if not atest_utils.is_valid_json_file(module_file_path) or force_build:
            logging.debug('Generating %s - this is required for '
                          'initial runs or forced rebuilds.', _MODULE_INFO)
            build_env = dict(constants.ATEST_BUILD_ENV)
            build_start = time.time()
            if not atest_utils.build([module_info_target],
                                     verbose=logging.getLogger().isEnabledFor(
                                         logging.DEBUG), env_vars=build_env):
                sys.exit(constants.EXIT_CODE_BUILD_FAILURE)
            build_duration = time.time() - build_start
            metrics.LocalDetectEvent(
                detect_type=constants.DETECT_TYPE_ONLY_BUILD_MODULE_INFO,
                result=int(build_duration))
        return module_info_target, module_file_path

    def _load_module_info_file(self, force_build, module_file):
        """Load the module file.

        Args:
            force_build: Boolean to indicate if we should rebuild the
                         module_info file regardless if it's created or not.
            module_file: String of path to file to load up. Used for testing.

        Returns:
            Tuple of module_info_target and dict of json.
        """
        # If module_file is specified, we're testing so we don't care if
        # module_info_target stays None.
        module_info_target = None
        file_path = module_file
        if not file_path:
            module_info_target, file_path = self._discover_mod_file_and_target(
                force_build)
        merged_file_path = self.get_atest_merged_info_path()
        if (not self.need_update_merged_file(force_build)
            and os.path.exists(merged_file_path)):
            file_path = merged_file_path
            logging.debug('Loading %s as module-info.', file_path)
        with open(file_path) as json_file:
            mod_info = json.load(json_file)
        if self.need_update_merged_file(force_build):
            mod_info = self._merge_build_system_infos(mod_info)
        return module_info_target, mod_info

    @staticmethod
    def _get_path_to_module_info(name_to_module_info):
        """Return the path_to_module_info dict.

        Args:
            name_to_module_info: Dict of module name to module info dict.

        Returns:
            Dict of module path to module info dict.
        """
        path_to_module_info = {}
        for mod_name, mod_info in name_to_module_info.items():
            # Cross-compiled and multi-arch modules actually all belong to
            # a single target so filter out these extra modules.
            if mod_name != mod_info.get(constants.MODULE_NAME, ''):
                continue
            for path in mod_info.get(constants.MODULE_PATH, []):
                mod_info[constants.MODULE_NAME] = mod_name
                # There could be multiple modules in a path.
                if path in path_to_module_info:
                    path_to_module_info[path].append(mod_info)
                else:
                    path_to_module_info[path] = [mod_info]
        return path_to_module_info

    def is_module(self, name):
        """Return True if name is a module, False otherwise."""
        if self.get_module_info(name):
            return True
        return False

    def get_paths(self, name):
        """Return paths of supplied module name, Empty list if non-existent."""
        info = self.get_module_info(name)
        if info:
            return info.get(constants.MODULE_PATH, [])
        return []

    def get_module_names(self, rel_module_path):
        """Get the modules that all have module_path.

        Args:
            rel_module_path: path of module in module-info.json

        Returns:
            List of module names.
        """
        return [m.get(constants.MODULE_NAME)
                for m in self.path_to_module_info.get(rel_module_path, [])]

    def get_module_info(self, mod_name):
        """Return dict of info for given module name, None if non-existence."""
        module_info = self.name_to_module_info.get(mod_name)
        # Android's build system will automatically adding 2nd arch bitness
        # string at the end of the module name which will make atest could not
        # find the matched module. Rescan the module-info with the matched module
        # name without bitness.
        if not module_info:
            for _, mod_info in self.name_to_module_info.items():
                if mod_name == mod_info.get(constants.MODULE_NAME, ''):
                    return mod_info
        return module_info

    def is_suite_in_compatibility_suites(self, suite, mod_info):
        """Check if suite exists in the compatibility_suites of module-info.

        Args:
            suite: A string of suite name.
            mod_info: Dict of module info to check.

        Returns:
            True if it exists in mod_info, False otherwise.
        """
        return suite in mod_info.get(constants.MODULE_COMPATIBILITY_SUITES, [])

    def get_testable_modules(self, suite=None):
        """Return the testable modules of the given suite name.

        Args:
            suite: A string of suite name. Set to None to return all testable
            modules.

        Returns:
            List of testable modules. Empty list if non-existent.
            If suite is None, return all the testable modules in module-info.
        """
        modules = set()
        for _, info in self.name_to_module_info.items():
            if self.is_testable_module(info):
                if suite:
                    if self.is_suite_in_compatibility_suites(suite, info):
                        modules.add(info.get(constants.MODULE_NAME))
                else:
                    modules.add(info.get(constants.MODULE_NAME))
        return modules

    def is_testable_module(self, mod_info):
        """Check if module is something we can test.

        A module is testable if:
          - it's installed, or
          - it's a robolectric module (or shares path with one).

        Args:
            mod_info: Dict of module info to check.

        Returns:
            True if we can test this module, False otherwise.
        """
        if not mod_info:
            return False
        if mod_info.get(constants.MODULE_INSTALLED) and self.has_test_config(mod_info):
            return True
        if self.is_robolectric_test(mod_info.get(constants.MODULE_NAME)):
            return True
        return False

    def has_test_config(self, mod_info):
        """Validate if this module has a test config.

        A module can have a test config in the following manner:
          - AndroidTest.xml at the module path.
          - test_config be set in module-info.json.
          - Auto-generated config via the auto_test_config key
            in module-info.json.

        Args:
            mod_info: Dict of module info to check.

        Returns:
            True if this module has a test config, False otherwise.
        """
        # Check if test_config in module-info is set.
        for test_config in mod_info.get(constants.MODULE_TEST_CONFIG, []):
            if os.path.isfile(os.path.join(self.root_dir, test_config)):
                return True
        # Check for AndroidTest.xml at the module path.
        for path in mod_info.get(constants.MODULE_PATH, []):
            if os.path.isfile(os.path.join(self.root_dir, path,
                                           constants.MODULE_CONFIG)):
                return True
        # Check if the module has an auto-generated config.
        return self.is_auto_gen_test_config(mod_info.get(constants.MODULE_NAME))

    def get_robolectric_test_name(self, module_name):
        """Returns runnable robolectric module name.

        There are at least 2 modules in every robolectric module path, return
        the module that we can run as a build target.

        Arg:
            module_name: String of module.

        Returns:
            String of module that is the runnable robolectric module, None if
            none could be found.
        """
        module_name_info = self.get_module_info(module_name)
        if not module_name_info:
            return None
        module_paths = module_name_info.get(constants.MODULE_PATH, [])
        if module_paths:
            for mod in self.get_module_names(module_paths[0]):
                mod_info = self.get_module_info(mod)
                if self.is_robolectric_module(mod_info):
                    return mod
        return None

    def is_robolectric_test(self, module_name):
        """Check if module is a robolectric test.

        A module can be a robolectric test if the specified module has their
        class set as ROBOLECTRIC (or shares their path with a module that does).

        Args:
            module_name: String of module to check.

        Returns:
            True if the module is a robolectric module, else False.
        """
        # Check 1, module class is ROBOLECTRIC
        mod_info = self.get_module_info(module_name)
        if self.is_robolectric_module(mod_info):
            return True
        # Check 2, shared modules in the path have class ROBOLECTRIC_CLASS.
        if self.get_robolectric_test_name(module_name):
            return True
        return False

    def is_auto_gen_test_config(self, module_name):
        """Check if the test config file will be generated automatically.

        Args:
            module_name: A string of the module name.

        Returns:
            True if the test config file will be generated automatically.
        """
        if self.is_module(module_name):
            mod_info = self.get_module_info(module_name)
            auto_test_config = mod_info.get('auto_test_config', [])
            return auto_test_config and auto_test_config[0]
        return False

    def is_robolectric_module(self, mod_info):
        """Check if a module is a robolectric module.

        Args:
            mod_info: ModuleInfo to check.

        Returns:
            True if module is a robolectric module, False otherwise.
        """
        if mod_info:
            return (mod_info.get(constants.MODULE_CLASS, [None])[0] ==
                    constants.MODULE_CLASS_ROBOLECTRIC)
        return False

    def is_native_test(self, module_name):
        """Check if the input module is a native test.

        Args:
            module_name: A string of the module name.

        Returns:
            True if the test is a native test, False otherwise.
        """
        mod_info = self.get_module_info(module_name)
        return constants.MODULE_CLASS_NATIVE_TESTS in mod_info.get(
            constants.MODULE_CLASS, [])

    def has_mainline_modules(self, module_name, mainline_modules):
        """Check if the mainline modules are in module-info.

        Args:
            module_name: A string of the module name.
            mainline_modules: A list of mainline modules.

        Returns:
            True if mainline_modules is in module-info, False otherwise.
        """
        # TODO: (b/165425972)Check AndroidTest.xml or specific test config.
        mod_info = self.get_module_info(module_name)
        if mainline_modules in mod_info.get(constants.MODULE_MAINLINE_MODULES,
                                            []):
            return True
        return False

    def generate_atest_merged_dep_file(self):
        """Method for generating atest_merged_dep.json."""
        self._merge_build_system_infos(self.name_to_module_info,
                                       self.get_java_dep_info_path(),
                                       self.get_cc_dep_info_path())

    def _merge_build_system_infos(self, name_to_module_info,
        java_bp_info_path=None, cc_bp_info_path=None):
        """Merge the full build system's info to name_to_module_info.

        Args:
            name_to_module_info: Dict of module name to module info dict.
            java_bp_info_path: String of path to java dep file to load up.
                               Used for testing.
            cc_bp_info_path: String of path to cc dep file to load up.
                             Used for testing.

        Returns:
            Dict of merged json of input def_file_path and name_to_module_info.
        """
        # Merge _JAVA_DEP_INFO
        if not java_bp_info_path:
            java_bp_info_path = self.get_java_dep_info_path()
        if atest_utils.is_valid_json_file(java_bp_info_path):
            with open(java_bp_info_path) as json_file:
                java_bp_infos = json.load(json_file)
                logging.debug('Merging Java build info: %s', java_bp_info_path)
                name_to_module_info = self._merge_soong_info(
                    name_to_module_info, java_bp_infos)
        # Merge _CC_DEP_INFO
        if not cc_bp_info_path:
            cc_bp_info_path = self.get_cc_dep_info_path()
        if atest_utils.is_valid_json_file(cc_bp_info_path):
            with open(cc_bp_info_path) as json_file:
                cc_bp_infos = json.load(json_file)
            logging.debug('Merging CC build info: %s', cc_bp_info_path)
            # CC's dep json format is different with java.
            # Below is the example content:
            # {
            #   "clang": "${ANDROID_ROOT}/bin/clang",
            #   "clang++": "${ANDROID_ROOT}/bin/clang++",
            #   "modules": {
            #       "ACameraNdkVendorTest": {
            #           "path": [
            #                   "frameworks/av/camera/ndk"
            #           ],
            #           "srcs": [
            #                   "frameworks/tests/AImageVendorTest.cpp",
            #                   "frameworks/tests/ACameraManagerTest.cpp"
            #           ],
            name_to_module_info = self._merge_soong_info(
                name_to_module_info, cc_bp_infos.get('modules', {}))
        return name_to_module_info

    def _merge_soong_info(self, name_to_module_info, mod_bp_infos):
        """Merge the dependency and srcs in mod_bp_infos to name_to_module_info.

        Args:
            name_to_module_info: Dict of module name to module info dict.
            mod_bp_infos: Dict of module name to bp's module info dict.

        Returns:
            Dict of merged json of input def_file_path and name_to_module_info.
        """
        merge_items = [constants.MODULE_DEPENDENCIES, constants.MODULE_SRCS]
        for module_name, dep_info in mod_bp_infos.items():
            if name_to_module_info.get(module_name, None):
                mod_info = name_to_module_info.get(module_name)
                for merge_item in merge_items:
                    dep_info_values = dep_info.get(merge_item, [])
                    mod_info_values = mod_info.get(merge_item, [])
                    for dep_info_value in dep_info_values:
                        if dep_info_value not in mod_info_values:
                            mod_info_values.append(dep_info_value)
                    mod_info_values.sort()
                    name_to_module_info[
                        module_name][merge_item] = mod_info_values
        output_file = self.get_atest_merged_info_path()
        if not os.path.isdir(os.path.dirname(output_file)):
            os.makedirs(os.path.dirname(output_file))
        # b/178559543 saving merged module info in a temp file and copying it to
        # atest_merged_dep.json can eliminate the possibility of accessing it
        # concurrently and resulting in invalid JSON format.
        temp_file = tempfile.NamedTemporaryFile()
        with open(temp_file.name, 'w') as _temp:
            json.dump(name_to_module_info, _temp, indent=0)
        shutil.copy(temp_file.name, output_file)
        temp_file.close()
        return name_to_module_info

    def get_module_dependency(self, module_name, depend_on=None):
        """Get the dependency sets for input module.

        Recursively find all the dependencies of the input module.

        Args:
            module_name: String of module to check.
            depend_on: The list of parent dependencies.

        Returns:
            Set of dependency modules.
        """
        if not depend_on:
            depend_on = set()
        deps = set()
        mod_info = self.get_module_info(module_name)
        if not mod_info:
            return deps
        mod_deps = set(mod_info.get(constants.MODULE_DEPENDENCIES, []))
        # Remove item in deps if it already in depend_on:
        mod_deps = mod_deps - depend_on
        deps = deps.union(mod_deps)
        for mod_dep in mod_deps:
            deps = deps.union(set(self.get_module_dependency(
                mod_dep, depend_on=depend_on.union(deps))))
        return deps

    def get_install_module_dependency(self, module_name, depend_on=None):
        """Get the dependency set for the given modules with installed path.

        Args:
            module_name: String of module to check.
            depend_on: The list of parent dependencies.

        Returns:
            Set of dependency modules which has installed path.
        """
        install_deps = set()
        deps = self.get_module_dependency(module_name, depend_on)
        logging.debug('%s depends on: %s', module_name, deps)
        for module in deps:
            mod_info = self.get_module_info(module)
            if mod_info and mod_info.get(constants.MODULE_INSTALLED, []):
                install_deps.add(module)
        logging.debug('modules %s required by %s were not installed',
                      install_deps, module_name)
        return install_deps

    @staticmethod
    def get_atest_merged_info_path():
        """Returns the path for atest_merged_dep.json.

        Returns:
            String for atest_merged_dep.json.
        """
        return os.path.join(atest_utils.get_build_out_dir(),
                            'soong', _MERGED_INFO)

    @staticmethod
    def get_java_dep_info_path():
        """Returns the path for atest_merged_dep.json.

        Returns:
            String for atest_merged_dep.json.
        """
        return os.path.join(atest_utils.get_build_out_dir(),
                            'soong', _JAVA_DEP_INFO)

    @staticmethod
    def get_cc_dep_info_path():
        """Returns the path for atest_merged_dep.json.

        Returns:
            String for atest_merged_dep.json.
        """
        return os.path.join(atest_utils.get_build_out_dir(),
                            'soong', _CC_DEP_INFO)

    def has_soong_info(self):
        """Ensure the existence of soong info files.

        Returns:
            True if soong info need to merge, false otherwise.
        """
        return (os.path.isfile(self.get_java_dep_info_path()) and
                os.path.isfile(self.get_cc_dep_info_path()))

    def need_update_merged_file(self, force_build=False):
        """Check if need to update/generated atest_merged_dep.

        If force_build, always update merged info.
        If not force build, if soong info exist but merged inforamtion not exist,
        need to update merged file.

        Args:
            force_build: Boolean to indicate that if user want to rebuild
                         module_info file regardless if it's created or not.

        Returns:
            True if atest_merged_dep should be updated, false otherwise.
        """
        return (force_build or
                (self.has_soong_info() and
                 not os.path.exists(self.get_atest_merged_info_path())))

    def is_unit_test(self, mod_info):
        """Return True if input module is unit test, False otherwise.

        Args:
            mod_info: ModuleInfo to check.

        Returns:
            True if if input module is unit test, False otherwise.
        """
        return mod_info.get(constants.MODULE_IS_UNIT_TEST, '') == 'true'

    def get_all_unit_tests(self):
        """Get a list of all the module names which are unit tests."""
        unit_tests = []
        for mod_name, mod_info in self.name_to_module_info.items():
            if mod_info.get(constants.MODULE_NAME, '') == mod_name:
                if self.is_unit_test(mod_info):
                    unit_tests.append(mod_name)
        return unit_tests
