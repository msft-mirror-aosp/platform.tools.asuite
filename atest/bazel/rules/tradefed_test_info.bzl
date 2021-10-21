# Copyright (C) 2021 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A provider used to provide test information required by Tradefed rules."""

TradefedTestInfo = provider(
    doc = "Info required by Tradefed rules to run tests",
    fields = {
        "test_binaries": "Test binary files",
        "test_configs": "Tradefed config files",
        "shared_libs": "Targets that should be dynamically linked into this target",
        "module_name": "Test module name",
    },
)
