# Copyright 2017, The Android Open Source Project
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

"""Imports the various constant files that are available (default, google, etc)."""
# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import

import json
import os
import sys
from atest.constants_default import *


def _load_asuite_python_paths():
  """Load additional python paths to module find path.

  When atest is built with embedded mode, the PYTHONPATH is ignored. We use
  this function to add the paths to the module search paths. Specifically, we
  only need to add the asuite python paths so that we can load the
  `constants_google` module.
  """
  python_paths = os.environ.get('PYTHONPATH', '').split(':')
  for python_path in python_paths:
    if 'asuite' in python_path and python_path not in sys.path:
      sys.path.append(python_path)


_load_asuite_python_paths()

# Now try to import the various constant files outside this repo to overwrite
# the globals as desired.
# pylint: disable=g-import-not-at-top
try:
  from constants_google import *
except ImportError:
  pass

# Note: This is part of the work to eventually replace the dangling import of
# constants_google entirely. We will start with migrating the constants to json
# and source code. In the future, we will migrate to use a config object instead
# of relying on composing the constants module.
def _load_vendor_config():
  """Load the atest vendor configs from json path if available."""

  config_path = os.environ.get('ATEST_VENDOR_CONFIG_PATH', None)
  if not config_path:
    return
  with open(config_path, 'r') as config_file:
    globals().update(json.load(config_file))


_load_vendor_config()
