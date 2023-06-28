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

"""
Utility functions for atest.
"""


# pylint: disable=import-outside-toplevel
# pylint: disable=too-many-lines

from __future__ import print_function

import enum
import datetime
import fnmatch
import hashlib
import html
import importlib
import itertools
import json
import logging
import os
import pickle
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib
import zipfile

from dataclasses import dataclass
from multiprocessing import Process
from pathlib import Path
from typing import Any, Dict, List, Set

import xml.etree.ElementTree as ET

from atest.atest_enum import DetectType, ExitCode, FilterType

#pylint: disable=wrong-import-position
from atest import atest_decorator
from atest import atest_error
from atest import constants

from atest.metrics import metrics
from atest.metrics import metrics_utils
from atest.tf_proto import test_record_pb2

_BASH_RESET_CODE = '\033[0m\n'
DIST_OUT_DIR = Path(os.environ.get(constants.ANDROID_BUILD_TOP, os.getcwd())
                    + '/out/dist/')
MAINLINE_MODULES_EXT_RE = re.compile(r'(.apex|.apks|.apk)$')

# Arbitrary number to limit stdout for failed runs in _run_limited_output.
# Reason for its use is that the make command itself has its own carriage
# return output mechanism that when collected line by line causes the streaming
# full_output list to be extremely large.
_FAILED_OUTPUT_LINE_LIMIT = 100
# Regular expression to match the start of a ninja compile:
# ex: [ 99% 39710/39711]
_BUILD_COMPILE_STATUS = re.compile(r'\[\s*(\d{1,3}%\s+)?\d+/\d+\]')
_BUILD_FAILURE = 'FAILED: '
CMD_RESULT_PATH = os.path.join(os.environ.get(constants.ANDROID_BUILD_TOP,
                                              os.getcwd()),
                               'tools/asuite/atest/test_data',
                               'test_commands.json')
BUILD_TOP_HASH = hashlib.md5(os.environ.get(constants.ANDROID_BUILD_TOP, '').
                             encode()).hexdigest()
_DEFAULT_TERMINAL_WIDTH = 80
_DEFAULT_TERMINAL_HEIGHT = 25
_BUILD_CMD = 'build/soong/soong_ui.bash'
_FIND_MODIFIED_FILES_CMDS = (
    "cd {};"
    "local_branch=$(git rev-parse --abbrev-ref HEAD);"
    "remote_branch=$(git branch -r | grep '\\->' | awk '{{print $1}}');"
    # Get the number of commits from local branch to remote branch.
    "ahead=$(git rev-list --left-right --count $local_branch...$remote_branch "
    "| awk '{{print $1}}');"
    # Get the list of modified files from HEAD to previous $ahead generation.
    "git diff HEAD~$ahead --name-only")
_ANDROID_BUILD_EXT = ('.bp', '.mk')

# Set of special chars for various purposes.
_REGEX_CHARS = {'[', '(', '{', '|', '\\', '*', '?', '+', '^'}
_WILDCARD_CHARS = {'?', '*'}

_WILDCARD_FILTER_RE = re.compile(r'.*[?|*]$')
_REGULAR_FILTER_RE = re.compile(r'.*\w$')

SUGGESTIONS = {
    # (b/198581508) Do not run "adb sync" for the users.
    'CANNOT LINK EXECUTABLE': 'Please run "adb sync" or reflash the device(s).',
    # (b/177626045) If Atest does not install target application properly.
    'Runner reported an invalid method': 'Please reflash the device(s).'
}

_BUILD_ENV = {}


@dataclass
class BuildEnvProfiler:
    """Represents the condition before and after trigging build."""
    ninja_file: Path
    ninja_file_mtime: float
    variable_file: Path
    variable_file_md5: str
    clean_out: bool
    build_files_integrity: bool


@enum.unique
class BuildOutputMode(enum.Enum):
    "Represents the different ways to display build output."
    STREAMED = 'streamed'
    LOGGED = 'logged'

    def __init__(self, arg_name: str):
        self._description = arg_name

    # pylint: disable=missing-function-docstring
    def description(self):
        return self._description


@dataclass
class AndroidVariables:
    """Class that stores the value of environment variables."""
    build_top: str
    product_out: str
    target_out_cases: str
    host_out: str
    host_out_cases: str
    target_product: str
    build_variant: str

    def __init__(self):
        self.build_top = os.getenv('ANDROID_BUILD_TOP')
        self.product_out = os.getenv('ANDROID_PRODUCT_OUT')
        self.target_out_cases = os.getenv('ANDROID_TARGET_OUT_TESTCASES')
        self.host_out = os.getenv('ANDROID_HOST_OUT')
        self.host_out_cases = os.getenv('ANDROID_HOST_OUT_TESTCASES')
        self.target_product = os.getenv('TARGET_PRODUCT')
        self.build_variant = os.getenv('TARGET_BUILD_VARIANT')


def get_build_top(*joinpaths: Any) -> Path:
    """Get the absolute path from the given repo path."""
    return Path(AndroidVariables().build_top, *joinpaths)


def get_host_out(*joinpaths: Any) -> Path:
    """Get the absolute host out path from the given path."""
    return Path(AndroidVariables().host_out, *joinpaths)


def get_product_out(*joinpaths: Any) -> Path:
    """Get the absolute product out path from the given path."""
    return Path(AndroidVariables().product_out, *joinpaths)


def get_build_cmd(dump=False):
    """Compose build command with no-absolute path and flag "--make-mode".

    Args:
        dump: boolean that determines the option of build/soong/soong_iu.bash.
              True: used to dump build variables, equivalent to printconfig.
                    e.g. build/soong/soong_iu.bash --dumpvar-mode <VAR_NAME>
              False: (default) used to build targets in make mode.
                    e.g. build/soong/soong_iu.bash --make-mode <MOD_NAME>

    Returns:
        A list of soong build command.
    """
    make_cmd = ('%s/%s' %
                (os.path.relpath(os.environ.get(
                    constants.ANDROID_BUILD_TOP, os.getcwd()), os.getcwd()),
                 _BUILD_CMD))
    if dump:
        return [make_cmd, '--dumpvar-mode', 'report_config']
    return [make_cmd, '--make-mode']

def _capture_fail_section(full_log):
    """Return the error message from the build output.

    Args:
        full_log: List of strings representing full output of build.

    Returns:
        capture_output: List of strings that are build errors.
    """
    am_capturing = False
    capture_output = []
    for line in full_log:
        if am_capturing and _BUILD_COMPILE_STATUS.match(line):
            break
        if am_capturing or line.startswith(_BUILD_FAILURE):
            capture_output.append(line)
            am_capturing = True
            continue
    return capture_output


def _capture_limited_output(full_log):
    """Return the limited error message from capture_failed_section.

    Args:
        full_log: List of strings representing full output of build.

    Returns:
        output: List of strings that are build errors.
    """
    # Parse out the build error to output.
    output = _capture_fail_section(full_log)
    if not output:
        output = full_log
    if len(output) >= _FAILED_OUTPUT_LINE_LIMIT:
        output = output[-_FAILED_OUTPUT_LINE_LIMIT:]
    output = 'Output (may be trimmed):\n%s' % ''.join(output)
    return output


# TODO: b/187122993 refine subprocess with 'with-statement' in fixit week.
def _run_limited_output(cmd, env_vars=None):
    """Runs a given command and streams the output on a single line in stdout.

    Args:
        cmd: A list of strings representing the command to run.
        env_vars: Optional arg. Dict of env vars to set during build.

    Raises:
        subprocess.CalledProcessError: When the command exits with a non-0
            exitcode.
    """
    # Send stderr to stdout so we only have to deal with a single pipe.
    with subprocess.Popen(cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, env=env_vars) as proc:
        sys.stdout.write('\n')
        term_width, _ = get_terminal_size()
        white_space = " " * int(term_width)
        full_output = []
        while proc.poll() is None:
            line = proc.stdout.readline().decode('utf-8')
            # Readline will often return empty strings.
            if not line:
                continue
            full_output.append(line)
            # Trim the line to the width of the terminal.
            # Note: Does not handle terminal resizing, which is probably not
            #       worth checking the width every loop.
            if len(line) >= term_width:
                line = line[:term_width - 1]
            # Clear the last line we outputted.
            sys.stdout.write('\r%s\r' % white_space)
            sys.stdout.write('%s' % line.strip())
            sys.stdout.flush()
        # Reset stdout (on bash) to remove any custom formatting and newline.
        sys.stdout.write(_BASH_RESET_CODE)
        sys.stdout.flush()
        # Wait for the Popen to finish completely before checking the
        # returncode.
        proc.wait()
        if proc.returncode != 0:
            # get error log from "OUT_DIR/error.log"
            error_log_file = os.path.join(get_build_out_dir(), "error.log")
            output = []
            if os.path.isfile(error_log_file):
                if os.stat(error_log_file).st_size > 0:
                    with open(error_log_file, encoding='utf-8') as f:
                        output = f.read()
            if not output:
                output = _capture_limited_output(full_output)
            raise subprocess.CalledProcessError(proc.returncode, cmd, output)


def get_build_out_dir() -> str:
    """Get android build out directory.

    The order of the rules are:
    1. OUT_DIR
    2. OUT_DIR_COMMON_BASE
    3. ANDROID_BUILD_TOP/out

    Returns:
        String of the out directory.
    """
    build_top = os.environ.get(constants.ANDROID_BUILD_TOP, '/')
    # Get the out folder if user specified $OUT_DIR
    custom_out_dir = os.environ.get(constants.ANDROID_OUT_DIR)
    custom_out_dir_common_base = os.environ.get(
        constants.ANDROID_OUT_DIR_COMMON_BASE)
    user_out_dir = None
    # If OUT_DIR == /output, the output dir will always be /outdir
    # regardless of branch names. (Not recommended.)
    if custom_out_dir:
        if os.path.isabs(custom_out_dir):
            user_out_dir = custom_out_dir
        else:
            user_out_dir = os.path.join(build_top, custom_out_dir)
    # https://source.android.com/setup/build/initializing#using-a-separate-output-directory
    # If OUT_DIR_COMMON_BASE is /output and the source tree is /src/master1,
    # the output dir will be /output/master1.
    elif custom_out_dir_common_base:
        build_top_basename = os.path.basename(build_top)
        if os.path.isabs(custom_out_dir_common_base):
            user_out_dir = os.path.join(custom_out_dir_common_base,
                                        build_top_basename)
        else:
            user_out_dir = os.path.join(build_top, custom_out_dir_common_base,
                                        build_top_basename)
    if user_out_dir:
        return user_out_dir
    return os.path.join(build_top, "out")

def update_build_env(env: Dict[str, str]):
    """Method that updates build environment variables."""
    # pylint: disable=global-statement, global-variable-not-assigned
    global _BUILD_ENV
    _BUILD_ENV.update(env)


def build(build_targets: Set[str]):
    """Shell out and invoke run_build_cmd to make build_targets.

    Args:
        build_targets: A set of strings of build targets to make.

    Returns:
        Boolean of whether build command was successful, True if nothing to
        build.
    """
    if not build_targets:
        logging.debug('No build targets, skipping build.')
        return True

    # pylint: disable=global-statement, global-variable-not-assigned
    global _BUILD_ENV
    full_env_vars = os.environ.copy()
    update_build_env(full_env_vars)
    print('\n%s\n%s' % (
        colorize("Building Dependencies...", constants.CYAN),
                 ', '.join(build_targets)))
    logging.debug('Building Dependencies: %s', ' '.join(build_targets))
    cmd = get_build_cmd() + list(build_targets)
    return _run_build_cmd(cmd, _BUILD_ENV)


def _run_build_cmd(cmd: List[str], env_vars: Dict[str, str]):
    """The main process of building targets.

    Args:
        cmd: A list of soong command.
        env_vars: Dict of environment variables used for build.
    Returns:
        Boolean of whether build command was successful, True if nothing to
        build.
    """
    logging.debug('Executing command: %s', cmd)
    build_profiler = _build_env_profiling()
    try:
        if env_vars.get('BUILD_OUTPUT_MODE') == BuildOutputMode.STREAMED.value:
            print()
            subprocess.check_call(cmd, stderr=subprocess.STDOUT, env=env_vars)
        else:
            # Note that piping stdout forces Soong to switch to 'dumb terminal
            # mode' which only prints completed actions. This gives users the
            # impression that actions are taking longer than they really are.
            # See b/233044822 for more details.
            log_path = Path(get_build_out_dir()).joinpath('verbose.log.gz')
            print('\n(Build log may not reflect actual status in simple output'
                  'mode; check {} for detail after build finishes.)'.format(
                    colorize(f'{log_path}', constants.CYAN)
                  ), end='')
            _run_limited_output(cmd, env_vars=env_vars)
        _send_build_condition_metrics(build_profiler, cmd)
        logging.info('Build successful')
        return True
    except subprocess.CalledProcessError as err:
        logging.error('Build failure when running: %s', ' '.join(cmd))
        if err.output:
            logging.error(err.output)
        return False


# pylint: disable=unused-argument
def get_result_server_args(for_test_mapping=False):
    """Return list of args for communication with result server.

    Args:
        for_test_mapping: True if the test run is for Test Mapping to include
            additional reporting args. Default is False.
    """
    # Customize test mapping argument here if needed.
    return constants.RESULT_SERVER_ARGS

def sort_and_group(iterable, key):
    """Sort and group helper function."""
    return itertools.groupby(sorted(iterable, key=key), key=key)


def is_test_mapping(args):
    """Check if the atest command intends to run tests in test mapping.

    When atest runs tests in test mapping, it must have at most one test
    specified. If a test is specified, it must be started with  `:`,
    which means the test value is a test group name in TEST_MAPPING file, e.g.,
    `:postsubmit`.

    If --host-unit-test-only or --smart-testing-local was applied, it doesn't
    intend to be a test_mapping test.
    If any test mapping options is specified, the atest command must also be
    set to run tests in test mapping files.

    Args:
        args: arg parsed object.

    Returns:
        True if the args indicates atest shall run tests in test mapping. False
        otherwise.
    """
    if any((args.host_unit_test_only, args.smart_testing_local)):
        return False
    if any((args.test_mapping, args.include_subdirs, not args.tests)):
        return True
    # ':postsubmit' implicitly indicates running in test-mapping mode.
    return all((len(args.tests) == 1, args.tests[0][0] == ':'))


@atest_decorator.static_var("cached_has_colors", {})
def _has_colors(stream):
    """Check the output stream is colorful.

    Args:
        stream: The standard file stream.

    Returns:
        True if the file stream can interpreter the ANSI color code.
    """
    cached_has_colors = _has_colors.cached_has_colors
    if stream in cached_has_colors:
        return cached_has_colors[stream]
    cached_has_colors[stream] = True
    # Following from Python cookbook, #475186
    if not hasattr(stream, "isatty"):
        cached_has_colors[stream] = False
        return False
    if not stream.isatty():
        # Auto color only on TTYs
        cached_has_colors[stream] = False
        return False
    # curses.tigetnum() cannot be used for telling supported color numbers
    # because it does not come with the prebuilt py3-cmd.
    return cached_has_colors[stream]


def colorize(text, color, bp_color=None):
    """ Convert to colorful string with ANSI escape code.

    Args:
        text: A string to print.
        color: Forground(Text) color which is an ANSI code shift for colorful
               print. They are defined in constants_default.py.
        bp_color: Backgroud color which is an ANSI code shift for colorful
                   print.

    Returns:
        Colorful string with ANSI escape code.
    """
    clr_pref = '\033[1;'
    clr_suff = '\033[0m'
    has_colors = _has_colors(sys.stdout)
    if has_colors:
        background_color = ''
        if bp_color:
            # Foreground(Text) ranges from 30-37
            text_color = 30 + color
            # Background ranges from 40-47
            background_color = ';%d' % (40 + bp_color)
        else:
            text_color = 30 + color
        clr_str = "%s%d%sm%s%s" % (clr_pref, text_color, background_color,
                                    text, clr_suff)
    else:
        clr_str = text
    return clr_str


def colorful_print(text, color, bp_color=None, auto_wrap=True):
    """Print out the text with color.

    Args:
        text: A string to print.
        color: Forground(Text) color which is an ANSI code shift for colorful
               print. They are defined in constants_default.py.
        bp_color: Backgroud color which is an ANSI code shift for colorful
                   print.
        auto_wrap: If True, Text wraps while print.
    """
    output = colorize(text, color, bp_color)
    if auto_wrap:
        print(output)
    else:
        print(output, end="")


def get_terminal_size():
    """Get terminal size and return a tuple.

    Returns:
        2 integers: the size of X(columns) and Y(lines/rows).
    """
    # Determine the width of the terminal. We'll need to clear this many
    # characters when carriage returning. Set default value as 80.
    columns, rows = shutil.get_terminal_size(
        fallback=(_DEFAULT_TERMINAL_WIDTH,
                  _DEFAULT_TERMINAL_HEIGHT))
    return columns, rows


def handle_test_runner_cmd(input_test, test_cmds, do_verification=False,
                           result_path=constants.VERIFY_DATA_PATH):
    """Handle the runner command of input tests.

    Args:
        input_test: A string of input tests pass to atest.
        test_cmds: A list of strings for running input tests.
        do_verification: A boolean to indicate the action of this method.
                         True: Do verification without updating result map and
                               raise DryRunVerificationError if verifying fails.
                         False: Update result map, if the former command is
                                different with current command, it will confirm
                                with user if they want to update or not.
        result_path: The file path for saving result.
    """
    full_result_content = load_json_safely(result_path)
    former_test_cmds = full_result_content.get(input_test, [])
    test_cmds = _normalize(test_cmds)
    former_test_cmds = _normalize(former_test_cmds)
    if not _are_identical_cmds(test_cmds, former_test_cmds):
        if do_verification:
            raise atest_error.DryRunVerificationError(
                'Dry run verification failed, former commands: {}'.format(
                    former_test_cmds))
        if former_test_cmds:
            # If former_test_cmds is different from test_cmds, ask users if they
            # are willing to update the result.
            print('Former cmds = %s' % former_test_cmds)
            print('Current cmds = %s' % test_cmds)
            if not prompt_with_yn_result('Do you want to update former result '
                                         'to the latest one?', True):
                print('SKIP updating result!!!')
                return
    else:
        # If current commands are the same as the formers, no need to update
        # result.
        return
    full_result_content[input_test] = test_cmds
    with open(result_path, 'w', encoding='utf-8') as outfile:
        json.dump(full_result_content, outfile, indent=0)
        print('Save result mapping to %s' % result_path)

def _normalize(cmd_list):
    """Method that normalize commands. Note that '--atest-log-file-path' is not
    considered a critical argument, therefore, it will be removed during
    the comparison. Also, atest can be ran in any place, so verifying relative
    path, LD_LIBRARY_PATH, and --proto-output-file is regardless as well.

    Args:
        cmd_list: A list with one element. E.g. ['cmd arg1 arg2 True']

    Returns:
        A list with elements. E.g. ['cmd', 'arg1', 'arg2', 'True']
    """
    _cmd = ' '.join(cmd_list).split()
    for cmd in _cmd:
        if cmd.startswith('--skip-all-system-status-check'):
            _cmd.remove(cmd)
            continue
        if cmd.startswith('--atest-log-file-path'):
            _cmd.remove(cmd)
            continue
        if cmd.startswith('LD_LIBRARY_PATH='):
            _cmd.remove(cmd)
            continue
        if cmd.startswith('--proto-output-file='):
            _cmd.remove(cmd)
            continue
        if cmd.startswith('--log-root-path'):
            _cmd.remove(cmd)
            continue
        if _BUILD_CMD in cmd:
            _cmd.remove(cmd)
            _cmd.append(os.path.join('./', _BUILD_CMD))
            continue
    return _cmd

def _are_identical_cmds(current_cmds, former_cmds):
    """Tell two commands are identical.

    Args:
        current_cmds: A list of strings for running input tests.
        former_cmds: A list of strings recorded from the previous run.

    Returns:
        True if both commands are identical, False otherwise.
    """
    # Always sort cmd list to make it comparable.
    current_cmds.sort()
    former_cmds.sort()
    return current_cmds == former_cmds

def _get_hashed_file_name(main_file_name):
    """Convert the input string to a md5-hashed string. If file_extension is
       given, returns $(hashed_string).$(file_extension), otherwise
       $(hashed_string).cache.

    Args:
        main_file_name: The input string need to be hashed.

    Returns:
        A string as hashed file name with .cache file extension.
    """
    hashed_fn = hashlib.md5(str(main_file_name).encode())
    hashed_name = hashed_fn.hexdigest()
    return hashed_name + '.cache'

def md5sum(filename):
    """Generate MD5 checksum of a file.

    Args:
        name: A string of a filename.

    Returns:
        A string of hashed MD5 checksum.
    """
    filename = Path(filename)
    if not filename.is_file():
        return ""
    with open(filename, 'rb') as target:
        content = target.read()
    if not isinstance(content, bytes):
        content = content.encode('utf-8')
    return hashlib.md5(content).hexdigest()

def check_md5(check_file, missing_ok=False):
    """Method equivalent to 'md5sum --check /file/to/check'.

    Args:
        check_file: A string of filename that stores filename and its
                   md5 checksum.
        missing_ok: A boolean that considers OK even when the check_file does
                    not exist. Using missing_ok=True allows ignoring md5 check
                    especially for initial run that the check_file has not yet
                    generated. Using missing_ok=False ensures the consistency of
                    files, and guarantees the process is successfully completed.

    Returns:
        When missing_ok is True (soft check):
          - True if the checksum is consistent with the actual MD5, even the
            check_file is missing or not a valid JSON.
          - False when the checksum is inconsistent with the actual MD5.
        When missing_ok is False (ensure the process completed properly):
          - True if the checksum is consistent with the actual MD5.
          - False otherwise.
    """
    if not Path(check_file).is_file():
        if not missing_ok:
            logging.debug(
                'Unable to verify: %s not found.', check_file)
        return missing_ok
    content = load_json_safely(check_file)
    if content:
        for filename, md5 in content.items():
            if md5sum(filename) != md5:
                logging.debug('%s has altered.', filename)
                return False
        return True
    return False

def save_md5(filenames, save_file):
    """Method equivalent to 'md5sum file1 file2 > /file/to/check'

    Args:
        filenames: A list of filenames.
        save_file: Filename for storing files and their md5 checksums.
    """
    data = {}
    for f in filenames:
        name = Path(f)
        if not name.is_file():
            logging.warning(' ignore %s: not a file.', name)
        data.update({str(name): md5sum(name)})
    with open(save_file, 'w+', encoding='utf-8') as _file:
        json.dump(data, _file)

def get_cache_root():
    """Get the root path dir for cache.

    Use branch and target information as cache_root.
    The path will look like ~/.atest/info_cache/$hash(branch+target)

    Returns:
        A string of the path of the root dir of cache.
    """
    manifest_branch = get_manifest_branch()
    if not manifest_branch:
        manifest_branch = os.environ.get(
            constants.ANDROID_BUILD_TOP, constants.ANDROID_BUILD_TOP)
    # target
    build_target = os.path.basename(
        os.environ.get(constants.ANDROID_PRODUCT_OUT,
                       constants.ANDROID_PRODUCT_OUT))
    branch_target_hash = hashlib.md5(
        (constants.MODE + manifest_branch + build_target).encode()).hexdigest()
    return os.path.join(get_misc_dir(), '.atest', 'info_cache',
                        branch_target_hash[:8])

def get_test_info_cache_path(test_reference, cache_root=None):
    """Get the cache path of the desired test_infos.

    Args:
        test_reference: A string of the test.
        cache_root: Folder path where stores caches.

    Returns:
        A string of the path of test_info cache.
    """
    if not cache_root:
        cache_root = get_cache_root()
    return os.path.join(cache_root, _get_hashed_file_name(test_reference))

def update_test_info_cache(test_reference, test_infos,
                           cache_root=None):
    """Update cache content which stores a set of test_info objects through
       pickle module, each test_reference will be saved as a cache file.

    Args:
        test_reference: A string referencing a test.
        test_infos: A set of TestInfos.
        cache_root: Folder path for saving caches.
    """
    if not cache_root:
        cache_root = get_cache_root()
    if not os.path.isdir(cache_root):
        os.makedirs(cache_root)
    cache_path = get_test_info_cache_path(test_reference, cache_root)
    # Save test_info to files.
    try:
        with open(cache_path, 'wb') as test_info_cache_file:
            logging.debug('Saving cache %s.', cache_path)
            pickle.dump(test_infos, test_info_cache_file, protocol=2)
    except (pickle.PicklingError, TypeError, IOError) as err:
        # Won't break anything, just log this error, and collect the exception
        # by metrics.
        logging.debug('Exception raised: %s', err)
        metrics_utils.handle_exc_and_send_exit_event(
            constants.ACCESS_CACHE_FAILURE)


def load_test_info_cache(test_reference, cache_root=None):
    """Load cache by test_reference to a set of test_infos object.

    Args:
        test_reference: A string referencing a test.
        cache_root: Folder path for finding caches.

    Returns:
        A list of TestInfo namedtuple if cache found, else None.
    """
    if not cache_root:
        cache_root = get_cache_root()
    cache_file = get_test_info_cache_path(test_reference, cache_root)
    if os.path.isfile(cache_file):
        logging.debug('Loading cache %s.', cache_file)
        try:
            with open(cache_file, 'rb') as config_dictionary_file:
                return pickle.load(config_dictionary_file, encoding='utf-8')
        except (pickle.UnpicklingError,
                ValueError,
                TypeError,
                EOFError,
                IOError,
                ImportError) as err:
            # Won't break anything, just remove the old cache, log this error,
            # and collect the exception by metrics.
            logging.debug('Exception raised: %s', err)
            os.remove(cache_file)
            metrics_utils.handle_exc_and_send_exit_event(
                constants.ACCESS_CACHE_FAILURE)
    return None

def clean_test_info_caches(tests, cache_root=None):
    """Clean caches of input tests.

    Args:
        tests: A list of test references.
        cache_root: Folder path for finding caches.
    """
    if not cache_root:
        cache_root = get_cache_root()
    for test in tests:
        cache_file = get_test_info_cache_path(test, cache_root)
        if os.path.isfile(cache_file):
            logging.debug('Removing cache: %s', cache_file)
            try:
                os.remove(cache_file)
            except IOError as err:
                logging.debug('Exception raised: %s', err)
                metrics_utils.handle_exc_and_send_exit_event(
                    constants.ACCESS_CACHE_FAILURE)

def get_modified_files(root_dir):
    """Get the git modified files. The git path here is git top level of
    the root_dir. It's inevitable to utilise different commands to fulfill
    2 scenario:
        1. locate unstaged/staged files
        2. locate committed files but not yet merged.
    the 'git_status_cmd' fulfils the former while the 'find_modified_files'
    fulfils the latter.

    Args:
        root_dir: the root where it starts finding.

    Returns:
        A set of modified files altered since last commit.
    """
    modified_files = set()
    try:
        find_git_cmd = 'cd {}; git rev-parse --show-toplevel'.format(root_dir)
        git_paths = subprocess.check_output(
            find_git_cmd, shell=True).decode().splitlines()
        for git_path in git_paths:
            # Find modified files from git working tree status.
            git_status_cmd = ("repo forall {} -c git status --short | "
                              "awk '{{print $NF}}'").format(git_path)
            modified_wo_commit = subprocess.check_output(
                git_status_cmd, shell=True).decode().rstrip().splitlines()
            for change in modified_wo_commit:
                modified_files.add(
                    os.path.normpath('{}/{}'.format(git_path, change)))
            # Find modified files that are committed but not yet merged.
            find_modified_files = _FIND_MODIFIED_FILES_CMDS.format(git_path)
            commit_modified_files = subprocess.check_output(
                find_modified_files, shell=True).decode().splitlines()
            for line in commit_modified_files:
                modified_files.add(os.path.normpath('{}/{}'.format(
                    git_path, line)))
    except (OSError, subprocess.CalledProcessError) as err:
        logging.debug('Exception raised: %s', err)
    return modified_files

def delimiter(char, length=_DEFAULT_TERMINAL_WIDTH, prenl=0, postnl=0):
    """A handy delimiter printer.

    Args:
        char: A string used for delimiter.
        length: An integer for the replication.
        prenl: An integer that insert '\n' before delimiter.
        postnl: An integer that insert '\n' after delimiter.

    Returns:
        A string of delimiter.
    """
    return prenl * '\n' + char * length + postnl * '\n'

def find_files(path, file_name=constants.TEST_MAPPING):
    """Find all files with given name under the given path.

    Args:
        path: A string of path in source.
        file_name: The file name pattern for finding matched files.

    Returns:
        A list of paths of the files with the matching name under the given
        path.
    """
    match_files = []
    for root, _, filenames in os.walk(path):
        try:
            for filename in fnmatch.filter(filenames, file_name):
                match_files.append(os.path.join(root, filename))
        except re.error as e:
            msg = "Unable to locate %s among %s" % (file_name, filenames)
            logging.debug(msg)
            logging.debug("Exception: %s", e)
            metrics.AtestExitEvent(
                duration=metrics_utils.convert_duration(0),
                exit_code=ExitCode.COLLECT_ONLY_FILE_NOT_FOUND,
                stacktrace=msg,
                logs=str(e))
    return match_files

def extract_zip_text(zip_path):
    """Extract the text files content for input zip file.

    Args:
        zip_path: The file path of zip.

    Returns:
        The string in input zip file.
    """
    content = ''
    try:
        with zipfile.ZipFile(zip_path) as zip_file:
            for filename in zip_file.namelist():
                if os.path.isdir(filename):
                    continue
                # Force change line if multiple text files in zip
                content = content + '\n'
                # read the file
                with zip_file.open(filename) as extract_file:
                    for line in extract_file:
                        if matched_tf_error_log(line.decode()):
                            content = content + line.decode()
    except zipfile.BadZipfile as err:
        logging.debug('Exception raised: %s', err)
    return content

def matched_tf_error_log(content):
    """Check if the input content matched tradefed log pattern.
    The format will look like this.
    05-25 17:37:04 W/XXXXXX
    05-25 17:37:04 E/XXXXXX

    Args:
        content: Log string.

    Returns:
        True if the content matches the regular expression for tradefed error or
        warning log.
    """
    reg = ('^((0[1-9])|(1[0-2]))-((0[1-9])|([12][0-9])|(3[0-1])) '
           '(([0-1][0-9])|([2][0-3])):([0-5][0-9]):([0-5][0-9]) (E|W/)')
    if re.search(reg, content):
        return True
    return False

def has_valid_cert():
    """Check whether the certificate is valid.

    Returns: True if the cert is valid.
    """
    if not constants.CERT_STATUS_CMD:
        return False
    try:
        return (not subprocess.check_call(constants.CERT_STATUS_CMD,
                                          stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL))
    except subprocess.CalledProcessError:
        return False

# pylint: disable=too-many-locals
def get_flakes(branch='',
               target='',
               test_name='',
               test_module='',
               test_method=''):
    """Get flake information.

    Args:
        branch: A string of branch name.
        target: A string of target.
        test_name: A string of test suite name.
        test_module: A string of test module.
        test_method: A string of test method.

    Returns:
        A dictionary of flake info. None if no flakes service exists.
    """
    if not branch:
        branch = constants.FLAKE_BRANCH
    if not target:
        target = constants.FLAKE_TARGET
    if not test_name:
        test_name = constants.FLAKE_TEST_NAME
    # Currently lock the flake information from test-mapping test
    # which only runs on cuttlefish(x86) devices.
    # TODO: extend supporting other devices
    if test_module:
        test_module = 'x86 {}'.format(test_module)
    flake_service = os.path.join(constants.FLAKE_SERVICE_PATH,
                                 constants.FLAKE_FILE)
    if not os.path.exists(flake_service):
        logging.debug('Get flakes: Flake service path not exist.')
        # Send (3, 0) to present no flakes info because service does not exist.
        metrics.LocalDetectEvent(
            detect_type=DetectType.NO_FLAKE, result=0)
        return None
    if not has_valid_cert():
        logging.debug('Get flakes: No valid cert.')
        # Send (3, 1) to present no flakes info because no valid cert.
        metrics.LocalDetectEvent(
            detect_type=DetectType.NO_FLAKE, result=1)
        return None
    flake_info = {}
    start = time.time()
    try:
        shutil.copy2(flake_service, constants.FLAKE_TMP_PATH)
        tmp_service = os.path.join(constants.FLAKE_TMP_PATH,
                                   constants.FLAKE_FILE)
        os.chmod(tmp_service, 0o0755)
        cmd = [tmp_service, branch, target, test_name, test_module, test_method]
        logging.debug('Executing: %s', ' '.join(cmd))
        output = subprocess.check_output(cmd).decode()
        percent_template = "{}:".format(constants.FLAKE_PERCENT)
        postsubmit_template = "{}:".format(constants.FLAKE_POSTSUBMIT)
        for line in output.splitlines():
            if line.startswith(percent_template):
                flake_info[constants.FLAKE_PERCENT] = line.replace(
                    percent_template, '')
            if line.startswith(postsubmit_template):
                flake_info[constants.FLAKE_POSTSUBMIT] = line.replace(
                    postsubmit_template, '')
    # pylint: disable=broad-except
    except Exception as e:
        logging.debug('Exception:%s', e)
        return None
    # Send (4, time) to present having flakes info and it spent time.
    duration = round(time.time()-start)
    logging.debug('Took %ss to get flakes info', duration)
    metrics.LocalDetectEvent(
        detect_type=DetectType.HAS_FLAKE,
        result=duration)
    return flake_info

def read_test_record(path):
    """A Helper to read test record proto.

    Args:
        path: The proto file path.

    Returns:
        The test_record proto instance.
    """
    with open(path, 'rb') as proto_file:
        msg = test_record_pb2.TestRecord()
        msg.ParseFromString(proto_file.read())
    return msg

def has_python_module(module_name):
    """Detect if the module can be loaded without importing it in real.

    Args:
        cmd: A string of the tested module name.

    Returns:
        True if found, False otherwise.
    """
    return bool(importlib.util.find_spec(module_name))

def load_json_safely(jsonfile):
    """Load the given json file as an object.

    Args:
        jsonfile: The json file path.

    Returns:
        The content of the give json file. Null dict when:
        1. the given path doesn't exist.
        2. the given path is not a json or invalid format.
    """
    if isinstance(jsonfile, bytes):
        jsonfile = jsonfile.decode('utf-8')
    if Path(jsonfile).is_file():
        try:
            with open(jsonfile, 'r', encoding='utf-8') as cache:
                return json.load(cache)
        except json.JSONDecodeError:
            logging.debug('Exception happened while loading %s.', jsonfile)
    else:
        logging.debug('%s: File not found.', jsonfile)
    return {}

def get_atest_version():
    """Get atest version.

    Returns:
        Version string from the VERSION file, e.g. prebuilt
            2022-11-24_9314547  (<release_date>_<build_id>)

        If VERSION does not exist (src or local built):
            2022-11-24_5d448c50 (<commit_date>_<commit_id>)

        If the git command fails for unexpected reason:
            2022-11-24_unknown  (<today_date>_unknown)
    """
    atest_dir = Path(__file__).resolve().parent
    version_file = atest_dir.joinpath('VERSION')
    if Path(version_file).is_file():
        return open(version_file, encoding='utf-8').read()

    # Try fetching commit date (%ci) and commit hash (%h).
    git_cmd = 'git log -1 --pretty=format:"%ci;%h"'
    try:
        # commit date/hash are only available when running from the source
        # and the local built.
        result = subprocess.run(
            git_cmd, shell=True, check=False, capture_output=True,
            cwd=Path(
                os.getenv(constants.ANDROID_BUILD_TOP), '').joinpath(
                    'tools/asuite/atest'))
        if result.stderr:
            raise subprocess.CalledProcessError(
                returncode=0, cmd=git_cmd)
        raw_date, commit = result.stdout.decode().split(';')
        date = datetime.datetime.strptime(raw_date,
                                          '%Y-%m-%d %H:%M:%S %z').date()
    # atest_dir doesn't exist will throw FileNotFoundError.
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Use today as the commit date for unexpected conditions.
        date = datetime.datetime.today().date()
        commit = 'unknown'
    return f'{date}_{commit}'

def get_manifest_branch(show_aosp=False):
    """Get the manifest branch.

         (portal xml)                            (default xml)
    +--------------------+ _get_include() +-----------------------------+
    | .repo/manifest.xml |--------------->| .repo/manifests/default.xml |
    +--------------------+                +---------------+-------------+
                             <default revision="master" |
                                      remote="aosp"     | _get_revision()
                                      sync-j="4"/>      V
                                                    +--------+
                                                    | master |
                                                    +--------+

    Args:
        show_aosp: A boolean that shows 'aosp' prefix by checking the 'remote'
                   attribute.

    Returns:
        The value of 'revision' of the included xml or default.xml.

        None when no ANDROID_BUILD_TOP or unable to access default.xml.
    """
    build_top = os.getenv(constants.ANDROID_BUILD_TOP)
    if not build_top:
        return None
    portal_xml = Path(build_top).joinpath('.repo', 'manifest.xml')
    default_xml = Path(build_top).joinpath('.repo/manifests', 'default.xml')
    def _get_revision(xml):
        try:
            xml_root = ET.parse(xml).getroot()
        except (IOError, OSError, ET.ParseError):
            # TODO(b/274989179) Change back to warning once warning if not going
            # to be treat as test failure. Or test_get_manifest_branch unit test
            # could be fix if return None if portal_xml or default_xml not
            # exist.
            logging.info('%s could not be read.', xml)
            return ''
        default_tags = xml_root.findall('./default')
        if default_tags:
            prefix = ''
            for tag in default_tags:
                branch = tag.attrib.get('revision')
                if show_aosp and tag.attrib.get('remote') == 'aosp':
                    prefix = 'aosp-'
                return f'{prefix}{branch}'
        return ''
    def _get_include(xml):
        try:
            xml_root = ET.parse(xml).getroot()
        except (IOError, OSError, ET.ParseError):
            # TODO(b/274989179) Change back to warning once warning if not going
            # to be treat as test failure. Or test_get_manifest_branch unit test
            # could be fix if return None if portal_xml or default_xml not
            # exist.
            logging.info('%s could not be read.', xml)
            return Path()
        include_tags = xml_root.findall('./include')
        if include_tags:
            for tag in include_tags:
                name = tag.attrib.get('name')
                if name:
                    return Path(build_top).joinpath('.repo/manifests', name)
        return default_xml

    # 1. Try getting revision from .repo/manifests/default.xml
    if default_xml.is_file():
        return _get_revision(default_xml)
    # 2. Try getting revision from the included xml of .repo/manifest.xml
    include_xml = _get_include(portal_xml)
    if include_xml.is_file():
        return _get_revision(include_xml)
    # 3. Try getting revision directly from manifest.xml (unlikely to happen)
    return _get_revision(portal_xml)

def get_build_target():
    """Get the build target form system environment TARGET_PRODUCT."""
    build_target = '%s-%s' % (
        os.getenv(constants.ANDROID_TARGET_PRODUCT, None),
        os.getenv(constants.TARGET_BUILD_VARIANT, None))
    return build_target

def build_module_info_target(module_info_target):
    """Build module-info.json after deleting the original one.

    Args:
        module_info_target: the target name that soong is going to build.
    """
    module_file = 'module-info.json'
    logging.debug('Generating %s - this is required for '
                  'initial runs or forced rebuilds.', module_file)
    build_start = time.time()
    product_out = os.getenv(constants.ANDROID_PRODUCT_OUT, None)
    module_info_path = Path(product_out).joinpath('module-info.json')
    if module_info_path.is_file():
        os.remove(module_info_path)
    if not build([module_info_target]):
        sys.exit(ExitCode.BUILD_FAILURE)
    build_duration = time.time() - build_start
    metrics.LocalDetectEvent(
        detect_type=DetectType.ONLY_BUILD_MODULE_INFO,
        result=int(build_duration))

def has_wildcard(test_name):
    """ Tell whether the test_name(either a list or string) contains wildcard
    symbols.

    Args:
        test_name: A list or a str.

    Return:
        True if test_name contains wildcard, False otherwise.
    """
    if isinstance(test_name, str):
        return any(char in test_name for char in _WILDCARD_CHARS)
    if isinstance(test_name, list):
        for name in test_name:
            if has_wildcard(name):
                return True
    return False

def is_build_file(path):
    """ If input file is one of an android build file.

    Args:
        path: A string of file path.

    Return:
        True if path is android build file, False otherwise.
    """
    return bool(os.path.splitext(path)[-1] in _ANDROID_BUILD_EXT)

def quote(input_str):
    """ If the input string -- especially in custom args -- contains shell-aware
    characters, insert a pair of "\" to the input string.

    e.g. unit(test|testing|testing) -> 'unit(test|testing|testing)'

    Args:
        input_str: A string from user input.

    Returns: A string with single quotes if regex chars were detected.
    """
    if has_chars(input_str, _REGEX_CHARS):
        return "\'" + input_str + "\'"
    return input_str

def has_chars(input_str, chars):
    """ Check if the input string contains one of the designated characters.

    Args:
        input_str: A string from user input.
        chars: An iterable object.

    Returns:
        True if the input string contains one of the special chars.
    """
    for char in chars:
        if char in input_str:
            return True
    return False

def prompt_with_yn_result(msg, default=True):
    """Prompt message and get yes or no result.

    Args:
        msg: The question you want asking.
        default: boolean to True/Yes or False/No
    Returns:
        default value if get KeyboardInterrupt or ValueError exception.
    """
    suffix = '[Y/n]: ' if default else '[y/N]: '
    try:
        return strtobool(input(msg+suffix))
    except (ValueError, KeyboardInterrupt):
        return default

def strtobool(val):
    """Convert a string representation of truth to True or False.

    Args:
        val: a string of input value.

    Returns:
        True when values are 'y', 'yes', 't', 'true', 'on', and '1';
        False when 'n', 'no', 'f', 'false', 'off', and '0'.
        Raises ValueError if 'val' is anything else.
    """
    if val.lower() in ('y', 'yes', 't', 'true', 'on', '1'):
        return True
    if val.lower() in ('n', 'no', 'f', 'false', 'off', '0'):
        return False
    raise ValueError("invalid truth value %r" % (val,))

def get_android_junit_config_filters(test_config):
    """Get the dictionary of a input config for junit config's filters

    Args:
        test_config: The path of the test config.
    Returns:
        A dictionary include all the filters in the input config.
    """
    filter_dict = {}
    xml_root = ET.parse(test_config).getroot()
    option_tags = xml_root.findall('.//option')
    for tag in option_tags:
        name = tag.attrib['name'].strip()
        if name in constants.SUPPORTED_FILTERS:
            filter_values = filter_dict.get(name, [])
            value = tag.attrib['value'].strip()
            filter_values.append(value)
            filter_dict.update({name: filter_values})
    return filter_dict

def get_config_parameter(test_config):
    """Get all the parameter values for the input config

    Args:
        test_config: The path of the test config.
    Returns:
        A set include all the parameters of the input config.
    """
    parameters = set()
    xml_root = ET.parse(test_config).getroot()
    option_tags = xml_root.findall('.//option')
    for tag in option_tags:
        name = tag.attrib['name'].strip()
        if name == constants.CONFIG_DESCRIPTOR:
            key = tag.attrib['key'].strip()
            if key == constants.PARAMETER_KEY:
                value = tag.attrib['value'].strip()
                parameters.add(value)
    return parameters

def get_config_device(test_config):
    """Get all the device names from the input config

    Args:
        test_config: The path of the test config.
    Returns:
        A set include all the device name of the input config.
    """
    devices = set()
    try:
        xml_root = ET.parse(test_config).getroot()
        device_tags = xml_root.findall('.//device')
        for tag in device_tags:
            name = tag.attrib['name'].strip()
            devices.add(name)
    except ET.ParseError as e:
        colorful_print('Config has invalid format.', constants.RED)
        colorful_print('File %s : %s' % (test_config, str(e)), constants.YELLOW)
        sys.exit(ExitCode.CONFIG_INVALID_FORMAT)
    return devices

def get_mainline_param(test_config):
    """Get all the mainline-param values for the input config

    Args:
        test_config: The path of the test config.
    Returns:
        A set include all the parameters of the input config.
    """
    mainline_param = set()
    xml_root = ET.parse(test_config).getroot()
    option_tags = xml_root.findall('.//option')
    for tag in option_tags:
        name = tag.attrib['name'].strip()
        if name == constants.CONFIG_DESCRIPTOR:
            key = tag.attrib['key'].strip()
            if key == constants.MAINLINE_PARAM_KEY:
                value = tag.attrib['value'].strip()
                mainline_param.add(value)
    return mainline_param

def get_adb_devices():
    """Run `adb devices` and return a list of devices.

    Returns:
        A list of devices. e.g.
        ['127.0.0.1:40623', '127.0.0.1:40625']
    """
    probe_cmd = "adb devices | egrep -v \"^List|^$\"||true"
    suts = subprocess.check_output(probe_cmd, shell=True).decode().splitlines()
    return [sut.split('\t')[0] for sut in suts]

def get_android_config():
    """Get Android config as "printconfig" shows.

    Returns:
        A dict of Android configurations.
    """
    dump_cmd = get_build_cmd(dump=True)
    raw_config = subprocess.check_output(dump_cmd).decode('utf-8')
    android_config = {}
    for element in raw_config.splitlines():
        if not element.startswith('='):
            key, value = tuple(element.split('=', 1))
            android_config.setdefault(key, value)
    return android_config

def get_config_gtest_args(test_config):
    """Get gtest's module-name and device-path option from the input config

    Args:
        test_config: The path of the test config.
    Returns:
        A string of gtest's module name.
        A string of gtest's device path.
    """
    module_name = ''
    device_path = ''
    xml_root = ET.parse(test_config).getroot()
    option_tags = xml_root.findall('.//option')
    for tag in option_tags:
        name = tag.attrib['name'].strip()
        value = tag.attrib['value'].strip()
        if name == 'native-test-device-path':
            device_path = value
        elif name == 'module-name':
            module_name = value
    return module_name, device_path

def get_arch_name(module_name, is_64=False):
    """Get the arch folder name for the input module.

        Scan the test case folders to get the matched arch folder name.

        Args:
            module_name: The module_name of test
            is_64: If need 64 bit arch name, False otherwise.
        Returns:
            A string of the arch name.
    """
    arch_32 = ['arm', 'x86']
    arch_64 = ['arm64', 'x86_64']
    arch_list = arch_32
    if is_64:
        arch_list = arch_64
    test_case_root = os.path.join(
        os.environ.get(constants.ANDROID_TARGET_OUT_TESTCASES, ''),
        module_name
    )
    if not os.path.isdir(test_case_root):
        logging.debug('%s does not exist.', test_case_root)
        return ''
    for f in os.listdir(test_case_root):
        if f in arch_list:
            return f
    return ''

def copy_single_arch_native_symbols(
    symbol_root, module_name, device_path, is_64=False):
    """Copy symbol files for native tests which belong to input arch.

        Args:
            module_name: The module_name of test
            device_path: The device path define in test config.
            is_64: True if need to copy 64bit symbols, False otherwise.
    """
    src_symbol = os.path.join(symbol_root, 'data', 'nativetest', module_name)
    if is_64:
        src_symbol = os.path.join(
            symbol_root, 'data', 'nativetest64', module_name)
    dst_symbol = os.path.join(
        symbol_root, device_path[1:], module_name,
        get_arch_name(module_name, is_64))
    if os.path.isdir(src_symbol):
        # TODO: Use shutil.copytree(src, dst, dirs_exist_ok=True) after
        #  python3.8
        if os.path.isdir(dst_symbol):
            shutil.rmtree(dst_symbol)
        shutil.copytree(src_symbol, dst_symbol)

def copy_native_symbols(module_name, device_path):
    """Copy symbol files for native tests to match with tradefed file structure.

    The original symbols will locate at
    $(PRODUCT_OUT)/symbols/data/nativetest(64)/$(module)/$(stem).
    From TF, the test binary will locate at
    /data/local/tmp/$(module)/$(arch)/$(stem).
    In order to make trace work need to copy the original symbol to
    $(PRODUCT_OUT)/symbols/data/local/tmp/$(module)/$(arch)/$(stem)

    Args:
        module_name: The module_name of test
        device_path: The device path define in test config.
    """
    symbol_root = os.path.join(
        os.environ.get(constants.ANDROID_PRODUCT_OUT, ''),
        'symbols')
    if not os.path.isdir(symbol_root):
        logging.debug('Symbol dir:%s not exist, skip copy symbols.',
                      symbol_root)
        return
    # Copy 32 bit symbols
    if get_arch_name(module_name, is_64=False):
        copy_single_arch_native_symbols(
            symbol_root, module_name, device_path, is_64=False)
    # Copy 64 bit symbols
    if get_arch_name(module_name, is_64=True):
        copy_single_arch_native_symbols(
            symbol_root, module_name, device_path, is_64=True)

def get_config_preparer_options(test_config, class_name):
    """Get all the parameter values for the input config

    Args:
        test_config: The path of the test config.
        class_name: A string of target_preparer
    Returns:
        A set include all the parameters of the input config.
    """
    options = {}
    xml_root = ET.parse(test_config).getroot()
    option_tags = xml_root.findall(
        './/target_preparer[@class="%s"]/option' % class_name)
    for tag in option_tags:
        name = tag.attrib['name'].strip()
        value = tag.attrib['value'].strip()
        options[name] = value
    return options


def get_verify_key(tests, extra_args):
    """Compose test command key.

    Args:
        test_name: A list of input tests.
        extra_args: Dict of extra args to add to test run.
    Returns:
        A composed test commands.
    """
    # test_commands is a concatenated string of sorted test_ref+extra_args.
    # For example, "ITERATIONS=5 hello_world_test"
    test_commands = tests
    for key, value in extra_args.items():
        if key not in constants.SKIP_VARS:
            test_commands.append('%s=%s' % (key, str(value)))
    test_commands.sort()
    return ' '.join(test_commands)

def gen_runner_cmd_to_file(tests, dry_run_cmd,
                           result_path=constants.RUNNER_COMMAND_PATH):
    """Generate test command and save to file.

    Args:
        tests: A String of input tests.
        dry_run_cmd: A String of dry run command.
        result_path: A file path for saving result.
    Returns:
        A composed run commands.
    """
    normalized_cmd = dry_run_cmd
    root_path = os.environ.get(constants.ANDROID_BUILD_TOP)
    if root_path in dry_run_cmd:
        normalized_cmd = dry_run_cmd.replace(root_path,
                                             f"${constants.ANDROID_BUILD_TOP}")
    results = load_json_safely(result_path)
    if results.get(tests) != normalized_cmd:
        results[tests] = normalized_cmd
    with open(result_path, 'w+', encoding='utf-8') as _file:
        json.dump(results, _file, indent=0)
    return results.get(tests, '')


def handle_test_env_var(input_test, result_path=constants.VERIFY_ENV_PATH,
                        pre_verify=False):
    """Handle the environment variable of input tests.

    Args:
        input_test: A string of input tests pass to atest.
        result_path: The file path for saving result.
        pre_verify: A booloan to separate into pre-verify and actually verify.
    Returns:
        0 is no variable needs to verify, 1 has some variables to next verify.
    """
    full_result_content = load_json_safely(result_path)
    demand_env_vars = []
    demand_env_vars = full_result_content.get(input_test)
    if demand_env_vars is None:
        raise atest_error.DryRunVerificationError(
            '{}: No verify key.'.format(input_test))
    # No mapping variables.
    if demand_env_vars == []:
        return 0
    if pre_verify:
        return 1
    verify_error = []
    for env in demand_env_vars:
        if '=' in env:
            key, value = env.split('=', 1)
            env_value = os.environ.get(key, None)
            if env_value is None or env_value != value:
                verify_error.append('Environ verification failed, ({0},{1})!='
                    '({0},{2})'.format(key, value, env_value))
        else:
            if not os.environ.get(env, None):
                verify_error.append('Missing environ:{}'.format(env))
    if verify_error:
        raise atest_error.DryRunVerificationError('\n'.join(verify_error))
    return 1

def save_build_files_timestamp():
    """ Method that generate timestamp of Android.{bp,mk} files.

    The checksum of build files are stores in
        $ANDROID_HOST_OUT/indexes/buildfiles.stp
    """
    index_dir = get_host_out('indexes')
    plocate_db = index_dir.joinpath(constants.LOCATE_CACHE)

    if plocate_db.is_file():
        cmd = (f'locate -d{plocate_db} --existing '
               r'--regex "/Android\.(bp|mk)$"')
        results = subprocess.getoutput(cmd)
        if results:
            timestamp = {}
            for build_file in results.splitlines():
                timestamp.update({build_file: Path(build_file).stat().st_mtime})

            checksum_file = index_dir.joinpath(constants.BUILDFILES_STP)
            with open(checksum_file, 'w', encoding='utf-8') as _file:
                json.dump(timestamp, _file)


def run_multi_proc(func, *args, **kwargs):
    """Start a process with multiprocessing and return Process object.

    Args:
        func: A string of function name which will be the target name.
        args/kwargs: check doc page:
        https://docs.python.org/3.8/library/multiprocessing.html#process-and-exceptions

    Returns:
        multiprocessing.Process object.
    """
    proc = Process(target=func, *args, **kwargs)
    proc.start()
    return proc

def get_prebuilt_sdk_tools_dir():
    """Get the path for the prebuilt sdk tools root dir.

    Returns: The absolute path of prebuilt sdk tools directory.
    """
    build_top = Path(os.environ.get(constants.ANDROID_BUILD_TOP, ''))
    return build_top.joinpath(
        'prebuilts/sdk/tools/', str(platform.system()).lower(), 'bin')


def is_writable(path):
    """Check if the given path is writable.

    Returns: True if input path is writable, False otherwise.
    """
    if not os.path.exists(path):
        return is_writable(os.path.dirname(path))
    return os.access(path, os.W_OK)


def get_misc_dir():
    """Get the path for the ATest data root dir.

    Returns: The absolute path of the ATest data root dir.
    """
    home_dir = os.path.expanduser('~')
    if is_writable(home_dir):
        return home_dir
    return get_build_out_dir()

def get_full_annotation_class_name(module_info, class_name):
    """ Get fully qualified class name from a class name.

    If the given keyword(class_name) is "smalltest", this method can search
    among source codes and grep the accurate annotation class name:

        android.test.suitebuilder.annotation.SmallTest

    Args:
        module_info: A dict of module_info.
        class_name: A string of class name.

    Returns:
        A string of fully qualified class name, empty string otherwise.
    """
    fullname_re = re.compile(
        r'import\s+(?P<fqcn>{})(|;)$'.format(class_name), re.I)
    keyword_re = re.compile(
        r'import\s+(?P<fqcn>.*\.{})(|;)$'.format(class_name), re.I)
    build_top = Path(os.environ.get(constants.ANDROID_BUILD_TOP, ''))
    for f in module_info.get(constants.MODULE_SRCS, []):
        full_path = build_top.joinpath(f)
        with open(full_path, 'r', encoding='utf-8') as cache:
            for line in cache.readlines():
                # Accept full class name.
                match = fullname_re.match(line)
                if match:
                    return match.group('fqcn')
                # Search annotation class from keyword.
                match = keyword_re.match(line)
                if match:
                    return match.group('fqcn')
    return ""

def has_mixed_type_filters(test_infos):
    """ There are different types in a test module.

    Dict test_to_types is mapping module name and the set of types.
    For example,
    {
        'module_1': {'wildcard class_method'},
        'module_2': {'wildcard class_method', 'regular class_method'},
        'module_3': set()
        }

    Args:
        test_infos: A set of TestInfos.

    Returns:
        True if more than one filter type in a test module, False otherwise.
    """
    test_to_types = {}
    for test_info in test_infos:
        filters = test_info.data.get(constants.TI_FILTER, [])
        filter_types = set()
        for flt in filters:
            filter_types |= get_filter_types(flt.to_set_of_tf_strings())
        filter_types |= test_to_types.get(test_info.test_name, set())
        test_to_types[test_info.test_name] = filter_types
    for _, types in test_to_types.items():
        if len(types) > 1:
            return True
    return False

def get_filter_types(tf_filter_set):
    """ Get filter types.

    Args:
        tf_filter_set: A set of tf filter strings.

    Returns:
        A set of FilterType.
    """
    type_set = set()
    for tf_filter in tf_filter_set:
        if _WILDCARD_FILTER_RE.match(tf_filter):
            logging.debug('Filter and type: (%s, %s)',
                          tf_filter, FilterType.WILDCARD_FILTER.value)
            type_set.add(FilterType.WILDCARD_FILTER.value)
        if _REGULAR_FILTER_RE.match(tf_filter):
            logging.debug('Filter and type: (%s, %s)',
                         tf_filter, FilterType.REGULAR_FILTER.value)
            type_set.add(FilterType.REGULAR_FILTER.value)
    return type_set

def has_index_files():
    """Determine whether the essential index files are done.

    (b/206886222) checksum may be different even the src is not changed; so
    the main process needs to wait when the essential index files do not exist.

    Returns:
        False if one of the index file does not exist; True otherwise.
    """
    return all(Path(f).is_file() for f in [
        constants.CLASS_INDEX,
        constants.CC_CLASS_INDEX,
        constants.QCLASS_INDEX,
        constants.PACKAGE_INDEX])

# pylint: disable=anomalous-backslash-in-string,too-many-branches
def get_bp_content(filename: Path, module_type: str) -> Dict:
    """Get essential content info from an Android.bp.
    By specifying module_type (e.g. 'android_test', 'android_app'), this method
    can parse the given starting point and grab 'name', 'instrumentation_for'
    and 'manifest'.

    Returns:
        A dict of mapping test module and target module; e.g.
        {
         'FooUnitTests':
             {'manifest': 'AndroidManifest.xml', 'target_module': 'Foo'},
         'Foo':
             {'manifest': 'AndroidManifest-common.xml', 'target_module': ''}
        }
        Null dict if there is no content of the given module_type.
    """
    build_file = Path(filename)
    if not any((build_file.suffix == '.bp', build_file.is_file())):
        return {}
    start_from = re.compile(f'^{module_type}\s*\{{')
    end_with = re.compile(r'^\}$')
    context_re = re.compile(
        r'\s*(?P<key>(name|manifest|instrumentation_for))\s*:'
        r'\s*\"(?P<value>.*)\"\s*,', re.M)
    with open(build_file, 'r', encoding='utf-8') as cache:
        data = cache.readlines()
    content_dict = {}
    start_recording = False
    for _line in data:
        line = _line.strip()
        if re.match(start_from, line):
            start_recording = True
            _dict = {}
            continue
        if start_recording:
            if not re.match(end_with, line):
                match = re.match(context_re, line)
                if match:
                    _dict.update(
                        {match.group('key'): match.group('value')})
            else:
                start_recording = False
                module_name = _dict.get('name')
                if module_name:
                    content_dict.update(
                        {module_name: {
                            'manifest': _dict.get(
                                'manifest', 'AndroidManifest.xml'),
                            'target_module': _dict.get(
                                'instrumentation_for', '')}
                        })
    return content_dict

def get_manifest_info(manifest: Path) -> Dict[str, Any]:
    """Get the essential info from the given manifest file.
    This method cares only three attributes:
        * package
        * targetPackage
        * persistent
    For an instrumentation test, the result will be like:
    {
        'package': 'com.android.foo.tests.unit',
        'targetPackage': 'com.android.foo',
        'persistent': False
    }
    For a target module of the instrumentation test:
    {
        'package': 'com.android.foo',
        'targetPackage': '',
        'persistent': True
    }
    """
    mdict = {'package': '', 'target_package': '', 'persistent': False}
    try:
        xml_root = ET.parse(manifest).getroot()
    except (ET.ParseError, FileNotFoundError):
        return mdict
    manifest_package_re =  re.compile(r'[a-z][\w]+(\.[\w]+)*')
    # 1. Must probe 'package' name from the top.
    for item in xml_root.findall('.'):
        if 'package' in item.attrib.keys():
            pkg = item.attrib.get('package')
            match = manifest_package_re.match(pkg)
            if match:
                mdict['package'] = pkg
                break
    for item in xml_root.findall('*'):
        # 2. Probe 'targetPackage' in 'instrumentation' tag.
        if item.tag == 'instrumentation':
            for key, value in item.attrib.items():
                if 'targetPackage' in key:
                    mdict['target_package'] = value
                    break
        # 3. Probe 'persistent' in any tags.
        for key, value in item.attrib.items():
            if 'persistent' in key:
                mdict['persistent'] = value.lower() == 'true'
                break
    return mdict

# pylint: disable=broad-except
def generate_print_result_html(result_file: Path):
    """Generate a html that collects all log files."""
    result_file = Path(result_file)
    search_dir = Path(result_file).parent.joinpath('log')
    result_html = Path(search_dir, 'test_logs.html')
    try:
        logs = sorted(find_files(str(search_dir), file_name='*'))
        with open(result_html, 'w', encoding='utf-8') as cache:
            cache.write('<!DOCTYPE html><html><body>')
            result = load_json_safely(result_file)
            if result:
                cache.write(f'<h1>{"atest " + result.get("args")}</h1>')
                timestamp = datetime.datetime.fromtimestamp(
                    result_file.stat().st_ctime)
                cache.write(f'<h2>{timestamp}</h2>')
            for log in logs:
                cache.write(f'<p><a href="{urllib.parse.quote(log)}">'
                            f'{html.escape(Path(log).name)}</a></p>')
            cache.write('</body></html>')
        print(f'\nTo access logs, press "ctrl" and click on\n'
              f'file://{result_html}\n')
    except Exception as e:
        logging.debug('Did not generate log html for reason: %s', e)

# pylint: disable=broad-except
def prompt_suggestions(result_file: Path):
    """Generate suggestions when detecting keywords in logs."""
    result_file = Path(result_file)
    search_dir = Path(result_file).parent.joinpath('log')
    logs = sorted(find_files(str(search_dir), file_name='*'))
    for log in logs:
        for keyword, suggestion in SUGGESTIONS.items():
            try:
                with open(log, 'r', encoding='utf-8') as cache:
                    content = cache.read()
                    if keyword in content:
                        colorful_print(
                            '[Suggestion] ' + suggestion, color=constants.RED)
                        break
            # If the given is not a plain text, just ignore it.
            except Exception:
                pass

# pylint: disable=invalid-name
def get_rbe_and_customized_out_state() -> int:
    """Return decimal state of RBE and customized out.

    Customizing out dir (OUT_DIR/OUT_DIR_COMMON_BASE) dramatically slows down
    the RBE performance; by collecting the combined state of the two states,
    we can profile the performance relationship between RBE and the build time.

       RBE  | out_dir |  decimal
    --------+---------+---------
        0   |    0    |    0
        0   |    1    |    1
        1   |    0    |    2
        1   |    1    |    3    --> Caution for poor performance.

    Returns:
        An integer that describes the combined state.
    """
    ON = '1'
    OFF = '0'
    # 1. ensure RBE is enabled during the build.
    actual_out_dir = Path(get_build_out_dir())
    log_path = actual_out_dir.joinpath('soong.log')
    rbe_enabled = not bool(
        subprocess.call(f'grep -q USE_RBE=true {log_path}'.split())
        )
    rbe_state = ON if rbe_enabled else OFF

    # 2. The customized out path will be different from the regular one.
    regular_out_dir = Path(os.getenv(constants.ANDROID_BUILD_TOP), 'out')
    customized_out = OFF if actual_out_dir == regular_out_dir else ON

    return int(rbe_state + customized_out, 2)


def build_files_integrity_is_ok() -> bool:
    """Return Whether the integrity of build files is OK."""
    # 0. Inexistence of the timestamp file means a fresh repo sync.
    timestamp_file = get_host_out('indexes', constants.BUILDFILES_STP)
    if not timestamp_file.is_file():
        return False
    # 1. Ensure no build files were added/deleted.
    recorded_amount = len(load_json_safely(timestamp_file).keys())
    cmd = (f'locate -d{constants.LOCATE_CACHE} --regex '
            r'"/Android\.(bp|mk)$" | wc -l')
    if int(subprocess.getoutput(cmd)) != recorded_amount:
        return False

    # 2. Ensure the consistency of all build files.
    for file, timestamp in load_json_safely(timestamp_file).items():
        if Path(file).stat().st_mtime != timestamp:
            return False
    return True


def _build_env_profiling() -> BuildEnvProfiler:
    """Determine the status profile before build.

    The BuildEnvProfiler object can help use determine whether a build is:
        1. clean build. (empty out/ dir)
        2. Build files Integrity (Android.bp/Android.mk changes).
        3. Environment variables consistency.
        4. New Ninja file generated. (mtime of soong/build.ninja)

    Returns:
        the BuildProfile object.
    """
    out_dir = Path(get_build_out_dir())
    ninja_file = out_dir.joinpath('soong/build.ninja')
    mtime = ninja_file.stat().st_mtime if ninja_file.is_file() else 0
    variables_file = out_dir.joinpath('soong/soong.environment.used.build')

    return BuildEnvProfiler(
        ninja_file=ninja_file,
        ninja_file_mtime=mtime,
        variable_file=variables_file,
        variable_file_md5=md5sum(variables_file),
        clean_out=not ninja_file.exists(),
        build_files_integrity=build_files_integrity_is_ok()
    )


def _send_build_condition_metrics(
        build_profile: BuildEnvProfiler, cmd: List[str]):
    """Send build conditions by comparing build env profilers."""

    # when build module-info.json only, 'module-info.json' will be
    # the last element.
    m_mod_info_only = 'module-info.json' in cmd.pop()

    def ninja_file_is_changed(env_profiler: BuildEnvProfiler) -> bool:
        """Determine whether the ninja file had been renewal."""
        if not env_profiler.ninja_file.is_file():
            return True
        return (env_profiler.ninja_file.stat().st_mtime !=
                env_profiler.ninja_file_mtime)

    def env_var_is_changed(env_profiler: BuildEnvProfiler) -> bool:
        """Determine whether soong-related variables had changed."""
        return (md5sum(env_profiler.variable_file) !=
                env_profiler.variable_file_md5)

    def send_data(detect_type, value=1):
        """A simple wrapper of metrics.LocalDetectEvent."""
        metrics.LocalDetectEvent(detect_type=detect_type, result=value)

    send_data(DetectType.RBE_STATE, get_rbe_and_customized_out_state())

    # Determine the correct detect type before profiling.
    # (build module-info.json or build dependencies.)
    clean_out = (DetectType.MODULE_INFO_CLEAN_OUT
                 if m_mod_info_only else DetectType.BUILD_CLEAN_OUT)
    ninja_generation = (DetectType.MODULE_INFO_GEN_NINJA
                        if m_mod_info_only else DetectType.BUILD_GEN_NINJA)
    bpmk_change = (DetectType.MODULE_INFO_BPMK_CHANGE
                   if m_mod_info_only else DetectType.BUILD_BPMK_CHANGE)
    env_change = (DetectType.MODULE_INFO_ENV_CHANGE
                  if m_mod_info_only else DetectType.BUILD_ENV_CHANGE)
    src_change = (DetectType.MODULE_INFO_SRC_CHANGE
                  if m_mod_info_only else DetectType.BUILD_SRC_CHANGE)
    other = (DetectType.MODULE_INFO_OTHER
             if m_mod_info_only else DetectType.BUILD_OTHER)
    incremental =(DetectType.MODULE_INFO_INCREMENTAL
                  if m_mod_info_only else DetectType.BUILD_INCREMENTAL)

    if build_profile.clean_out:
        send_data(clean_out)
    else:
        send_data(incremental)

    if ninja_file_is_changed(build_profile):
        send_data(ninja_generation)

    other_condition = True
    if not build_profile.build_files_integrity:
        send_data(bpmk_change)
        other_condition = False
    if env_var_is_changed(build_profile):
        send_data(env_change)
        other_condition = False
    if bool(get_modified_files(os.getcwd())):
        send_data(src_change)
        other_condition = False
    if other_condition:
        send_data(other)


def get_local_auto_shardable_tests():
    """Get the auto shardable test names in shardable file.

    The path will be ~/.atest/auto_shard/local_auto_shardable_tests

    Returns:
        A list of auto shardable test names.
    """
    shardable_tests_file = Path(get_misc_dir()).joinpath(
        '.atest/auto_shard/local_auto_shardable_tests')
    if not shardable_tests_file.exists():
        return []
    return open(shardable_tests_file, 'r', encoding='utf-8').read().split()

def update_shardable_tests(test_name: str, run_time_in_sec: int):
    """Update local_auto_shardable_test file.

    Strategy:
        - Determine to add the module by the run time > 10 mins.
        - local_auto_shardable_test file path :
            ~/.atest/auto_shard/local_auto_shardable_tests
        - The file content template is module name per line:
            <module1>
            <module2>
            ...
    """
    if run_time_in_sec < 600:
        return
    shardable_tests = get_local_auto_shardable_tests()
    if test_name not in shardable_tests:
        shardable_tests.append(test_name)
        logging.info('%s takes %ss (> 600s) to finish. Adding to shardable '
                    'test list.', test_name, run_time_in_sec)

    if not shardable_tests:
        logging.info('No shardable tests to run.')
        return
    shardable_dir = Path(get_misc_dir()).joinpath('.atest/auto_shard')
    shardable_dir.mkdir(parents=True, exist_ok=True)
    shardable_tests_file = shardable_dir.joinpath('local_auto_shardable_tests')
    with open(shardable_tests_file, 'w', encoding='utf-8') as file:
        file.write('\n'.join(shardable_tests))


def contains_brackets(string: str, pair: bool=True) -> bool:
    """
    Determines whether a given string contains (pairs of) brackets.

    Args:
        string: The string to check for brackets.
        pair: Whether to check for brackets in pairs.

    Returns:
        bool: True if the given contains full pair of brackets; False otherwise.
    """
    if not pair:
        return re.search(r"\(|\)|\[|\]|\{|\}", string)

    stack = []
    brackets = {"(": ")", "[": "]", "{": "}"}
    for char in string:
        if char in brackets:
            stack.append(char)
        elif char in brackets.values():
            if not stack or brackets[stack.pop()] != char:
                return False
    return len(stack) == 0
