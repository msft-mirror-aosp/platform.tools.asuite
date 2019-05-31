#!/usr/bin/env python3
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

"""AIDEgen metrics functions."""

import json
import logging
import os
import platform
import subprocess
import sys
import urllib.request
import uuid

from aidegen import constant
from atest import atest_utils

try:
    from asuite.metrics import metrics
    from asuite.metrics import metrics_base
    from asuite.metrics import metrics_utils
except ImportError:
    logging.debug('Import metrics fail, can\'t send metrics')
    metrics = None
    metrics_base = None
    metrics_utils = None

_METRICS_URL = 'http://asuite-218222.appspot.com/aidegen/metrics'
_VALID_DOMAINS = ['google.com', 'android.com']
_COMMAND_GIT_CONFIG = ['git', 'config', '--get', 'user.email']
_JSON_HEADERS = {'Content-Type': 'application/json'}
_METRICS_RESPONSE = b'done'
_DUMMY_UUID = '00000000-0000-4000-8000-000000000000'
_METRICS_TIMEOUT = 2  #seconds
_META_FILE = os.path.join(
    os.path.expanduser('~'), '.config', 'asuite', '.metadata')


def log_usage():
    """Log aidegen run."""
    # Show privacy and license hint message before collect data.
    atest_utils.print_data_collection_notice()
    _log_event(_METRICS_URL, dummy_key_fallback=False, ldap=_get_ldap())


def starts_asuite_metrics():
    """Starts to record metrics data.

    Send a metrics data to log server at the same time.
    """
    if not metrics:
        return
    metrics_base.MetricsBase.tool_name = constant.AIDEGEN_TOOL_NAME
    metrics_utils.get_start_time()
    command = ' '.join(sys.argv)
    metrics.AtestStartEvent(
        command_line=command,
        test_references=[],
        cwd=os.getcwd(),
        os=platform.platform())


def ends_asuite_metrics(exit_code, stacktrace='', logs=''):
    """Send the end event to log server.

    Args:
        exit_code: An integer of exit code.
        stacktrace: A string of stacktrace.
        logs: A string of logs.
    """
    if not metrics_utils:
        return
    metrics_utils.send_exit_event(
        exit_code,
        stacktrace=stacktrace,
        logs=logs)


# pylint: disable=broad-except
def _get_ldap():
    """Return string email username for valid domains only, None otherwise."""
    if not atest_utils.is_external_run():
        aidegen_project = os.path.join(constant.ANDROID_ROOT_PATH, 'tools',
                                       'asuite', 'aidegen')
        email = subprocess.check_output(
            _COMMAND_GIT_CONFIG, cwd=aidegen_project).strip()
        ldap, domain = str(email, encoding="utf-8").split('@', 2)
        if domain in _VALID_DOMAINS:
            return ldap
    return None


# pylint: disable=broad-except
def _log_event(metrics_url, dummy_key_fallback=True, **kwargs):
    """Base log event function for asuite backend.

    Args:
        metrics_url: String, URL to report metrics to.
        dummy_key_fallback: Boolean, If True and unable to get grouping key,
                            use a dummy key otherwise return out. Sometimes we
                            don't want to return metrics for users we are
                            unable to identify. Default True.
        kwargs: Dict, additional fields we want to return metrics for.
    """
    try:
        try:
            key = str(_get_grouping_key())
        except Exception:
            if not dummy_key_fallback:
                return
            key = _DUMMY_UUID
        data = {'grouping_key': key, 'run_id': str(uuid.uuid4())}
        if kwargs:
            data.update(kwargs)
        data = json.dumps(data).encode("utf-8")
        request = urllib.request.Request(
            metrics_url, data=data, headers=_JSON_HEADERS)
        response = urllib.request.urlopen(request, timeout=_METRICS_TIMEOUT)
        content = response.read()
        if content != _METRICS_RESPONSE:
            raise Exception('Unexpected metrics response: %s' % content)
    except Exception:
        logging.exception('Exception sending metrics')


def _get_grouping_key():
    """Get grouping key. Returns UUID.uuid4."""
    if os.path.isfile(_META_FILE):
        with open(_META_FILE) as meta_file:
            try:
                return uuid.UUID(meta_file.read(), version=4)
            except ValueError:
                logging.exception('malformed group_key in file, rewriting')

    key = uuid.uuid4()
    dir_path = os.path.dirname(_META_FILE)
    if os.path.isfile(dir_path):
        os.remove(dir_path)
    try:
        os.makedirs(dir_path)
    except OSError as err:
        if not os.path.isdir(dir_path):
            raise err
    with open(_META_FILE, 'w+') as meta_file:
        meta_file.write(str(key))
    return key
