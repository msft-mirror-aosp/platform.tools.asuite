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
import shutil
import subprocess
import sys
import time

import atest_utils as au
import constants
import module_info

from metrics import metrics_utils

MAC_UPDB_SRC = os.path.join(os.path.dirname(__file__), 'updatedb_darwin.sh')
MAC_UPDB_DST = os.path.join(os.getenv(constants.ANDROID_HOST_OUT, ''), 'bin')
UPDATEDB = 'updatedb'
LOCATE = 'locate'
ACLOUD_DURATION = 'duration'
SEARCH_TOP = os.getenv(constants.ANDROID_BUILD_TOP, '')
MACOSX = 'Darwin'
OSNAME = os.uname()[0]
# When adding new index, remember to append constants to below tuple.
INDEXES = (constants.CC_CLASS_INDEX,
           constants.CLASS_INDEX,
           constants.LOCATE_CACHE,
           constants.MODULE_INDEX,
           constants.PACKAGE_INDEX,
           constants.QCLASS_INDEX)

# The list was generated by command:
# find `gettop` -type d -wholename `gettop`/out -prune  -o -type d -name '.*'
# -print | awk -F/ '{{print $NF}}'| sort -u
PRUNENAMES = ['.abc', '.appveyor', '.azure-pipelines',
              '.bazelci', '.buildscript',
              '.cache', '.ci', '.circleci', '.conan', '.config',
              '.externalToolBuilders',
              '.git', '.github', '.gitlab-ci', '.google', '.gradle',
              '.idea', '.intermediates',
              '.jenkins',
              '.kokoro',
              '.libs_cffi_backend',
              '.mvn',
              '.prebuilt_info', '.private', '__pycache__',
              '.repo',
              '.semaphore', '.settings', '.static', '.svn',
              '.test', '.travis', '.travis_scripts', '.tx',
              '.vscode']

def _mkdir_when_inexists(dirname):
    if not os.path.isdir(dirname):
        os.makedirs(dirname)

def _install_updatedb():
    """Install a customized updatedb for MacOS and ensure it is executable."""
    _mkdir_when_inexists(MAC_UPDB_DST)
    _mkdir_when_inexists(constants.INDEX_DIR)
    if OSNAME == MACOSX:
        shutil.copy2(MAC_UPDB_SRC, os.path.join(MAC_UPDB_DST, UPDATEDB))
        os.chmod(os.path.join(MAC_UPDB_DST, UPDATEDB), 0o0755)

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
    """Run updatedb and generate cache in $ANDROID_HOST_OUT/indexes/mlocate.db

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
    updatedb_cmd.append('-e%s' % prunepaths)
    updatedb_cmd.append('-n%s' % prunenames)
    updatedb_cmd.append('-o%s' % output_cache)
    try:
        _install_updatedb()
    except IOError as e:
        logging.error('Error installing updatedb: %s', e)

    if not has_command(UPDATEDB):
        return
    logging.debug('Running updatedb... ')
    try:
        full_env_vars = os.environ.copy()
        logging.debug('Executing: %s', updatedb_cmd)
        if subprocess.check_call(updatedb_cmd, env=full_env_vars) == 0:
            au.save_md5([constants.LOCATE_CACHE], constants.LOCATE_CACHE_MD5)
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
    _dict = {}
    with open(dump_file, 'wb') as cache_file:
        if isinstance(output, bytes):
            output = output.decode()
        for entry in output.splitlines():
            match = output_re.match(entry)
            if match:
                _dict.setdefault(match.group(key), set()).add(
                    match.group(value))
        try:
            pickle.dump(_dict, cache_file, protocol=2)
            logging.debug('Done')
        except IOError:
            os.remove(dump_file)
            logging.error('Failed in dumping %s', dump_file)

def _get_cc_result(locatedb=None):
    """Search all testable cc/cpp and grep TEST(), TEST_F() or TEST_P().

    Returns:
        A string object generated by subprocess.
    """
    if not locatedb:
        locatedb = constants.LOCATE_CACHE
    if OSNAME == MACOSX:
        find_cmd = (r"locate -d {0} '*.cpp' '*.cc' | grep -i test "
                    "| xargs egrep -sH '{1}' || true")
    else:
        find_cmd = (r"locate -d {0} / | egrep -i '/*.test.*\.(cc|cpp)$' "
                    "| xargs egrep -sH '{1}' || true")
    find_cc_cmd = find_cmd.format(locatedb, constants.CC_GREP_RE)
    logging.debug('Probing CC classes:\n %s', find_cc_cmd)
    return subprocess.check_output(find_cc_cmd, shell=True)

def _get_java_result(locatedb=None):
    """Search all testable java/kt and grep package.

    Returns:
        A string object generated by subprocess.
    """
    if not locatedb:
        locatedb = constants.LOCATE_CACHE
    package_grep_re = r'^\s*package\s+[a-z][[:alnum:]]+[^{]'
    if OSNAME == MACOSX:
        find_cmd = r"locate -d%s '*.java' '*.kt'|grep -i test" % locatedb
    else:
        find_cmd = r"locate -d%s / | egrep -i '/*.test.*\.(java|kt)$'" % locatedb
    find_java_cmd = find_cmd + '| xargs egrep -sH \'%s\' || true' % package_grep_re
    logging.debug('Probing Java classes:\n %s', find_java_cmd)
    return subprocess.check_output(find_java_cmd, shell=True)

def _index_testable_modules(index):
    """Dump testable modules read by tab completion.

    Args:
        index: A string path of the index file.
    """
    logging.debug('indexing testable modules.')
    try:
        # b/178559543 The module-info.json becomes invalid after a success build is
        # unlikely to happen, wrap with a try-catch to prevent it from happening.
        testable_modules = module_info.ModuleInfo().get_testable_modules()
    except json.JSONDecodeError:
        logging.error('Invalid module-info.json detected. Will not index modules.')
        return
    with open(index, 'wb') as cache:
        try:
            pickle.dump(testable_modules, cache, protocol=2)
            logging.debug('Done')
        except IOError:
            os.remove(cache)
            logging.error('Failed in dumping %s', cache)

def _index_cc_classes(output, index):
    """Index CC classes.

    The data structure is like:
    {
      'FooTestCase': {'/path1/to/the/FooTestCase.cpp',
                      '/path2/to/the/FooTestCase.cc'}
    }

    Args:
        output: A string object generated by _get_cc_result().
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
        output: A string object generated by _get_java_result().
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
        output: A string object generated by _get_java_result().
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
        output: A string object generated by _get_java_result().
        index: A string path of the index file.
    """
    logging.debug('indexing qualified classes.')
    _dict = {}
    with open(index, 'wb') as cache_file:
        if isinstance(output, bytes):
            output = output.decode()
        for entry in output.split('\n'):
            match = constants.QCLASS_OUTPUT_RE.match(entry)
            if match:
                fqcn = match.group('package') + '.' + match.group('class')
                _dict.setdefault(fqcn, set()).add(match.group('java_path'))
        try:
            pickle.dump(_dict, cache_file, protocol=2)
            logging.debug('Done')
        except (KeyboardInterrupt, SystemExit):
            logging.error('Process interrupted or failure.')
            os.remove(index)
        except IOError:
            logging.error('Failed in dumping %s', index)

def index_targets(output_cache=constants.LOCATE_CACHE, **kwargs):
    """The entrypoint of indexing targets.

    Utilise mlocate database to index reference types of CLASS, CC_CLASS,
    PACKAGE and QUALIFIED_CLASS. Testable module for tab completion is also
    generated in this method.

    Args:
        output_cache: A file path of the updatedb cache
                      (e.g. /path/to/mlocate.db).
        kwargs: (optional)
            class_index: A path string of the Java class index.
            qclass_index: A path string of the qualified class index.
            package_index: A path string of the package index.
            cc_class_index: A path string of the CC class index.
            module_index: A path string of the testable module index.
            integration_index: A path string of the integration index.
    """
    class_index = kwargs.pop('class_index', constants.CLASS_INDEX)
    qclass_index = kwargs.pop('qclass_index', constants.QCLASS_INDEX)
    package_index = kwargs.pop('package_index', constants.PACKAGE_INDEX)
    cc_class_index = kwargs.pop('cc_class_index', constants.CC_CLASS_INDEX)
    module_index = kwargs.pop('module_index', constants.MODULE_INDEX)
    # Uncomment below if we decide to support INTEGRATION.
    #integration_index = kwargs.pop('integration_index', constants.INT_INDEX)
    if kwargs:
        raise TypeError('Unexpected **kwargs: %r' % kwargs)

    try:
        # Step 0: generate mlocate database prior to indexing targets.
        run_updatedb(SEARCH_TOP, constants.LOCATE_CACHE)
        if not has_command(LOCATE):
            return
        # Step 1: generate output string for indexing targets.
        logging.debug('Indexing targets... ')
        cc_result = _get_cc_result(output_cache)
        java_result = _get_java_result(output_cache)
        # Step 2: index Java and CC classes.
        _index_cc_classes(cc_result, cc_class_index)
        _index_java_classes(java_result, class_index)
        _index_qualified_classes(java_result, qclass_index)
        _index_packages(java_result, package_index)
        # Step 3: index testable mods and TEST_MAPPING files.
        _index_testable_modules(module_index)

    # Delete indexes when mlocate.db is locked() or other CalledProcessError.
    # (b/141588997)
    except subprocess.CalledProcessError as err:
        logging.error('Executing %s error.', UPDATEDB)
        metrics_utils.handle_exc_and_send_exit_event(
            constants.MLOCATEDB_LOCKED)
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
    if au.is_valid_json_file(report_file):
        try:
            with open(report_file, 'r') as _rfile:
                result = json.load(_rfile)
            result[ACLOUD_DURATION] = acloud_duration
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
        if not au.is_valid_json_file(report_file):
            return constants.EXIT_CODE_AVD_CREATE_FAILURE
        with open(report_file, 'r') as rfile:
            result = json.load(rfile)

        if result.get('status') == 'SUCCESS':
            logging.info('acloud create successfully!')
            # Always fetch the adb of the first created AVD.
            adb_port = result.get('data').get('devices')[0].get('adb_port')
            os.environ[constants.ANDROID_SERIAL] = '127.0.0.1:{}'.format(adb_port)
            return constants.EXIT_CODE_SUCCESS
        au.colorful_print(
            'acloud create failed. Please check\n{}\nfor detail'.format(
                report_file), constants.RED)
        return constants.EXIT_CODE_AVD_CREATE_FAILURE

    # 2. Failed to create because of invalid acloud arguments.
    logging.error('Invalid acloud arguments found!')
    return constants.EXIT_CODE_AVD_INVALID_ARGS

def get_acloud_duration(report_file):
    """Method which gets the duration of 'acloud create' from a report file.

    Args:
        report_file: A path string of acloud report file.

    Returns:
        An float of seconds which acloud create takes.
    """
    if not au.is_valid_json_file(report_file):
        return 0
    with open(report_file, 'r') as rfile:
        return json.load(rfile).get(ACLOUD_DURATION, 0)


if __name__ == '__main__':
    if not os.getenv(constants.ANDROID_HOST_OUT, ''):
        sys.exit()
    index_targets()
