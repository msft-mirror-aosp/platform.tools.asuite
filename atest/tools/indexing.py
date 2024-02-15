#!/usr/bin/env python3
# Copyright 2019, The Android Open Source Project
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

"""Atest indexing module."""

from __future__ import annotations
from __future__ import print_function

from dataclasses import dataclass
import functools
import logging
import os
from pathlib import Path
import pickle
import shutil
import subprocess
import sys
import tempfile
import time
from typing import List

from atest import atest_utils as au
from atest import constants
from atest.atest_enum import DetectType
from atest.metrics import metrics, metrics_utils

UPDATEDB = 'updatedb'
LOCATE = 'locate'
# The list was generated by command:
# find `gettop` -type d -wholename `gettop`/out -prune  -o -type d -name '.*'
# -print | awk -F/ '{{print $NF}}'| sort -u
PRUNENAMES = [
    '.abc',
    '.appveyor',
    '.azure-pipelines',
    '.bazelci',
    '.build-id',
    '.buildkite',
    '.buildscript',
    '.cargo',
    '.ci',
    '.circleci',
    '.clusterfuzzlite',
    '.conan',
    '.devcontainer',
    '.dwz',
    '.externalToolBuilders',
    '.git',
    '.githooks',
    '.github',
    '.gitlab',
    '.gitlab-ci',
    '.google',
    '.hidden',
    '.idea',
    '.intermediates',
    '.jenkins',
    '.kokoro',
    '.libs_cffi_backend',
    '.more',
    '.mvn',
    '.prebuilt_info',
    '.private',
    '__pycache__',
    '.repo',
    '.settings',
    '.static',
    '.svn',
    '.test',
    '.travis',
    '.travis_scripts',
    '.tx',
    '.vscode',
]
PRUNEPATHS = ['prebuilts']


def debug_log(func):
  """Decorator for logging with debug mode."""

  @functools.wraps(func)
  def wrapper(*args, **kwargs):
    logging.debug('Running %s...', {func.__name__})
    func(*args, **kwargs)
    logging.debug('%s done.', {func.__name__})

  return wrapper


def run_updatedb(output_cache: Path, prunepaths: List[str] = None):
  """Run updatedb and generate cache in $ANDROID_HOST_OUT/indices/plocate.db

  Args:
      output_cache: The file path of the updatedb cache.
      prunepaths: a list of paths that are relative to the build top.
  """
  search_root = str(au.get_build_top())
  prunepaths = prunepaths if prunepaths else PRUNEPATHS
  prunepaths = [os.path.join(search_root, p) for p in prunepaths]
  prunepaths.append(str(au.get_build_out_dir()))
  updatedb_cmd = [UPDATEDB, '-l0']
  updatedb_cmd.append('-U%s' % search_root)
  updatedb_cmd.append('-n%s' % ' '.join(PRUNENAMES))
  updatedb_cmd.append('-o%s' % output_cache)
  # (b/206866627) /etc/updatedb.conf excludes /mnt from scanning on Linux.
  # Use --prunepaths to override the default configuration.
  updatedb_cmd.append('--prunepaths')
  updatedb_cmd.append(' '.join(prunepaths))
  # Support scanning bind mounts as well.
  updatedb_cmd.extend(['--prune-bind-mounts', 'no'])

  logging.debug('Running updatedb... ')
  try:
    full_env_vars = os.environ.copy()
    logging.debug('Executing: %s', updatedb_cmd)
    result = subprocess.run(updatedb_cmd, env=full_env_vars, check=True)
  except (KeyboardInterrupt, SystemExit):
    logging.error('Process interrupted or failure.')
  # Delete indices when plocate.db is locked() or other CalledProcessError.
  # (b/141588997)
  except subprocess.CalledProcessError as err:
    logging.error('Executing %s error.', ' '.join(updatedb_cmd))
    metrics_utils.handle_exc_and_send_exit_event(constants.PLOCATEDB_LOCKED)
    if err.output:
      logging.error(err.output)
    output_cache.unlink()

  return result.returncode == 0


def _dump_index(dump_file, output, output_re, key, value):
  """Dump indexed data with pickle.

  Args:
      dump_file: A string of absolute path of the index file.
      output: A string generated by locate and grep.
      output_re: An regex which is used for grouping patterns.
      key: A string for dictionary key, e.g. classname, package, cc_class, etc.
      value: A set of path.

  The data structure will be like:
  {
    'Foo': {'/path/to/Foo.java', '/path2/to/Foo.kt'},
    'Boo': {'/path3/to/Boo.java'}
  }
  """
  _dict = {}
  with tempfile.NamedTemporaryFile() as temp_file:
    with open(temp_file.name, 'wb') as cache_file:
      if isinstance(output, bytes):
        output = output.decode()
      for entry in output.splitlines():
        match = output_re.match(entry)
        if match:
          _dict.setdefault(match.group(key), set()).add(match.group(value))
      try:
        pickle.dump(_dict, cache_file, protocol=2)
      except IOError:
        logging.error('Failed in dumping %s', dump_file)
    shutil.copy(temp_file.name, dump_file)


# pylint: disable=anomalous-backslash-in-string
def get_cc_result(indices: Indices):
  """Search all testable cc/cpp and grep TEST(), TEST_F() or TEST_P().

  After searching cc/cpp files, index corresponding data types in parallel.

  Args:
      indices: an Indices object.
  """
  find_cc_cmd = (
      f"{LOCATE} -id{indices.locate_db} --regex '/*.test.*\.(cc|cpp)$'"
      f"| xargs egrep -sH '{constants.CC_GREP_RE}' 2>/dev/null || true"
  )
  logging.debug('Probing CC classes:\n %s', find_cc_cmd)
  result = subprocess.getoutput(find_cc_cmd)

  au.start_threading(
      target=_index_cc_classes, args=[result, indices.cc_classes_idx]
  )


# pylint: disable=anomalous-backslash-in-string
def get_java_result(indices: Indices):
  """Search all testable java/kt and grep package.

  After searching java/kt files, index corresponding data types in parallel.

  Args:
      indices: an Indices object.
  """
  package_grep_re = r'^\s*package\s+[a-z][[:alnum:]]+[^{]'
  find_java_cmd = (
      f"{LOCATE} -id{indices.locate_db} --regex '/*.test.*\.(java|kt)$' "
      # (b/204398677) suppress stderr when indexing target terminated.
      f"| xargs egrep -sH '{package_grep_re}' 2>/dev/null|| true"
  )
  logging.debug('Probing Java classes:\n %s', find_java_cmd)
  result = subprocess.getoutput(find_java_cmd)

  au.start_threading(
      target=_index_java_classes, args=[result, indices.classes_idx]
  )
  au.start_threading(
      target=_index_qualified_classes, args=[result, indices.fqcn_idx]
  )
  au.start_threading(
      target=_index_packages, args=[result, indices.packages_idx]
  )


@debug_log
def _index_cc_classes(output, index):
  """Index CC classes.

  The data structure is like:
  {
    'FooTestCase': {'/path1/to/the/FooTestCase.cpp',
                    '/path2/to/the/FooTestCase.cc'}
  }

  Args:
      output: A string object generated by get_cc_result().
      index: A string path of the index file.
  """
  _dump_index(
      dump_file=index,
      output=output,
      output_re=constants.CC_OUTPUT_RE,
      key='test_name',
      value='file_path',
  )


@debug_log
def _index_java_classes(output, index):
  """Index Java classes.

  The data structure is like: {

      'FooTestCase': {'/path1/to/the/FooTestCase.java',
                      '/path2/to/the/FooTestCase.kt'}
  }

  Args:
      output: A string object generated by get_java_result().
      index: A string path of the index file.
  """
  _dump_index(
      dump_file=index,
      output=output,
      output_re=constants.CLASS_OUTPUT_RE,
      key='class',
      value='java_path',
  )


@debug_log
def _index_packages(output, index):
  """Index Java packages.

  The data structure is like: {

      'a.b.c.d': {'/path1/to/a/b/c/d/',
                  '/path2/to/a/b/c/d/'
  }

  Args:
      output: A string object generated by get_java_result().
      index: A string path of the index file.
  """
  _dump_index(
      dump_file=index,
      output=output,
      output_re=constants.PACKAGE_OUTPUT_RE,
      key='package',
      value='java_dir',
  )


@debug_log
def _index_qualified_classes(output, index):
  """Index Fully Qualified Java Classes(FQCN).

  The data structure is like: {

      'a.b.c.d.FooTestCase': {'/path1/to/a/b/c/d/FooTestCase.java',
                              '/path2/to/a/b/c/d/FooTestCase.kt'}
  }

  Args:
      output: A string object generated by get_java_result().
      index: A string path of the index file.
  """
  _dict = {}
  with tempfile.NamedTemporaryFile() as temp_file:
    with open(temp_file.name, 'wb') as cache_file:
      if isinstance(output, bytes):
        output = output.decode()
      for entry in output.split('\n'):
        match = constants.QCLASS_OUTPUT_RE.match(entry)
        if match:
          fqcn = match.group('package') + '.' + match.group('class')
          _dict.setdefault(fqcn, set()).add(match.group('java_path'))
      try:
        pickle.dump(_dict, cache_file, protocol=2)
      except (KeyboardInterrupt, SystemExit):
        logging.error('Process interrupted or failure.')
      except IOError:
        logging.error('Failed in dumping %s', index)
    shutil.copy(temp_file.name, index)


def index_targets():
  """The entrypoint of indexing targets.

  Utilise plocate database to index reference types of CLASS, CC_CLASS,
  PACKAGE and QUALIFIED_CLASS.
  """
  start = time.time()
  unavailable_cmds = [
      cmd for cmd in [UPDATEDB, LOCATE] if not au.has_command(cmd)
  ]
  if unavailable_cmds:
    logging.debug(
        'command %s is unavailable; skip indexing...',
        ' '.join(unavailable_cmds),
    )
    return None

  indices = Indices()
  output_cache = indices.locate_db
  get_num_cmd = f'{LOCATE} -d{output_cache} --count /'
  pre_number = 0
  if output_cache.exists():
    ret, pre_number = subprocess.getstatusoutput(get_num_cmd)
    if ret != 0:
      logging.debug('Found a broken db: %s', output_cache)
      pre_number = sys.maxsize

  if run_updatedb(output_cache):
    if not indices.has_all_indices():
      logging.debug('Missing essential indices; will re-index targets.')
      return _index_targets(indices, start)

    # (b/206886222) The checksum and plocate.db file size are not indicators
    # to determining whether the source tree had changed. Therefore, when
    # fulfilling the following conditions, Atest will trigger indexing:
    #  1. different file numbers in current and previous plocate.db.
    same_number_of_files = pre_number == subprocess.getoutput(get_num_cmd)
    if not same_number_of_files:
      logging.debug('Found file number changed; will re-index targets.')
      return _index_targets(indices, start)

    #  2. had issued `repo sync` before running atest.
    checksum_file = au.get_index_path('repo_sync.md5')
    repo_syncd = not au.check_md5(checksum_file, missing_ok=False)
    if repo_syncd:
      logging.debug('Found repo syncd; will re-index targets.')
      repo_file = au.get_build_top('.repo/.repo_fetchtimes.json')
      au.start_threading(target=au.save_md5, args=[[repo_file], checksum_file])
      return _index_targets(indices, start)
    logging.debug('Indices remains the same. Ignore indexing...')
  else:
    logging.warning(
        'Unable to run %s. Search targets will be very slow.', output_cache
    )
  return None


def _index_targets(indices: Indices, start_from: float):
  """The actual index_targets function."""
  logging.debug('Indexing targets... ')
  proc_java = au.start_threading(target=get_java_result, args=[indices])
  proc_cc = au.start_threading(target=get_cc_result, args=[indices])
  proc_java.join()
  proc_cc.join()
  elapsed_time = time.time() - start_from
  logging.debug('Indexing targets took %ss', elapsed_time)
  metrics.LocalDetectEvent(
      detect_type=DetectType.INDEX_TARGETS_MS, result=int(elapsed_time * 1000)
  )


@dataclass
class Indices:
  """Class that stores index files."""

  locate_db: Path
  classes_idx: Path
  cc_classes_idx: Path
  packages_idx: Path
  fqcn_idx: Path

  def __init__(self):
    """initiation of Indices object."""
    self.locate_db = au.get_index_path('plocate.db')
    self.classes_idx = au.get_index_path('classes.idx')
    self.cc_classes_idx = au.get_index_path('cc_classes.idx')
    self.packages_idx = au.get_index_path('packages.idx')
    self.fqcn_idx = au.get_index_path('fqcn.idx')
    au.get_index_path().mkdir(parents=True, exist_ok=True)

  def has_all_indices(self):
    """Whether all indices files exist."""
    exists = [
        self.locate_db.exists(),
        self.classes_idx.exists(),
        self.cc_classes_idx.exists(),
        self.packages_idx.exists(),
        self.fqcn_idx.exists(),
    ]
    if not all(exists):
      logging.debug("Some index file doesn't exist: %s", exists)
    return all(exists)
