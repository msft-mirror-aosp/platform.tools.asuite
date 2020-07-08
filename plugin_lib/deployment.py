#!/usr/bin/env python3
#
# Copyright 2020 - The Android Open Source Project
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

"""Asuite plugin deployment."""


class PluginDeployment:
    """The util class of Asuite plugin deployment.

    Usage:
        PluginDeployment.install_asuite_plugin()
        It will start installation process.

    Attributes:
        is_internal: True if the user is a internal user.
    """

    def __init__(self):
        """PluginDeployment initialize."""
        self.is_internal = self._is_internal_user()

    def install_asuite_plugin(self):
        """It is the main entry function for installing Asuite plugin."""

    def _ask_for_install(self):
        """Asks the user to install the Asuite plugin."""

    def _ask_for_upgrade(self):
        """Asks the user to upgrade the Asuite plugin."""

    def _copy_jars(self):
        """Copies jars to IntelliJ plugin folders."""

    def _is_plugin_installed(self):
        """Checks if the user has installed Asuite plugin before.

        Return:
            True if the user has installed Asuite plugin.
        """

    def _is_version_up_to_date(self):
        """Checks if all plugins' versions are up to date or not.

        Return:
            True if all plugins' versions are up to date.
        """

    def _write_selection(self):
        """Writes the user's selection to config file."""

    def _read_selection(self):
        """Reads the user's selection from config file.

        Return:
            A string of the user's selection: yes/no/auto
        """

    @staticmethod
    def _is_internal_user():
        """Checks if the user is internal user or external user.

        Return:
            True if the user is a internal user.
        """
        return True
