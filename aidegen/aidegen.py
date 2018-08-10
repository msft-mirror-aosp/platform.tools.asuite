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
"""AIDEgen

This CLI generates a configuration iml file for using in IntelliJ.

- Sample usage:
    - Generating a Settings.iml under packages/apps/Settings folder.
    $ aidegen packages/apps/Settings
"""

import argparse
import logging
import sys

logger = logging.getLogger(__name__)


def _ParseArgs(args):
    """Parse command line arguments.

    Args:
        args: A list of arguments.

    Returns:
        An argparse.Namespace class instance holding parsed args.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="aidegen {project_path}")
    parser.required = False
    parser.add_argument(
        "project_path",
        type=str,
        help="Android module path, e.g. packages/apps/Settings.")
    return parser.parse_args(args)


def main(argv):
    """Main entry.

    Args:
        argv: A list of system arguments.
    """
    args = _ParseArgs(argv)
    logger.info(args.project_path)


if __name__ == "__main__":
    main(sys.argv[1:])
