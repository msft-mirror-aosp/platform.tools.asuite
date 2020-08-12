#  Copyright (C) 2020 The Android Open Source Project
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
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


""" Utility functions for logstorage. """
from __future__ import print_function

import httplib2
import constants

# pylint: disable=import-error
from googleapiclient.discovery import build


class BuildClient:
    """Build api helper class."""

    def __init__(self, creds):
        """Init BuildClient class.
        Args:
            creds: An oauth2client.OAuth2Credentials instance.
        """
        http_auth = creds.authorize(httplib2.Http())
        self.client = build(
            serviceName=constants.STORAGE_SERVICE_NAME,
            version=constants.STORAGE_API_VERSION,
            cache_discovery=False,
            http=http_auth)

    def insert_local_build(self, external_id, target, branch):
        """Insert a build record.
        Args:
            external_id: unique id of build record.
            target: build target.
            branch: build branch.

        Returns:
            An build record object.
        """
        body = {
            "buildId": "",
            "externalId": external_id,
            "branch": branch,
            "target": {
                "name": target,
                "target": target
            },
            "buildAttemptStatus": "complete",
        }
        return self.client.build().insert(buildType="local",
                                          body=body).execute()

    def insert_build_attempts(self, build_id, target):
        """Insert a build attempt record.
        Args:
            build_id: id of build record.
            target: build target.

        Returns:
            An build attempt object.
        """
        build_attempt = {
            "id": 0,
            "status": "complete",
            "successful": True
        }
        return self.client.buildattempt().insert(buildId=build_id,
                                                 target=target,
                                                 body=build_attempt).execute()

    def insert_invocation(self, build_id, target, branch):
        """Insert a build invocation record.
        Args:
            build_id: id of build record.
            target: build target.
            branch: build branch.

        Returns:
            A build invocation object.
        """
        invocation = {
            "primaryBuild": {
                "buildId": build_id,
                "buildTarget": target,
                "branch": branch,
            },
            "schedulerState": "running"
        }
        return self.client.invocation().insert(body=invocation).execute()

    def insert_work_unit(self, invocation_id):
        """Insert a workunit record.
          Args:
              invocation_id: id of the invocation.

          Returns:
              the workunit object.
          """
        workunit = {
            'invocationId': invocation_id
        }
        return self.client.workunit().insert(body=workunit).execute()
