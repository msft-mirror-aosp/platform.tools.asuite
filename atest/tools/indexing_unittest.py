#!/usr/bin/env python3
#
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

"""Unittest for indexing.py"""

# pylint: disable=line-too-long

import os
import pickle
import subprocess
import unittest

from unittest import mock

from atest import atest_utils as au
from atest import unittest_constants as uc

from atest.tools import indexing

SEARCH_ROOT = uc.TEST_DATA_DIR
PRUNEPATH = uc.TEST_CONFIG_DATA_DIR
LOCATE = indexing.LOCATE
UPDATEDB = indexing.UPDATEDB

class IndexTargetUnittests(unittest.TestCase):
    """"Unittest Class for indexing.py."""

    # TODO: (b/265245404) Re-write test cases with AAA style.
    # TODO: (b/242520851) constants.LOCATE_CACHE should be in literal.
    @mock.patch('atest.constants.INDEX_DIR', uc.INDEX_DIR)
    @mock.patch('atest.constants.LOCATE_CACHE', uc.LOCATE_CACHE)
    @mock.patch('atest.tools.indexing.SEARCH_TOP', uc.TEST_DATA_DIR)
    def test_index_targets(self):
        """Test method index_targets."""
        if au.has_command(UPDATEDB) and au.has_command(LOCATE):
            # 1. Test run_updatedb() is functional.
            indexing.run_updatedb(SEARCH_ROOT, uc.LOCATE_CACHE,
                                     prunepaths=PRUNEPATH)
            # test_config/ is excluded so that a.xml won't be found.
            locate_cmd1 = [LOCATE, '-d', uc.LOCATE_CACHE, '/a.xml']
            # locate returns non-zero when target not found; therefore, use run
            # method and assert stdout only.
            result = subprocess.run(locate_cmd1, check=False,
                                    capture_output=True)
            self.assertEqual(result.stdout.decode(), '')

            # module-info.json can be found in the search_root.
            locate_cmd2 = [LOCATE, '-d', uc.LOCATE_CACHE, 'module-info.json']
            self.assertEqual(subprocess.call(locate_cmd2), 0)

            # 2. Test get_java_result is functional.
            _cache = {}
            jproc = au.run_multi_proc(
                    func=indexing.get_java_result, args=[uc.LOCATE_CACHE],
                    kwargs={'class_index':uc.CLASS_INDEX,
                            'package_index':uc.PACKAGE_INDEX,
                            'qclass_index':uc.QCLASS_INDEX})
            jproc.join()
            # 2.1 Test finding a Java class.
            with open(uc.CLASS_INDEX, 'rb') as cache:
                _cache = pickle.load(cache)
            self.assertIsNotNone(_cache.get('PathTesting'))
            # 2.2 Test finding a package.
            with open(uc.PACKAGE_INDEX, 'rb') as cache:
                _cache = pickle.load(cache)
            self.assertIsNotNone(_cache.get(uc.PACKAGE))
            # 2.3 Test finding a fully qualified class name.
            with open(uc.QCLASS_INDEX, 'rb') as cache:
                _cache = pickle.load(cache)
            self.assertIsNotNone(_cache.get('android.jank.cts.ui.PathTesting'))

            # 3. Test get_cc_result is functional.
            cproc = au.run_multi_proc(
                    func=indexing.get_cc_result, args=[uc.LOCATE_CACHE],
                    kwargs={'cc_class_index':uc.CC_CLASS_INDEX})
            cproc.join()
            # 3.1 Test finding a CC class.
            with open(uc.CC_CLASS_INDEX, 'rb') as cache:
                _cache = pickle.load(cache)
            self.assertIsNotNone(_cache.get('HelloWorldTest'))
            # 4. Clean up.
            targets_to_delete = (uc.CC_CLASS_INDEX,
                                 uc.CLASS_INDEX,
                                 uc.LOCATE_CACHE,
                                 uc.PACKAGE_INDEX,
                                 uc.QCLASS_INDEX)
            for idx in targets_to_delete:
                os.remove(idx)
        else:
            self.assertEqual(au.has_command(UPDATEDB), False)
            self.assertEqual(au.has_command(LOCATE), False)

if __name__ == "__main__":
    unittest.main()