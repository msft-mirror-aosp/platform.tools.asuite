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

"""Atest tool functions."""

# pylint: disable=line-too-long

from __future__ import print_function

import json
import logging
import os
import pickle
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from pathlib import Path

import atest_utils as au
import constants

from atest_enum import ExitCode
from metrics import metrics_utils

UPDATEDB = 'updatedb'
LOCATE = 'locate'
ACLOUD_DURATION = 'duration'
SEARCH_TOP = os.getenv(constants.ANDROID_BUILD_TOP, '')
# When adding new index, remember to append constants to below tuple.
INDEXES = (constants.CC_CLASS_INDEX,
           constants.CLASS_INDEX,
           constants.LOCATE_CACHE,
           constants.PACKAGE_INDEX,
           constants.QCLASS_INDEX)

# The list was generated by command:
# find `gettop` -type d -wholename `gettop`/out -prune  -o -type d -name '.*'
# -print | awk -F/ '{{print $NF}}'| sort -u
PRUNENAMES = ['.abc', '.appveyor', '.azure-pipelines',
              '.bazelci', '.build-id', '.buildkite', '.buildscript',
              '.cargo', '.ci', '.circleci', '.clusterfuzzlite', '.conan',
              '.devcontainer',
              '.dwz',
              '.externalToolBuilders',
              '.git', '.githooks', '.github', '.gitlab', '.gitlab-ci', '.google',
              '.hidden',
              '.idea', '.intermediates',
              '.jenkins',
              '.kokoro',
              '.libs_cffi_backend',
              '.more', '.mvn',
              '.prebuilt_info', '.private', '__pycache__',
              '.repo',
              '.settings', '.static', '.svn',
              '.test',
              '.travis',
              '.travis_scripts',
              '.tx',
              '.vscode']

def _delete_indexes():
    """Delete all available index files."""
    for index in INDEXES:
        if os.path.isfile(index):
            os.remove(index)

def get_report_file(results_dir, acloud_args):
    """Get the acloud report file path.

    This method can parse either string:
        --acloud-create '--report-file=/tmp/acloud.json'
        --acloud-create '--report-file /tmp/acloud.json'
    and return '/tmp/acloud.json' as the report file. Otherwise returning the
    default path(/tmp/atest_result/<hashed_dir>/acloud_status.json).

    Args:
        results_dir: string of directory to store atest results.
        acloud_args: string of acloud create.

    Returns:
        A string path of acloud report file.
    """
    match = constants.ACLOUD_REPORT_FILE_RE.match(acloud_args)
    if match:
        return match.group('report_file')
    return os.path.join(results_dir, 'acloud_status.json')

def has_command(cmd):
    """Detect if the command is available in PATH.

    Args:
        cmd: A string of the tested command.

    Returns:
        True if found, False otherwise.
    """
    return bool(shutil.which(cmd))

def run_updatedb(search_root=SEARCH_TOP, output_cache=constants.LOCATE_CACHE,
                 **kwargs):
    """Run updatedb and generate cache in $ANDROID_HOST_OUT/indexes/plocate.db

    Args:
        search_root: The path of the search root(-U).
        output_cache: The filename of the updatedb cache(-o).
        kwargs: (optional)
            prunepaths: A list of paths unwanted to be searched(-e).
            prunenames: A list of dirname that won't be cached(-n).
    """
    prunenames = kwargs.pop('prunenames', ' '.join(PRUNENAMES))
    prunepaths = kwargs.pop('prunepaths', os.path.join(search_root, 'out'))
    if kwargs:
        raise TypeError('Unexpected **kwargs: %r' % kwargs)
    updatedb_cmd = [UPDATEDB, '-l0']
    updatedb_cmd.append('-U%s' % search_root)
    updatedb_cmd.append('-n%s' % prunenames)
    updatedb_cmd.append('-o%s' % output_cache)
    # (b/206866627) /etc/updatedb.conf excludes /mnt from scanning on Linux.
    # Use --prunepaths to override the default configuration.
    updatedb_cmd.append('--prunepaths')
    updatedb_cmd.append(prunepaths)
    # Support scanning bind mounts as well.
    updatedb_cmd.extend(['--prune-bind-mounts', 'no'])

    if not has_command(UPDATEDB):
        return
    logging.debug('Running updatedb... ')
    try:
        full_env_vars = os.environ.copy()
        logging.debug('Executing: %s', updatedb_cmd)
        if not os.path.isdir(constants.INDEX_DIR):
            os.makedirs(constants.INDEX_DIR)
        subprocess.call(updatedb_cmd, env=full_env_vars)
    except (KeyboardInterrupt, SystemExit):
        logging.error('Process interrupted or failure.')

def _dump_index(dump_file, output, output_re, key, value):
    """Dump indexed data with pickle.

    Args:
        dump_file: A string of absolute path of the index file.
        output: A string generated by locate and grep.
        output_re: An regex which is used for grouping patterns.
        key: A string for dictionary key, e.g. classname, package,
             cc_class, etc.
        value: A set of path.

    The data structure will be like:
    {
      'Foo': {'/path/to/Foo.java', '/path2/to/Foo.kt'},
      'Boo': {'/path3/to/Boo.java'}
    }
    """
    temp_file = tempfile.NamedTemporaryFile()
    _dict = {}
    with open(temp_file.name, 'wb') as cache_file:
        if isinstance(output, bytes):
            output = output.decode()
        for entry in output.splitlines():
            match = output_re.match(entry)
            if match:
                _dict.setdefault(match.group(key), set()).add(
                    match.group(value))
        try:
            pickle.dump(_dict, cache_file, protocol=2)
        except IOError:
            logging.error('Failed in dumping %s', dump_file)
    shutil.copy(temp_file.name, dump_file)
    temp_file.close()

# pylint: disable=anomalous-backslash-in-string
def get_manifest_result(locatedb=constants.LOCATE_CACHE, **kwargs):
    """Search all AndroidManifest.xml and grep package name.

    Args:
        locatedb: A string of the absolute path of the plocate.db
        kwargs: (optional)
            manifest_index: A path string of the manifest index.
    """
    find_manifest_cmd = (
        f"{LOCATE} -d{locatedb} --regex '/AndroidManifest\.xml$'")
    logging.debug('Probing AndroidManifest.xml files:\n %s', find_manifest_cmd)
    result = subprocess.check_output(find_manifest_cmd, shell=True)

    manifest_index = kwargs.pop('manifest_index', constants.MANIFEST_INDEX)
    au.run_multi_proc(func=_index_manifests, args=[result, manifest_index])

# pylint: disable=anomalous-backslash-in-string
def get_cc_result(locatedb=constants.LOCATE_CACHE, **kwargs):
    """Search all testable cc/cpp and grep TEST(), TEST_F() or TEST_P().

    After searching cc/cpp files, index corresponding data types in parallel.

    Args:
        locatedb: A string of the absolute path of the plocate.db
        kwargs: (optional)
            cc_class_index: A path string of the CC class index.
    """
    find_cc_cmd = (
        f"{LOCATE} -id{locatedb} --regex '/*.test.*\.(cc|cpp)$'"
        f"| xargs egrep -sH '{constants.CC_GREP_RE}' 2>/dev/null || true")
    logging.debug('Probing CC classes:\n %s', find_cc_cmd)
    result = subprocess.check_output(find_cc_cmd, shell=True)

    cc_class_index = kwargs.pop('cc_class_index', constants.CC_CLASS_INDEX)
    au.run_multi_proc(func=_index_cc_classes, args=[result, cc_class_index])

# pylint: disable=anomalous-backslash-in-string
def get_java_result(locatedb=constants.LOCATE_CACHE, **kwargs):
    """Search all testable java/kt and grep package.

    After searching java/kt files, index corresponding data types in parallel.

    Args:
        locatedb: A string of the absolute path of the plocate.db
        kwargs: (optional)
            class_index: A path string of the Java class index.
            qclass_index: A path string of the qualified class index.
            package_index: A path string of the package index.
    """
    package_grep_re = r'^\s*package\s+[a-z][[:alnum:]]+[^{]'
    find_java_cmd = (
        f"{LOCATE} -id{locatedb} --regex '/*.test.*\.(java|kt)$' "
        # (b/204398677) suppress stderr when indexing target terminated.
        f"| xargs egrep -sH '{package_grep_re}' 2>/dev/null|| true")
    logging.debug('Probing Java classes:\n %s', find_java_cmd)
    result = subprocess.check_output(find_java_cmd, shell=True)

    class_index = kwargs.pop('class_index', constants.CLASS_INDEX)
    qclass_index = kwargs.pop('qclass_index', constants.QCLASS_INDEX)
    package_index = kwargs.pop('package_index', constants.PACKAGE_INDEX)
    au.run_multi_proc(func=_index_java_classes, args=[result, class_index])
    au.run_multi_proc(func=_index_qualified_classes, args=[result, qclass_index])
    au.run_multi_proc(func=_index_packages, args=[result, package_index])

def _index_manifests(output, index):
    """Index AndroidManifest.xml files.

    The data structure is like:
    {
      'com.android.settings': {'/path1/foo/boo/AndroidManifest.xml',
                               '/path1/foo/AndroidManifest.xml'}
    }

    Args:
        output: A string object generated by get_manifest_result().
        index: A string path of the index file.
    """
    logging.debug('indexing package names for instrumentation tests.')
    _dict = {}
    manifest_package_re =  re.compile(r'[a-z][\w]+(\.[\w]+)*')
    if isinstance(output, bytes):
        output = output.decode()
    manifest_files = output.splitlines()
    with open(index, 'wb') as cache_file:
        for xml in manifest_files:
            try:
                xml_root = ET.parse(xml).getroot()
                for item in xml_root.findall('.'):
                    if 'package' in item.attrib.keys():
                        pkg = item.attrib.get('package')
                        match = manifest_package_re.match(pkg)
                        if match:
                            _dict.setdefault(pkg, set()).add(xml)
            except ET.ParseError:
                logging.debug('%s: not a valid xml.', xml)
        try:
            pickle.dump(_dict, cache_file, protocol=2)
        except (KeyboardInterrupt, SystemExit):
            logging.error('Process interrupted or failure.')
            os.remove(index)
        except IOError:
            logging.error('Failed in dumping %s', index)

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
    logging.debug('indexing CC classes.')
    _dump_index(dump_file=index, output=output,
                output_re=constants.CC_OUTPUT_RE,
                key='test_name', value='file_path')

def _index_java_classes(output, index):
    """Index Java classes.
    The data structure is like:
    {
        'FooTestCase': {'/path1/to/the/FooTestCase.java',
                        '/path2/to/the/FooTestCase.kt'}
    }

    Args:
        output: A string object generated by get_java_result().
        index: A string path of the index file.
    """
    logging.debug('indexing Java classes.')
    _dump_index(dump_file=index, output=output,
                output_re=constants.CLASS_OUTPUT_RE,
                key='class', value='java_path')

def _index_packages(output, index):
    """Index Java packages.
    The data structure is like:
    {
        'a.b.c.d': {'/path1/to/a/b/c/d/',
                    '/path2/to/a/b/c/d/'
    }

    Args:
        output: A string object generated by get_java_result().
        index: A string path of the index file.
    """
    logging.debug('indexing packages.')
    _dump_index(dump_file=index,
                output=output, output_re=constants.PACKAGE_OUTPUT_RE,
                key='package', value='java_dir')

def _index_qualified_classes(output, index):
    """Index Fully Qualified Java Classes(FQCN).
    The data structure is like:
    {
        'a.b.c.d.FooTestCase': {'/path1/to/a/b/c/d/FooTestCase.java',
                                '/path2/to/a/b/c/d/FooTestCase.kt'}
    }

    Args:
        output: A string object generated by get_java_result().
        index: A string path of the index file.
    """
    logging.debug('indexing qualified classes.')
    temp_file = tempfile.NamedTemporaryFile()
    _dict = {}
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
    temp_file.close()

def index_targets(output_cache=constants.LOCATE_CACHE):
    """The entrypoint of indexing targets.

    Utilise plocate database to index reference types of CLASS, CC_CLASS,
    PACKAGE and QUALIFIED_CLASS. Testable module for tab completion is also
    generated in this method.

    Args:
        output_cache: A file path of the updatedb cache
                      (e.g. /path/to/plocate.db).
    """
    if not has_command(LOCATE):
        logging.debug('command %s is unavailable; skip indexing.', LOCATE)
        return
    pre_md5sum = au.md5sum(constants.LOCATE_CACHE)
    pre_size = sys.maxsize
    if Path(constants.LOCATE_CACHE).is_file():
        pre_size = Path(constants.LOCATE_CACHE).stat().st_size
    try:
        # Step 0: generate plocate database prior to indexing targets.
        run_updatedb(SEARCH_TOP, output_cache)
        # (b/206886222) checksum may be different even the src is not changed.
        # check filesize as well to tell whether there are src changes or just
        # metadata changes.
        if any((pre_md5sum == au.md5sum(constants.LOCATE_CACHE),
                pre_size == Path(constants.LOCATE_CACHE).stat().st_size)):
            logging.debug('%s remains the same. Ignore indexing', output_cache)
            return
        # Step 1: generate output string for indexing targets when needed.
        logging.debug('Indexing targets... ')
        au.run_multi_proc(func=get_java_result, args=[output_cache])
        au.run_multi_proc(func=get_cc_result, args=[output_cache])
        au.run_multi_proc(func=get_manifest_result, args=[output_cache])
    # Delete indexes when plocate.db is locked() or other CalledProcessError.
    # (b/141588997)
    except subprocess.CalledProcessError as err:
        logging.error('Executing %s error.', UPDATEDB)
        metrics_utils.handle_exc_and_send_exit_event(
            constants.PLOCATEDB_LOCKED)
        if err.output:
            logging.error(err.output)
        _delete_indexes()

def acloud_create(report_file, args="", no_metrics_notice=True):
    """Method which runs acloud create with specified args in background.

    Args:
        report_file: A path string of acloud report file.
        args: A string of arguments.
        no_metrics_notice: Boolean whether sending data to metrics or not.
    """
    notice = constants.NO_METRICS_ARG if no_metrics_notice else ""
    match = constants.ACLOUD_REPORT_FILE_RE.match(args)
    report_file_arg = '--report-file={}'.format(report_file) if not match else ""
    # (b/161759557) Assume yes for acloud create to streamline atest flow.
    acloud_cmd = ('acloud create -y {ACLOUD_ARGS} '
                  '{REPORT_FILE_ARG} '
                  '{METRICS_NOTICE} '
                  ).format(ACLOUD_ARGS=args,
                           REPORT_FILE_ARG=report_file_arg,
                           METRICS_NOTICE=notice)
    au.colorful_print("\nCreating AVD via acloud...", constants.CYAN)
    logging.debug('Executing: %s', acloud_cmd)
    start = time.time()
    proc = subprocess.Popen(acloud_cmd, shell=True)
    proc.communicate()
    acloud_duration = time.time() - start
    logging.info('"acloud create" process has completed.')
    # Insert acloud create duration into the report file.
    result = au.load_json_safely(report_file)
    if result:
        result[ACLOUD_DURATION] = acloud_duration
        try:
            with open(report_file, 'w+') as _wfile:
                _wfile.write(json.dumps(result))
        except OSError as e:
            logging.error("Failed dumping duration to the report file: %s", str(e))

def probe_acloud_status(report_file):
    """Method which probes the 'acloud create' result status.

    If the report file exists and the status is 'SUCCESS', then the creation is
    successful.

    Args:
        report_file: A path string of acloud report file.

    Returns:
        0: success.
        8: acloud creation failure.
        9: invalid acloud create arguments.
    """
    # 1. Created but the status is not 'SUCCESS'
    if os.path.exists(report_file):
        if not au.load_json_safely(report_file):
            return ExitCode.AVD_CREATE_FAILURE
        with open(report_file, 'r') as rfile:
            result = json.load(rfile)

        if result.get('status') == 'SUCCESS':
            logging.info('acloud create successfully!')
            # Always fetch the adb of the first created AVD.
            adb_port = result.get('data').get('devices')[0].get('adb_port')
            is_remote_instance = result.get('command') == 'create_cf'
            adb_ip = '127.0.0.1' if is_remote_instance else '0.0.0.0'
            os.environ[constants.ANDROID_SERIAL] = f'{adb_ip}:{adb_port}'
            return ExitCode.SUCCESS
        au.colorful_print(
            'acloud create failed. Please check\n{}\nfor detail'.format(
                report_file), constants.RED)
        return ExitCode.AVD_CREATE_FAILURE

    # 2. Failed to create because of invalid acloud arguments.
    logging.error('Invalid acloud arguments found!')
    return ExitCode.AVD_INVALID_ARGS

def get_acloud_duration(report_file):
    """Method which gets the duration of 'acloud create' from a report file.

    Args:
        report_file: A path string of acloud report file.

    Returns:
        An float of seconds which acloud create takes.
    """
    content = au.load_json_safely(report_file)
    if not content:
        return 0
    return content.get(ACLOUD_DURATION, 0)


if __name__ == '__main__':
    if not os.getenv(constants.ANDROID_HOST_OUT, ''):
        sys.exit()
    index_targets()
