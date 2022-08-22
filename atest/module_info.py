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
import pickle
import shutil
import tempfile
import time

from pathlib import Path
from typing import Any, Dict, Set

import atest_utils
import constants

from atest_enum import DetectType
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


Module = Dict[str, Any]


class ModuleInfo:
    """Class that offers fast/easy lookup for Module related details."""

    def __init__(self, force_build=False, module_file=None, index_dir=None):
        """Initialize the ModuleInfo object.

        Load up the module-info.json file and initialize the helper vars.
        Note that module-info.json does not contain all module dependencies,
        therefore, Atest needs to accumulate dependencies defined in bp files.

          +----------------------+     +----------------------------+
          | $ANDROID_PRODUCT_OUT |     |$ANDROID_BUILD_TOP/out/soong|
          |  /module-info.json   |     |  /module_bp_java_deps.json |
          +-----------+----------+     +-------------+--------------+
                      |     _merge_soong_info()      |
                      +------------------------------+
                      |
                      v
        +----------------------------+  +----------------------------+
        |tempfile.NamedTemporaryFile |  |$ANDROID_BUILD_TOP/out/soong|
        +-------------+--------------+  |  /module_bp_cc_deps.json   |
                      |                 +-------------+--------------+
                      |     _merge_soong_info()       |
                      +-------------------------------+
                                     |
                             +-------|
                             v
                +============================+
                |  $ANDROID_PRODUCT_OUT      |
                |    /atest_merged_dep.json  |--> load as module info.
                +============================+

        Args:
            force_build: Boolean to indicate if we should rebuild the
                         module_info file regardless if it's created or not.
            module_file: String of path to file to load up. Used for testing.
            index_dir: String of path to store testable module index and md5.
        """
        # force_build could be from "-m" or smart_build(build files change).
        self.force_build = force_build
        # update_merge_info flag will merge dep files only when any of them have
        # changed even force_build == True.
        self.update_merge_info = False
        # Index and checksum files that will be used.
        if not index_dir:
            index_dir = Path(
                os.getenv(constants.ANDROID_HOST_OUT,
                          tempfile.TemporaryDirectory().name)).joinpath('indexes')
        index_dir = Path(index_dir)
        if not index_dir.is_dir():
            index_dir.mkdir(parents=True)
        self.module_index = index_dir.joinpath(constants.MODULE_INDEX)
        self.module_info_checksum = index_dir.joinpath(constants.MODULE_INFO_MD5)

        # Paths to java, cc and merged module info json files.
        self.java_dep_path = Path(
            atest_utils.get_build_out_dir()).joinpath('soong', _JAVA_DEP_INFO)
        self.cc_dep_path = Path(
            atest_utils.get_build_out_dir()).joinpath('soong', _CC_DEP_INFO)
        self.merged_dep_path = Path(
            os.getenv(constants.ANDROID_PRODUCT_OUT, '')).joinpath(_MERGED_INFO)

        self.mod_info_file_path = Path(module_file) if module_file else None
        module_info_target, name_to_module_info = self._load_module_info_file(
            module_file)
        self.name_to_module_info = name_to_module_info
        self.module_info_target = module_info_target
        self.path_to_module_info = self._get_path_to_module_info(
            self.name_to_module_info)
        self.root_dir = os.environ.get(constants.ANDROID_BUILD_TOP)
        self.module_index_proc = None
        if self.update_merge_info or not self.module_index.is_file():
            # Assumably null module_file reflects a common run, and index testable
            # modules only when common runs.
            if not module_file:
                self.module_index_proc = atest_utils.run_multi_proc(
                    func=self._get_testable_modules,
                    kwargs={'index': True})

    @staticmethod
    def _discover_mod_file_and_target(force_build):
        """Find the module file.

        Args:
            force_build: Boolean to indicate if we should rebuild the
                         module_info file regardless of the existence of it.

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
        if force_build:
            atest_utils.build_module_info_target(module_info_target)
        return module_info_target, module_file_path

    def _load_module_info_file(self, module_file):
        """Load the module file.

        No matter whether passing module_file or not, ModuleInfo will load
        atest_merged_dep.json as module info eventually.

        +--------------+                  +----------------------------------+
        | ModuleInfo() |                  | ModuleInfo(module_file=foo.json) |
        +-------+------+                  +----------------+-----------------+
                | _discover_mod_file_and_target()          |
                | atest_utils.build()                      | load
                v                                          V
        +--------------------------+         +--------------------------+
        | module-info.json         |         | foo.json                 |
        | module_bp_cc_deps.json   |         | module_bp_cc_deps.json   |
        | module_bp_java_deps.json |         | module_bp_java_deps.json |
        +--------------------------+         +--------------------------+
                |                                          |
                | _merge_soong_info() <--------------------+
                v
        +============================+
        |  $ANDROID_PRODUCT_OUT      |
        |    /atest_merged_dep.json  |--> load as module info.
        +============================+

        Args:
            module_file: String of path to file to load up. Used for testing.
                         Note: if set, ModuleInfo will skip build process.

        Returns:
            Tuple of module_info_target and dict of json.
        """
        # If module_file is specified, we're gonna test it so we don't care if
        # module_info_target stays None.
        module_info_target = None
        file_path = module_file
        previous_checksum = self._get_module_info_checksums()
        if not file_path:
            module_info_target, file_path = self._discover_mod_file_and_target(
                self.force_build)
            self.mod_info_file_path = Path(file_path)
        # Even undergone a rebuild after _discover_mod_file_and_target(), merge
        # atest_merged_dep.json only when module_deps_infos actually change so
        # that Atest can decrease disk I/O and ensure data accuracy at all.
        module_deps_infos = [file_path, self.java_dep_path, self.cc_dep_path]
        self._save_module_info_checksum(module_deps_infos)
        self.update_merge_info = self.need_update_merged_file(previous_checksum)
        start = time.time()
        if self.update_merge_info:
            # Load the $ANDROID_PRODUCT_OUT/module-info.json for merging.
            module_info_json = atest_utils.load_json_safely(file_path)
            if Path(file_path).name == _MODULE_INFO and not module_info_json:
                # Rebuild module-info.json when it has invalid format. However,
                # if the file_path doesn't end with module-info.json, it could
                # be from unit tests and won't trigger rebuild.
                atest_utils.build_module_info_target(module_info_target)
                start = time.time()
                module_info_json = atest_utils.load_json_safely(file_path)
            mod_info = self._merge_build_system_infos(module_info_json)
            duration = time.time() - start
            logging.debug('Merging module info took %ss', duration)
            metrics.LocalDetectEvent(
                detect_type=DetectType.MODULE_MERGE_MS, result=int(duration*1000))
        else:
            # Load $ANDROID_PRODUCT_OUT/atest_merged_dep.json directly.
            with open(self.merged_dep_path) as merged_info_json:
                mod_info = json.load(merged_info_json)
            duration = time.time() - start
            logging.debug('Loading module info took %ss', duration)
            metrics.LocalDetectEvent(
                detect_type=DetectType.MODULE_LOAD_MS, result=int(duration*1000))
        _add_missing_variant_modules(mod_info)
        logging.debug('Loading %s as module-info.', self.merged_dep_path)
        return module_info_target, mod_info

    def _get_module_info_checksums(self):
        """Load the module-info.md5 and return the content.

        Returns:
            A dict of filename and checksum.
        """
        return atest_utils.load_json_safely(self.module_info_checksum)

    def _save_module_info_checksum(self, filenames):
        """Dump the checksum of essential module info files.
           * module-info.json
           * module_bp_cc_deps.json
           * module_bp_java_deps.json
        """
        dirname = Path(self.module_info_checksum).parent
        if not dirname.is_dir():
            dirname.mkdir(parents=True)
        atest_utils.save_md5(filenames, self.module_info_checksum)

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

    def _index_testable_modules(self, content):
        """Dump testable modules.

        Args:
            content: An object that will be written to the index file.
        """
        logging.debug(r'Indexing testable modules... '
                      r'(This is required whenever module-info.json '
                      r'was rebuilt.)')
        Path(self.module_index).parent.mkdir(parents=True, exist_ok=True)
        with open(self.module_index, 'wb') as cache:
            try:
                pickle.dump(content, cache, protocol=2)
            except IOError:
                logging.error('Failed in dumping %s', cache)
                os.remove(cache)

    def _get_testable_modules(self, index=False, suite=None):
        """Return all available testable modules and index them.

        Args:
            index: boolean that determines running _index_testable_modules().
            suite: string for the suite name.

        Returns:
            Set of all testable modules.
        """
        modules = set()
        begin = time.time()
        for _, info in self.name_to_module_info.items():
            if self.is_testable_module(info):
                modules.add(info.get(constants.MODULE_NAME))
        logging.debug('Probing all testable modules took %ss',
                      time.time() - begin)
        if index:
            self._index_testable_modules(modules)
        if suite:
            _modules = set()
            for module_name in modules:
                info = self.get_module_info(module_name)
                if self.is_suite_in_compatibility_suites(suite, info):
                    _modules.add(info.get(constants.MODULE_NAME))
            return _modules
        return modules

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
        return self.name_to_module_info.get(mod_name)

    def is_suite_in_compatibility_suites(self, suite, mod_info):
        """Check if suite exists in the compatibility_suites of module-info.

        Args:
            suite: A string of suite name.
            mod_info: Dict of module info to check.

        Returns:
            True if it exists in mod_info, False otherwise.
        """
        if mod_info:
            return suite in mod_info.get(
                constants.MODULE_COMPATIBILITY_SUITES, [])
        return []

    def get_testable_modules(self, suite=None):
        """Return the testable modules of the given suite name.

        Atest does not index testable modules against compatibility_suites. When
        suite was given, or the index file was interrupted, always run
        _get_testable_modules() and re-index.

        Args:
            suite: A string of suite name.

        Returns:
            If suite is not given, return all the testable modules in module
            info, otherwise return only modules that belong to the suite.
        """
        modules = set()
        start = time.time()
        if self.module_index_proc:
            self.module_index_proc.join()

        if self.module_index.is_file():
            if not suite:
                with open(self.module_index, 'rb') as cache:
                    try:
                        modules = pickle.load(cache, encoding="utf-8")
                    except UnicodeDecodeError:
                        modules = pickle.load(cache)
                    # when module indexing was interrupted.
                    except EOFError:
                        pass
            else:
                modules = self._get_testable_modules(suite=suite)
        # If the modules.idx does not exist or invalid for any reason, generate
        # a new one arbitrarily.
        if not modules:
            if not suite:
                modules = self._get_testable_modules(index=True)
            else:
                modules = self._get_testable_modules(index=True, suite=suite)
        duration = time.time() - start
        metrics.LocalDetectEvent(
            detect_type=DetectType.TESTABLE_MODULES,
            result=int(duration))
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
        if all((mod_info.get(constants.MODULE_INSTALLED, []),
                self.has_test_config(mod_info))):
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

        This method is for legacy robolectric tests and returns one of associated
        modules. The pattern is determined by the amount of shards:

        10 shards:
            FooTests -> RunFooTests0, RunFooTests1 ... RunFooTests9
        No shard:
            FooTests -> RunFooTests

        Arg:
            module_name: String of module.

        Returns:
            String of the first-matched associated module that belongs to the
            actual robolectric module, None if nothing has been found.
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
        """Check if the given module is a robolectric test.

        Args:
            module_name: String of module to check.

        Returns:
            Boolean whether it's a robotest or not.
        """
        if self.get_robolectric_type(module_name):
            return True
        return False

    def get_robolectric_type(self, module_name):
        """Check if the given module is a robolectric test and return type of it.

        Robolectric declaration is converting from Android.mk to Android.bp, and
        in the interim Atest needs to support testing both types of tests.

        The modern robolectric tests defined by 'android_robolectric_test' in an
        Android.bp file can can be run in Tradefed Test Runner:

            SettingsRoboTests -> Tradefed Test Runner

        Legacy tests defined in an Android.mk can only run with the 'make' way.

            SettingsRoboTests -> make RunSettingsRoboTests0

        To determine whether the test is a modern/legacy robolectric test:
            1. Traverse all modules share the module path. If one of the
               modules has a ROBOLECTRIC class, it is a robolectric test.
            2. If found an Android.bp in that path, it's a modern one, otherwise
               it's a legacy test and will go to the build route.

        Args:
            module_name: String of module to check.

        Returns:
            0: not a robolectric test.
            1: a modern robolectric test(defined in Android.bp)
            2: a legacy robolectric test(defined in Android.mk)
        """
        not_a_robo_test = 0
        module_name_info = self.get_module_info(module_name)
        if not module_name_info:
            return not_a_robo_test
        mod_path = module_name_info.get(constants.MODULE_PATH, [])
        if mod_path:
            # Check1: If the associated modules are "ROBOLECTRIC".
            is_a_robotest = False
            modules_in_path = self.get_module_names(mod_path[0])
            for mod in modules_in_path:
                mod_info = self.get_module_info(mod)
                if self.is_robolectric_module(mod_info):
                    is_a_robotest = True
                    break
            if not is_a_robotest:
                return not_a_robo_test
            # Check 2: If found Android.bp in path, call it a modern test.
            bpfile = os.path.join(self.root_dir, mod_path[0], 'Android.bp')
            if os.path.isfile(bpfile):
                return constants.ROBOTYPE_MODERN
            return constants.ROBOTYPE_LEGACY
        return not_a_robo_test

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

        This method is for legacy robolectric tests that the associated modules
        contain:
            'class': ['ROBOLECTRIC']

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
        mod_info = self.get_module_info(module_name)
        # Check 'test_mainline_modules' attribute of the module-info.json.
        if mainline_modules in mod_info.get(constants.MODULE_MAINLINE_MODULES,
                                            []):
            return True
        for test_config in mod_info.get(constants.MODULE_TEST_CONFIG, []):
            # Check the value of 'mainline-param' in the test config.
            if not self.is_auto_gen_test_config(module_name):
                return mainline_modules in atest_utils.get_mainline_param(
                    os.path.join(self.root_dir, test_config))
            # Unable to verify mainline modules in an auto-gen test config.
            logging.debug('%s is associated with an auto-generated test config.',
                          module_name)
            return True

    def _merge_build_system_infos(self, name_to_module_info,
        java_bp_info_path=None, cc_bp_info_path=None):
        """Merge the content of module-info.json and CC/Java dependency files
        to name_to_module_info.

        Args:
            name_to_module_info: Dict of module name to module info dict.
            java_bp_info_path: String of path to java dep file to load up.
                               Used for testing.
            cc_bp_info_path: String of path to cc dep file to load up.
                             Used for testing.

        Returns:
            Dict of updated name_to_module_info.
        """
        # Merge _JAVA_DEP_INFO
        if not java_bp_info_path:
            java_bp_info_path = self.java_dep_path
        java_bp_infos = atest_utils.load_json_safely(java_bp_info_path)
        if java_bp_infos:
            logging.debug('Merging Java build info: %s', java_bp_info_path)
            name_to_module_info = self._merge_soong_info(
                name_to_module_info, java_bp_infos)
        # Merge _CC_DEP_INFO
        if not cc_bp_info_path:
            cc_bp_info_path = self.cc_dep_path
        cc_bp_infos = atest_utils.load_json_safely(cc_bp_info_path)
        if cc_bp_infos:
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
        # If $ANDROID_PRODUCT_OUT was not created in pyfakefs, simply return it
        # without dumping atest_merged_dep.json in real.
        if not self.merged_dep_path.parent.is_dir():
            return name_to_module_info
        # b/178559543 saving merged module info in a temp file and copying it to
        # atest_merged_dep.json can eliminate the possibility of accessing it
        # concurrently and resulting in invalid JSON format.
        temp_file = tempfile.NamedTemporaryFile()
        with open(temp_file.name, 'w') as _temp:
            json.dump(name_to_module_info, _temp, indent=0)
        shutil.copy(temp_file.name, self.merged_dep_path)
        temp_file.close()
        return name_to_module_info

    def _merge_soong_info(self, name_to_module_info, mod_bp_infos):
        """Merge the dependency and srcs in mod_bp_infos to name_to_module_info.

        Args:
            name_to_module_info: Dict of module name to module info dict.
            mod_bp_infos: Dict of module name to bp's module info dict.

        Returns:
            Dict of updated name_to_module_info.
        """
        merge_items = [constants.MODULE_DEPENDENCIES, constants.MODULE_SRCS,
                       constants.MODULE_LIBS, constants.MODULE_STATIC_LIBS]
        for module_name, dep_info in mod_bp_infos.items():
            if name_to_module_info.get(module_name, None):
                mod_info = name_to_module_info.get(module_name)
                for merge_item in merge_items:
                    dep_info_values = dep_info.get(merge_item, [])
                    mod_info_values = mod_info.get(merge_item, [])
                    mod_info_values.extend(dep_info_values)
                    mod_info_values.sort()
                    # deduplicate values just in case.
                    mod_info_values = list(dict.fromkeys(mod_info_values))
                    name_to_module_info[
                        module_name][merge_item] = mod_info_values
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

    def need_update_merged_file(self, checksum):
        """Check if need to update/generated atest_merged_dep.

        There are 2 scienarios that atest_merged_dep.json will be updated.
        1. One of the checksum of module-info.json, module_bp_java_deps.json and
           module_cc_java_deps.json have changed.
        2. atest_merged_deps.json does not exist.

        If fits one of above scienarios, it is recognized to update.

        Returns:
            True if one of the scienarios reaches, False otherwise.
        """
        return (checksum != self._get_module_info_checksums() or
            not Path(self.merged_dep_path).is_file())

    def is_unit_test(self, mod_info):
        """Return True if input module is unit test, False otherwise.

        Args:
            mod_info: ModuleInfo to check.

        Returns:
            True if if input module is unit test, False otherwise.
        """
        return mod_info.get(constants.MODULE_IS_UNIT_TEST, '') == 'true'

    def is_host_unit_test(self, mod_info):
        """Return True if input module is host unit test, False otherwise.

        Args:
            mod_info: ModuleInfo to check.

        Returns:
            True if if input module is host unit test, False otherwise.
        """
        return self.is_suite_in_compatibility_suites(
          'host-unit-tests', mod_info)

    def is_device_driven_test(self, mod_info):
        """Return True if input module is device driven test, False otherwise.

        Args:
            mod_info: ModuleInfo to check.

        Returns:
            True if if input module is device driven test, False otherwise.
        """
        return self.is_testable_module(mod_info) and 'DEVICE' in mod_info.get(
            constants.MODULE_SUPPORTED_VARIANTS, [])

    def _any_module(self, _: Module) -> bool:
        return True

    def get_all_tests(self):
        """Get a list of all the module names which are tests."""
        return self._get_all_modules(type_predicate=self.is_testable_module)

    def get_all_unit_tests(self):
        """Get a list of all the module names which are unit tests."""
        return self._get_all_modules(type_predicate=self.is_unit_test)

    def get_all_host_unit_tests(self):
        """Get a list of all the module names which are host unit tests."""
        return self._get_all_modules(type_predicate=self.is_host_unit_test)

    def get_all_device_driven_tests(self):
        """Get a list of all the module names which are device driven tests."""
        return self._get_all_modules(type_predicate=self.is_device_driven_test)

    def _get_all_modules(self, type_predicate=None):
        """Get a list of all the module names that passed the predicate."""
        modules = []
        type_predicate = type_predicate or self._any_module
        for mod_name, mod_info in self.name_to_module_info.items():
            if mod_info.get(constants.MODULE_NAME, '') == mod_name:
                if type_predicate(mod_info):
                    modules.append(mod_name)
        return modules

    def get_modules_by_path_in_srcs(self, path: str) -> str:
        """Get the module name that the given path belongs to.(in 'srcs')

        Args:
            path: Relative path to ANDROID_BUILD_TOP of a file.

        Returns:
            A set of string for matched module names, empty set if nothing find.
        """
        modules = set()
        for _, mod_info in self.name_to_module_info.items():
            if path in mod_info.get(constants.MODULE_SRCS, []):
                modules.add(mod_info.get(constants.MODULE_NAME))
        return modules

    def get_modules_by_include_deps(
            self, deps: Set[str],
            testable_module_only: bool = False) -> Set[str]:
        """Get the matched module names for the input dependencies.

        Args:
            deps: A set of string for dependencies.
            testable_module_only: Option if only want to get testable module.

        Returns:
            A set of matched module names for the input dependencies.
        """
        modules = set()

        for mod_name in (self.get_testable_modules() if testable_module_only
                         else self.name_to_module_info.keys()):
            mod_info = self.get_module_info(mod_name)
            if mod_info and deps.intersection(
                set(mod_info.get(constants.MODULE_DEPENDENCIES, []))):
                modules.add(mod_info.get(constants.MODULE_NAME))
        return modules


def _add_missing_variant_modules(name_to_module_info: Dict[str, Module]):
    missing_modules = dict()

    # Android's build system automatically adds a suffix for some build module
    # variants. For example, a module-info entry for a module originally named
    # 'HelloWorldTest' might appear as 'HelloWorldTest_32' and which Atest would
    # not be able to find. We add such entries if not already present so they
    # can be looked up using their declared module name.
    for mod_name, mod_info in name_to_module_info.items():
        declared_module_name = mod_info.get(constants.MODULE_NAME)
        if declared_module_name == mod_name:
            continue
        if declared_module_name in name_to_module_info:
            continue
        missing_modules.setdefault(declared_module_name, mod_info)

    name_to_module_info.update(missing_modules)
