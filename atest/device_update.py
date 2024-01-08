# Copyright 2023, The Android Open Source Project
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

"""Device update methods used to prepare the device under test."""

from pathlib import Path
from  subprocess import CalledProcessError

from abc import ABC, abstractmethod
from typing import Set

from atest import atest_utils


class DeviceUpdateMethod(ABC):
    """A device update method used to update device."""

    @abstractmethod
    def update(self):
        """Updates the device.

        Raises:
            Error: If the device update fails.
        """

    @abstractmethod
    def dependencies(self) -> Set[str]:
        """Returns the dependencies required by this device update method."""


class NoopUpdateMethod(DeviceUpdateMethod):
    def update(self) -> None:
        pass

    def dependencies(self) -> Set[str]:
        return set()


class AdeviceUpdateMethod(DeviceUpdateMethod):
    _TOOL = 'adevice'

    def __init__(self, adevice_path: Path = _TOOL):
        self._adevice_path = adevice_path

    def update(self) -> None:
        try:
            print(atest_utils.mark_cyan("\nUpdating device..."))
            update_start = time.time()

            atest_utils.run_limited_output([self._adevice_path, 'update'])

            print(atest_utils.mark_cyan(
                '\nDevice update finished in '
                f'{str(round(time.time() - update_start, 2))}s.'))

        except CalledProcessError as e:
            raise Error(
                'Failed to update the device with adevice') from e

    def dependencies(self) -> Set[str]:
        return {self._TOOL, 'sync'}


class Error(Exception):
    pass
