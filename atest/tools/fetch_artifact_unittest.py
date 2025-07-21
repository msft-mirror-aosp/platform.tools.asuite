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

import os
import pathlib
import subprocess
import unittest
from unittest import mock

from atest import constants
from atest.test_finders.test_info import TestInfo
from atest.tools import fetch_artifact
from pyfakefs import fake_filesystem_unittest


class ArtifactContextManagerUnittests(fake_filesystem_unittest.TestCase):

  def setUp(self):
    super(ArtifactContextManagerUnittests, self).setUp()
    self.setUpPyfakefs()
    self.fs.create_dir(os.getenv('ANDROID_TARGET_OUT_TESTCASES'))
    self.fs.create_dir(os.getenv('ANDROID_HOST_OUT_TESTCASES'))
    self._cache_path = pathlib.Path(fetch_artifact._CACHE_DIR, '123', 'target')
    self._target_tcases = pathlib.Path(
        os.getenv('ANDROID_TARGET_OUT_TESTCASES')
    )
    self._target_out = pathlib.Path(os.getenv('ANDROID_PRODUCT_OUT'))
    self._host_out = pathlib.Path(os.getenv('ANDROID_HOST_OUT'))
    self._host_tcases = pathlib.Path(os.getenv('ANDROID_HOST_OUT_TESTCASES'))

  def test_symlink_artifacts_swap(self):
    # Downloaded artifacts
    module_cache = self._cache_path / 'android-cts/testcases/module'
    self.fs.create_dir(module_cache)
    self.fs.create_file(module_cache / 'module.config', contents='module cache')
    # Existing testcases directory
    target_dir = self._target_tcases / 'module'
    module_config = target_dir / 'module.config'
    self.fs.create_dir(target_dir)
    self.fs.create_file(module_config, contents='module config')

    test_infos = [
        TestInfo(
            test_name='module',
            test_runner='',
            build_targets=set(),
            install_locations={constants.DEVICE_TEST},
        ),
    ]
    mod_info = mock.MagicMock()
    mod_info.get_installed_paths.return_value = []

    self.assertFalse(target_dir.is_symlink())
    self.assertEqual(module_config.read_text(), 'module config')
    with fetch_artifact.ArtifactContextManager(
        test_infos=test_infos, mod_info=mod_info, build_target='target'
    ):
      self.assertTrue(target_dir.is_symlink())
      self.assertEqual(target_dir.resolve(), module_cache)
      self.assertEqual(module_config.read_text(), 'module cache')
    self.assertFalse(target_dir.is_symlink())
    self.assertEqual(module_config.read_text(), 'module config')

  def test_symlink_artifacts_installed_files(self):
    # Downloaded artifacts
    module_cache = self._cache_path / 'android-cts/testcases/module'
    self.fs.create_dir(module_cache)
    self.fs.create_file(module_cache / 'module.config')
    self.fs.create_dir(module_cache / 'arm')
    self.fs.create_file(module_cache / 'arm/test.apk')
    self.fs.create_file(module_cache / 'arm/testdata/test.apk')
    self.fs.create_dir(module_cache / 'arm64')
    self.fs.create_file(module_cache / 'arm64/test.apk')
    self.fs.create_file(module_cache / 'arm64/testdata/test.apk')

    test_infos = [
        TestInfo(
            test_name='module',
            test_runner='',
            build_targets=set(),
            install_locations={constants.DEVICE_TEST, constants.HOST},
        ),
    ]
    mod_info = mock.MagicMock()
    mod_info.get_installed_paths.return_value = [
        self._host_out / 'nativetest64/module/test.apk',
        self._target_tcases / 'module/arm/test.apk',
        self._target_tcases / 'module/arm64/test.apk',
        self._target_out / 'nativetest64/module/test.apk',
        self._target_out / 'nativetest64/module/testdata/test.apk',
        self._target_out / 'nativetest/module/test.apk',
        self._target_out / 'nativetest/module/testdata/test.apk',
        self._target_out / 'unknown',
    ]
    self.fs.create_file(self._target_out / 'unknown')

    host_dir = self._host_tcases / 'module'
    target_dir = self._target_tcases / 'module'
    test_apk64 = self._target_out / 'nativetest64/module/test.apk'
    testdata_apk64 = self._target_out / 'nativetest64/module/testdata/test.apk'
    test_apk = self._target_out / 'nativetest/module/test.apk'
    testdata_apk = self._target_out / 'nativetest/module/testdata/test.apk'
    self.assertFalse(host_dir.exists())
    self.assertFalse(target_dir.exists())
    with fetch_artifact.ArtifactContextManager(
        test_infos=test_infos, mod_info=mod_info, build_target='target'
    ):
      # Ignore installed files for host
      self.assertFalse(host_dir.exists())
      self.assertFalse(
          (self._host_out / 'nativetest64/module/test.apk').exists()
      )

      # Symlink testcases directory
      self.assertTrue(target_dir.is_symlink())
      self.assertEqual(target_dir.resolve(), module_cache)

      # Ignore installed files in testcases directory
      self.assertTrue((self._target_tcases / 'module/arm/test.apk').exists())
      self.assertFalse(
          (self._target_tcases / 'module/arm/test.apk').is_symlink()
      )
      self.assertTrue((self._target_tcases / 'module/arm64/test.apk').exists())
      self.assertFalse(
          (self._target_tcases / 'module/arm64/test.apk').is_symlink()
      )

      # Symlink other installed files
      self.assertTrue(test_apk64.is_symlink())
      self.assertEqual(test_apk64.resolve(), module_cache / 'arm64/test.apk')
      self.assertTrue(testdata_apk64.is_symlink())
      self.assertEqual(
          testdata_apk64.resolve(), module_cache / 'arm64/testdata/test.apk'
      )
      self.assertTrue(test_apk.is_symlink())
      self.assertEqual(test_apk.resolve(), module_cache / 'arm/test.apk')
      self.assertTrue(testdata_apk.is_symlink())
      self.assertEqual(
          testdata_apk.resolve(), module_cache / 'arm/testdata/test.apk'
      )

      # Remove unknown file
      self.assertFalse((self._target_out / 'unknown').exists())
    self.assertFalse(host_dir.exists())
    self.assertFalse(target_dir.exists())
    self.assertFalse(test_apk64.exists())
    self.assertFalse(testdata_apk64.exists())
    self.assertFalse(test_apk.exists())
    self.assertFalse(testdata_apk.exists())
    self.assertTrue((self._target_out / 'unknown').exists())

  def test_symlink_artifacts_cleanup_on_error(self):
    self.fs.create_dir(self._cache_path / 'android-cts/testcases/module1')
    # Existing testcases directory
    module1_dir = self._host_tcases / 'module1'
    module2_dir = self._host_tcases / 'module2'
    self.fs.create_dir(module1_dir)
    self.fs.create_dir(module2_dir)

    test_infos = [
        TestInfo(
            test_name='module1',
            test_runner='',
            build_targets=set(),
            install_locations={constants.HOST},
        ),
        TestInfo(
            test_name='module2',
            test_runner='',
            build_targets=set(),
            install_locations={constants.HOST},
        ),
    ]
    mod_info = mock.MagicMock()
    mod_info.get_installed_paths.return_value = []

    try:
      with fetch_artifact.ArtifactContextManager(
          test_infos=test_infos, mod_info=mod_info, build_target='target'
      ):
        # symlink module1
        # error for module2
        pass
    except fetch_artifact.CrossBranchArtifactError:
      pass
    self.assertTrue(module1_dir.exists())
    self.assertFalse(module1_dir.is_symlink())
    self.assertTrue(module2_dir.exists())
    self.assertFalse(module2_dir.is_symlink())


class FetchArtifactUnittests(unittest.TestCase):

  @mock.patch.object(fetch_artifact, '_prepare_cache_dir', autospec=True)
  @mock.patch(
      'subprocess.run',
      return_value=subprocess.CompletedProcess(args=[], returncode=0),
  )
  @mock.patch('subprocess.Popen', autospec=True)
  def test_fetch_artifact_success(self, mock_popen, mock_run, mock_cache_dir):
    root_dir = mock.MagicMock()
    root_dir.rglob.side_effect = [iter(()), iter((mock.MagicMock(),))]
    root_dir.__str__.return_value = 'cache/123/target'
    mock_cache_dir.return_value = root_dir
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
            test_infos=test_infos, build_target='target', build_id='123'
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
                    '--bid',
                    '123',
                    '--zip_entry',
                    'testcases/module/module.config',
                    '--zip_entry',
                    'testcases/module/module',
                    '--zip_entry',
                    'testcases/module/test.apk',
                    'android-cts.zip',
                    'cache/123/target',
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
                    '--bid',
                    '123',
                    '--zip_entry',
                    'testcases/module/setup.sh',
                    'android-cts.zip',
                    'cache/123/target',
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

  @mock.patch.object(fetch_artifact, '_prepare_cache_dir', autospec=True)
  @mock.patch(
      'subprocess.run',
      return_value=subprocess.CompletedProcess(args=[], returncode=0),
  )
  @mock.patch('subprocess.Popen')
  def test_fetch_artifact_skip_downloading_with_cache(
      self, mock_popen, mock_run, mock_cache_dir
  ):
    mock_cache_dir.return_value.rglob.return_value = iter((mock.MagicMock(),))
    test_infos = [
        TestInfo(
            test_name='module',
            test_runner='',
            build_targets=set(),
            compatibility_suites=['cts'],
        )
    ]

    self.assertTrue(
        fetch_artifact.fetch_artifacts(test_infos=test_infos, build_target='')
    )
    mock_run.assert_called_once()
    mock_popen.assert_not_called()

  @mock.patch.object(fetch_artifact, '_prepare_cache_dir', autospec=True)
  @mock.patch(
      'subprocess.run',
      return_value=subprocess.CompletedProcess(args=[], returncode=0),
  )
  @mock.patch('subprocess.Popen', autospec=True)
  def test_fetch_artifact_suite_not_supported(
      self, mock_popen, mock_run, mock_cache_dir
  ):
    mock_cache_dir.return_value.rglob.return_value = iter(())
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

  @mock.patch.object(fetch_artifact, '_prepare_cache_dir', autospec=True)
  @mock.patch(
      'subprocess.run',
      return_value=subprocess.CompletedProcess(args=[], returncode=0),
  )
  @mock.patch(
      'subprocess.Popen',
      side_effect=subprocess.CalledProcessError(returncode=1, cmd='list'),
  )
  def test_fetch_artifact_list_artifact_error(
      self, mock_popen, mock_run, mock_cache_dir
  ):
    mock_cache_dir.return_value.rglob.return_value = iter(())
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

  @mock.patch.object(fetch_artifact, '_prepare_cache_dir', autospec=True)
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
      self, mock_popen, mock_run, mock_cache_dir
  ):
    root_dir = mock.MagicMock()
    root_dir.rglob.side_effect = [iter(()), iter((mock.MagicMock(),))]
    root_dir.__str__.return_value = 'cache/123/target'
    mock_cache_dir.return_value = root_dir
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
            test_infos=test_infos, build_target='target', branch='branch'
        )
    )
    mock_run.assert_has_calls(
        [
            mock.call(
                [
                    fetch_artifact._FETCH_ARTIFACT_BIN,
                    '--target',
                    'target',
                    '--branch',
                    'branch',
                    '--latest',
                    '--zip_entry',
                    'testcases/module/module.config',
                    '--zip_entry',
                    'testcases/module/module',
                    'android-cts.zip',
                    'cache/123/target',
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
                    '--branch',
                    'branch',
                    '--latest',
                    '--zip_entry',
                    'testcases/module/module.config',
                    'android-cts.zip',
                    'cache/123/target',
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
                    '--branch',
                    'branch',
                    '--latest',
                    '--zip_entry',
                    'testcases/module/module',
                    'android-cts.zip',
                    'cache/123/target',
                ],
                check=True,
                text=True,
                stderr=subprocess.STDOUT,
                stdout=subprocess.PIPE,
            ),
        ],
        any_order=True,
    )

  @mock.patch.object(fetch_artifact, '_prepare_cache_dir', autospec=True)
  @mock.patch(
      'subprocess.run',
      return_value=subprocess.CompletedProcess(args=[], returncode=0),
  )
  @mock.patch('subprocess.Popen')
  def test_fetch_artifact_empty_list(self, mock_popen, _, mock_cache_dir):
    mock_cache_dir.return_value.rglob.return_value = iter(())
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

  @mock.patch.object(pathlib.Path, 'mkdir')
  @mock.patch.object(pathlib.Path, 'exists', return_value=True)
  def test_prepare_cache_dir_success_with_digit_build_id(self, *_):
    self.assertEqual(
        fetch_artifact._prepare_cache_dir(
            build_target='target', build_id='123'
        ),
        pathlib.Path(fetch_artifact._CACHE_DIR, '123', 'target'),
    )

  @mock.patch.object(pathlib.Path, 'mkdir')
  @mock.patch.object(pathlib.Path, 'exists', return_value=True)
  @mock.patch.object(pathlib.Path, 'unlink')
  @mock.patch('builtins.open')
  @mock.patch('json.load', return_value={'bid': '123'})
  @mock.patch(
      'subprocess.run',
      return_value=subprocess.CompletedProcess(args=[], returncode=0),
  )
  def test_prepare_cache_dir_success_without_build_id(self, mock_run, *_):
    self.assertEqual(
        fetch_artifact._prepare_cache_dir(
            build_target='target', branch='branch'
        ),
        pathlib.Path(fetch_artifact._CACHE_DIR, '123', 'target'),
    )

    mock_run.assert_called_once_with(
        [
            fetch_artifact._FETCH_ARTIFACT_BIN,
            '--target',
            'target',
            '--branch',
            'branch',
            '--latest',
            'BUILD_INFO',
            fetch_artifact._CACHE_DIR,
        ],
        text=True,
        check=False,
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
    )

  @mock.patch.object(pathlib.Path, 'mkdir')
  @mock.patch.object(pathlib.Path, 'exists', return_value=False)
  @mock.patch(
      'subprocess.run',
      return_value=subprocess.CompletedProcess(
          args=[], returncode=0, stdout='err'
      ),
  )
  def test_prepare_cache_dir_fail_no_build_info(self, *_):
    with self.assertRaisesRegex(
        fetch_artifact.CrossBranchArtifactError, 'Failed to get build info'
    ):
      fetch_artifact._prepare_cache_dir(build_target='target', branch='branch')

  @mock.patch.object(pathlib.Path, 'mkdir')
  @mock.patch.object(pathlib.Path, 'exists', return_value=True)
  @mock.patch.object(pathlib.Path, 'unlink')
  @mock.patch('builtins.open')
  @mock.patch('json.load', return_value={'a': '123'})
  @mock.patch(
      'subprocess.run',
      return_value=subprocess.CompletedProcess(args=[], returncode=0),
  )
  def test_prepare_cache_dir_fail_invalid_build_info(self, *_):
    with self.assertRaisesRegex(
        fetch_artifact.CrossBranchArtifactError, 'Invalid build info'
    ):
      fetch_artifact._prepare_cache_dir(build_target='target', branch='branch')
