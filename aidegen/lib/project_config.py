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

"""Project config class."""

from aidegen import constant
from aidegen.lib import common_util

SKIP_BUILD_INFO = ('If you are sure the related modules and dependencies have '
                   'been already built, please try to use command {} to skip '
                   'the building process.')
_SKIP_BUILD_CMD = 'aidegen {} -s'
_SKIP_BUILD_WARN = (
    'You choose "--skip-build". Skip building jar and module might increase '
    'the risk of the absence of some jar or R/AIDL/logtags java files and '
    'cause the red lines to appear in IDE tool.')


class ProjectConfig:
    """Class manages AIDEGen's configurations.

    Attributes:
        ide_name: The IDE name which user prefer to launch.
        is_launch_ide: A boolean for launching IDE in the end of AIDEGen.
        depth: The depth of module referenced by source.
        full_repo: A boolean decides import whole Android source repo.
        is_skip_build: A boolean decides skipping building jars or modules.
        targets: A string list with Android module names or paths.
    """

    def __init__(self, args):
        self.ide_name = constant.IDE_NAME_DICT[args.ide[0]]
        self.is_launch_ide = not args.no_launch
        self.depth = args.depth
        self.full_repo = args.android_tree
        self.is_skip_build = args.skip_build
        self.targets = args.targets
        self._show_skip_build_msg()

    def _show_skip_build_msg(self):
        """Display different messages if users skip building targets or not."""
        if self.is_skip_build:
            print('\n{} {}\n'.format(
                common_util.COLORED_INFO('Warning:'), _SKIP_BUILD_WARN))
        else:
            msg = SKIP_BUILD_INFO.format(
                common_util.COLORED_INFO(
                    _SKIP_BUILD_CMD.format(' '.join(self.targets))))
            print('\n{} {}\n'.format(common_util.COLORED_INFO('INFO:'), msg))
