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
"""It is an AIDEGen sub task : launch IDE task!

Takes a project file path as input, after passing the needed check(file
existence, IDE type, IDE existence, etc.), try to launch the related IDE.

    Typical usage example:

    launch_ide(file_path)
    launch_intellij(file_path)
"""

import logging


def launch_ide(file_path):
    """Launches the relative IDE to open the passed project file.

    Args:
        file_path: The target to open IDE project file.
    """
    logging.info("Project file name:%s", file_path)
    # TODO(albaltai@): Do checking job and find related IDE to launch.


def launch_intellij(file_path):
    """Launches IntelliJ IDE to open the validated project file.

    Args:
        file_path: The target to open IDE project file.
    """
    logging.info("Project file name:%s", file_path)
    # TODO(albaltai@): Do IntelliJ specific checking, normal checking job,
    #                  and then launch IntelliJ.
