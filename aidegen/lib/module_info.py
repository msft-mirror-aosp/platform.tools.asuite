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

"""Module Info class used to hold cached merged_module_info.json.json."""

import json
import logging
import os

from aidegen import constant
from aidegen.lib import common_util
from aidegen.lib import module_info_util
from atest import module_info


class AidegenModuleInfo(module_info.ModuleInfo):
    """Class that offers fast/easy lookup for Module related details.

    Class attributes:
        mod_info: A ModuleInfo instance contains data of the merged json file
                  after initialization.
        projects: A list of project names.
        verbose: A boolean, if true displays full build output.
        skip_build: A boolean, if true skip building
                    constant.BLUEPRINT_JSONFILE_NAME if it exists, otherwise
                    build it.
    """
    mod_info = None
    projects = []
    verbose = False
    skip_build = False

    # pylint: disable=too-many-arguments
    def __init__(self,
                 force_build=False,
                 module_file=None,
                 atest_module_info=None,
                 projects=None,
                 verbose=False,
                 skip_build=False):
        """Initialize the AidegenModuleInfo object.

        Load up the module-info.json file and initialize the helper vars.

        Args:
            force_build: Boolean to indicate if we should rebuild the
                         module_info file regardless if it's created or not.
                         The default value is False: don't force build.
            module_file: String of path to file to load up. Used for testing.
                         The default value is None: don't specify the path.
            atest_module_info: A ModuleInfo instance contains data of
                               module-info.json. The default value is None,
                               module_info_util can get it from
                               common_util.get_atest_module_info function.
            projects: A list of project names. The default value is None,
                      module_info_util won't show reuse iml project file
                      message.
            verbose: A boolean, if true displays full build output. The default
                     value is False.
            skip_build: A boolean, if true skip building
                        constant.BLUEPRINT_JSONFILE_NAME if it exists, otherwise
                        build it. The default value is False.
        """
        AidegenModuleInfo.mod_info = atest_module_info
        AidegenModuleInfo.projects = projects
        AidegenModuleInfo.verbose = verbose
        AidegenModuleInfo.skip_build = skip_build
        super().__init__(force_build, module_file)

    @staticmethod
    def _discover_mod_file_and_target(force_build):
        """Find the module file.

        If force_build is True, we'll remove module_bp_java_deps.json first and
        let module_info_util.generate_merged_module_info regenerate it again.

        Args:
            force_build: Boolean to indicate if we should rebuild the
                         module_info file regardless if it's created or not.

        Returns:
            Tuple of the relative and absolute paths of the merged module info
            file.
        """
        module_file_path = common_util.get_blueprint_json_path()
        if force_build and os.path.isfile(module_file_path):
            os.remove(module_file_path)
        merged_file_path = os.path.join(common_util.get_soong_out_path(),
                                        constant.MERGED_MODULE_INFO)
        if not os.path.isfile(module_file_path):
            logging.debug(
                'Generating %s - this is required for the initial runs.',
                merged_file_path)
        if not AidegenModuleInfo.mod_info:
            AidegenModuleInfo.mod_info = common_util.get_atest_module_info()
        data = module_info_util.generate_merged_module_info(
            AidegenModuleInfo.mod_info, AidegenModuleInfo.projects,
            AidegenModuleInfo.verbose, AidegenModuleInfo.skip_build)
        with open(merged_file_path, 'w') as json_file:
            json.dump(data, json_file, indent=4)
        module_file_rel_path = os.path.relpath(
            merged_file_path, common_util.get_android_root_dir())
        return module_file_rel_path, merged_file_path
