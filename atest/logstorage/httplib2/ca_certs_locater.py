# Copyright (C) 2024 The Android Open Source Project
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

"""Custom locater for CA_CERTS files."""

import atexit
import importlib.resources
import os
import pathlib
import shutil
import tempfile

try:
  from httplib2 import certs
except ModuleNotFoundError as e:
  logging.debug('httplib2 is not available: %s', e)


def get() -> str:
  """Locate the ca_certs.txt file.

  The httplib2 library will look for local ca_certs_locater module to override
  the default location for the ca_certs.txt file. We override it here to load
  via resources for python binary built with embedded launcher.

  Returns:
    The file location returned as a string.
  """
  try:
    with importlib.resources.as_file(
        importlib.resources.files('httplib2').joinpath('cacerts.txt')
    ) as cacerts:
      _, tmp_file = tempfile.mkstemp(suffix='cacerts.txt')
      tmp_cacerts_path = pathlib.Path(tmp_file)
      atexit.register(lambda: tmp_cacerts_path.unlink())
      shutil.copyfile(cacerts, tmp_cacerts_path)
      return tmp_cacerts_path.as_posix()
  except (ModuleNotFoundError, FileNotFoundError):
    # Not running with embedded launcher
    return certs.BUILTIN_CA_CERTS
