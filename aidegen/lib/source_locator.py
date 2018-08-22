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
"""Collect the source paths from dependency information."""


def locate_source(project):
    """Locate dependent source folder path and jar files paths.

    Try to reference source folder path as dependent module unless the
    dependent module should be referenced to a jar file, such as modules have
    jars and jarjar_rules parameter.
    For example:
        Module: asm-6.0
            java_import {
                name: "asm-6.0",
                host_supported: true,
                jars: ["asm-6.0.jar"],
            }
        Module: bouncycastle
            java_library {
                name: "bouncycastle",
                ...
                target: {
                    android: {
                        jarjar_rules: "jarjar-rules.txt",
                    },
                },
            }

    Args:
        project: ProjectInfo class.Information of a project such as project
                 relative path, project real path, project dependencies.
    """
    # TODO(b/112523194): Generate project.source_path for module
    # lib.project_file_gen to create IDE project files.
    project.source_path = {
        "source_folder_path": [],
        "jar_path": []
    }
