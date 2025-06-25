#!/usr/bin/env python3
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

"""Unittests for fetch_artifact."""

import subprocess
import unittest
from unittest import mock

from atest.test_finders.test_info import TestInfo
from atest.tools import fetch_artifact


class FetchArtifactUnittests(unittest.TestCase):

  @mock.patch('pathlib.Path', autospec=True)
  @mock.patch(
      'subprocess.run',
      return_value=subprocess.CompletedProcess(args=[], returncode=0),
  )
  @mock.patch('subprocess.Popen', autospec=True)
  def test_fetch_artifact_success(self, mock_popen, mock_run, mock_path):
    mock_path.return_value.rglob.side_effect = [
        iter(()),
        iter((mock.MagicMock(),)),
    ]
    proc = mock.MagicMock()
    mock_popen.return_value.__enter__.return_value = proc
    proc.stdout = [
        'other_file',
        'testcases/module/',
        'testcases/module/module.config',
        'testcases/module/module',
        'testcases/module/test.apk',
        'testcases/module/setup.sh',
    ]
    proc.wait.return_value = 0

    test_infos = [
        TestInfo(
            test_name='module',
            test_runner='',
            build_targets=set(),
            compatibility_suites=['cts'],
        )
    ]

    self.assertTrue(
        fetch_artifact.fetch_artifacts(
            test_infos=test_infos, build_target='target'
        )
    )
    mock_run.assert_has_calls(
        [
            mock.call(
                (fetch_artifact._FETCH_ARTIFACT_BIN, '--version'),
                check=True,
                text=True,
                capture_output=True,
            ),
            mock.call(
                [
                    fetch_artifact._FETCH_ARTIFACT_BIN,
                    '--target',
                    'target',
                    '--zip_entry',
                    'testcases/module/module.config',
                    '--zip_entry',
                    'testcases/module/module',
                    '--zip_entry',
                    'testcases/module/test.apk',
                    'android-cts.zip',
                    fetch_artifact._CACHE_DIR,
                ],
                check=True,
                text=True,
                stderr=subprocess.STDOUT,
                stdout=subprocess.PIPE,
            ),
            mock.call(
                [
                    fetch_artifact._FETCH_ARTIFACT_BIN,
                    '--target',
                    'target',
                    '--zip_entry',
                    'testcases/module/setup.sh',
                    'android-cts.zip',
                    fetch_artifact._CACHE_DIR,
                ],
                check=True,
                text=True,
                stderr=subprocess.STDOUT,
                stdout=subprocess.PIPE,
            ),
        ],
        any_order=True,
    )

  @mock.patch(
      'subprocess.run',
      side_effect=subprocess.CalledProcessError(returncode=1, cmd='cmd'),
  )
  def test_fetch_artifact_not_available(self, mock_run):
    self.assertFalse(
        fetch_artifact.fetch_artifacts(test_infos=[], build_target='')
    )
    mock_run.assert_called_once()

  @mock.patch(
      'subprocess.run',
      return_value=subprocess.CompletedProcess(args=[], returncode=0),
  )
  @mock.patch('subprocess.Popen')
  def test_fetch_artifact_suite_not_supported(self, mock_popen, mock_run):
    test_infos = [
        TestInfo(
            test_name='module',
            test_runner='',
            build_targets=set(),
            compatibility_suites=['gts'],
        )
    ]

    self.assertFalse(
        fetch_artifact.fetch_artifacts(test_infos=test_infos, build_target='')
    )
    mock_run.assert_called_once()
    mock_popen.assert_not_called()

  @mock.patch(
      'subprocess.run',
      return_value=subprocess.CompletedProcess(args=[], returncode=0),
  )
  @mock.patch(
      'subprocess.Popen',
      side_effect=subprocess.CalledProcessError(returncode=1, cmd='list'),
  )
  def test_fetch_artifact_list_artifact_error(self, mock_popen, mock_run):
    test_infos = [
        TestInfo(
            test_name='module',
            test_runner='',
            build_targets=set(),
            compatibility_suites=['cts'],
        )
    ]

    self.assertFalse(
        fetch_artifact.fetch_artifacts(test_infos=test_infos, build_target='')
    )
    mock_run.assert_called_once()
    mock_popen.assert_called_once()

  @mock.patch('pathlib.Path', autospec=True)
  @mock.patch(
      'subprocess.run',
      side_effect=[
          subprocess.CompletedProcess(args=[], returncode=0),
          subprocess.CalledProcessError(returncode=1, cmd='fetch'),
          subprocess.CompletedProcess(args=[], returncode=0),
          subprocess.CompletedProcess(args=[], returncode=0),
      ],
  )
  @mock.patch('subprocess.Popen', autospec=True)
  def test_fetch_artifact_retry_failed_files(
      self, mock_popen, mock_run, mock_path
  ):
    mock_path.return_value.rglob.side_effect = [
        iter(()),
        iter((mock.MagicMock(),)),
    ]
    proc = mock.MagicMock()
    mock_popen.return_value.__enter__.return_value = proc
    proc.stdout = [
        'other_file',
        'testcases/module/',
        'testcases/module/module.config',
        'testcases/module/module',
    ]
    proc.wait.return_value = 0

    test_infos = [
        TestInfo(
            test_name='module',
            test_runner='',
            build_targets=set(),
            compatibility_suites=['cts'],
        )
    ]

    self.assertTrue(
        fetch_artifact.fetch_artifacts(
            test_infos=test_infos, build_target='target'
        )
    )
    mock_run.assert_has_calls(
        [
            mock.call(
                [
                    fetch_artifact._FETCH_ARTIFACT_BIN,
                    '--target',
                    'target',
                    '--zip_entry',
                    'testcases/module/module.config',
                    '--zip_entry',
                    'testcases/module/module',
                    'android-cts.zip',
                    fetch_artifact._CACHE_DIR,
                ],
                check=True,
                text=True,
                stderr=subprocess.STDOUT,
                stdout=subprocess.PIPE,
            ),
            mock.call(
                [
                    fetch_artifact._FETCH_ARTIFACT_BIN,
                    '--target',
                    'target',
                    '--zip_entry',
                    'testcases/module/module.config',
                    'android-cts.zip',
                    fetch_artifact._CACHE_DIR,
                ],
                check=True,
                text=True,
                stderr=subprocess.STDOUT,
                stdout=subprocess.PIPE,
            ),
            mock.call(
                [
                    fetch_artifact._FETCH_ARTIFACT_BIN,
                    '--target',
                    'target',
                    '--zip_entry',
                    'testcases/module/module',
                    'android-cts.zip',
                    fetch_artifact._CACHE_DIR,
                ],
                check=True,
                text=True,
                stderr=subprocess.STDOUT,
                stdout=subprocess.PIPE,
            ),
        ],
        any_order=True,
    )

  @mock.patch('pathlib.Path', autospec=True)
  @mock.patch(
      'subprocess.run',
      return_value=subprocess.CompletedProcess(args=[], returncode=0),
  )
  @mock.patch('subprocess.Popen')
  def test_fetch_artifact_empty_list(self, mock_popen, _, mock_path):
    mock_path.return_value.rglob.return_value = iter(())
    mock_popen.return_value.__enter__.return_value.wait.return_value = 0
    test_infos = [
        TestInfo(
            test_name='module',
            test_runner='',
            build_targets=set(),
            compatibility_suites=['cts'],
        )
    ]

    self.assertFalse(
        fetch_artifact.fetch_artifacts(
            test_infos=test_infos, build_target='target'
        )
    )
