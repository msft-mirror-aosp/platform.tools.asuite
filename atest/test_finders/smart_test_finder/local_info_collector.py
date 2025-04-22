#!/usr/bin/env python3
#
# Copyright 2025, The Android Open Source Project
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

"""Provides utils to obtain local change infos (project, branch, changed files, etc.)"""

import dataclasses
import getpass
import logging
import re
import subprocess
from xml.etree import ElementTree
from atest import atest_utils


_PROJECT_KEY = 'project'
_BRANCH_KEY = 'branch'
_REMOTE_HOSTNAME_KEY = 'remote_hostname'
_MATCH_PROJECT_REGEX = re.compile(rf'^Project: (?P<{_PROJECT_KEY}>[^\s]+)')
_MATCH_BRANCH_REGEX = re.compile(
    rf'^Manifest branch: (?P<{_BRANCH_KEY}>[^\s]+)'
)
_ANDROID_BUILD_TOP_KEY = 'ANDROID_BUILD_TOP'
_MATCH_REMOTE_HOSTNAME_REGEX = re.compile(
    rf'sso://(?P<{_REMOTE_HOSTNAME_KEY}>[^/]+)/'
)


@dataclasses.dataclass(frozen=True)
class ChangeInfo:
  """Information of local changes against the remote HEAD.

  The info includes the current project, branch, remote hostname, username, set
  of changed files.
  """

  project: str
  branch: str
  remote_hostname: str
  user_key: str
  changed_files: set[atest_utils.ChangedFileDetails]


def get_local_change_info() -> ChangeInfo:
  """Get the local change info under the current project."""
  project, branch = _get_project_and_branch()
  change_info = ChangeInfo(
      project=project,
      branch=branch,
      remote_hostname=_get_remote_hostname(),
      user_key=getpass.getuser(),
      changed_files=atest_utils.get_modified_files_with_details(),
  )
  return change_info


def _get_remote_hostname() -> str:
  """Get remote hostname.

  Returns:
      Remote hostnames extracted from the domain name
      'sso://{remote-hostname}/'.
  """
  manifest_default_path = ''
  try:
    manifest_default_path = atest_utils.get_build_top(
        '.repo/manifests/default.xml'
    )
    manifest = ElementTree.parse(str(manifest_default_path))
    root = manifest.getroot()
    default = root.find('default')
    if default is not None:
      for element in root.findall('remote'):
        if element.attrib['name'] == default.attrib['remote']:
          match_remote_hostname = _MATCH_REMOTE_HOSTNAME_REGEX.match(
              element.attrib['review']
          )
          if match_remote_hostname:
            return match_remote_hostname.group(_REMOTE_HOSTNAME_KEY)
  except (OSError, ElementTree.ParseError):
    if manifest_default_path:
      logging.debug(
          'Failed to parse the XML file for remote hostname: %s',
          manifest_default_path,
      )
    else:
      logging.debug('Failed to get the build top for remote hostname.')
  return ''


def _get_project_and_branch() -> tuple[str, str]:
  """Get the project and branch name in the current working directory."""
  branch = ''
  project = ''
  try:
    repo_output = (
        subprocess.check_output('repo info .', shell=True).decode().splitlines()
    )
    for line in repo_output:
      match_project = _MATCH_PROJECT_REGEX.match(line)
      if match_project:
        project = match_project.group(_PROJECT_KEY)
        continue
      match_branch = _MATCH_BRANCH_REGEX.match(line)
      if match_branch:
        branch = match_branch.group(_BRANCH_KEY)
  except subprocess.CalledProcessError as err:
    logging.debug('Failed to get the repo or the branch: %s', err)

  return (project, branch)
