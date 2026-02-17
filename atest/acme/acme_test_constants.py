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

"""Unittest constants for the ACME directory."""

from atest import constants
from atest import test_mapping
from atest import unittest_constants
from test_configs_proto import test_configs_pb2

MODULE_PLAN = test_configs_pb2.ModulePlan(
    module=unittest_constants.MODULE_NAME,
    include=['include-filter1', 'include-filter2'],
    exclude=['exclude-filter1', 'exclude-filter2'],
    module_args=[test_configs_pb2.KeyValue(key='arg1', value='val1')],
)
MODULE_PLAN_SIMPLE = test_configs_pb2.ModulePlan(
    module=unittest_constants.MODULE_NAME,
)
MODULE2_PLAN = test_configs_pb2.ModulePlan(
    module=unittest_constants.MODULE2_NAME,
    module_args=[test_configs_pb2.KeyValue(key='arg2', value='val2')],
)
MODULE2_PLAN_SIMPLE = test_configs_pb2.ModulePlan(
    module=unittest_constants.MODULE2_NAME,
)

SCHEDULING_PLAN = test_configs_pb2.TestSchedulingPlan(
    name='sample-scheduling-plan'
)
SCHEDULING_PLAN_2 = test_configs_pb2.TestSchedulingPlan(
    name='sample-scheduling-plan-2'
)

TEST_EXECUTION_PLAN = test_configs_pb2.TestExecutionPlan(
    name='sample-test-execution-plan', tests=[MODULE_PLAN, MODULE2_PLAN]
)
TEST_EXECUTION_PLAN_2 = test_configs_pb2.TestExecutionPlan(
    name='sample-test-execution-plan-2',
    tests=[MODULE2_PLAN, MODULE_PLAN_SIMPLE],
)
TEST_EXECUTION_PLAN_3 = test_configs_pb2.TestExecutionPlan(
    name='sample-test-execution-plan-3', tests=[MODULE2_PLAN_SIMPLE]
)
TEST_WORKFLOW = test_configs_pb2.TestWorkflow(
    name='sample-workflow-1',
    scheduling_plan=SCHEDULING_PLAN,
    execution_plan=TEST_EXECUTION_PLAN,
)
TEST_WORKFLOW_2 = test_configs_pb2.TestWorkflow(
    name='sample-workflow-2',
    scheduling_plan=SCHEDULING_PLAN,
    execution_plan=TEST_EXECUTION_PLAN_2,
)
TEST_WORKFLOW_3 = test_configs_pb2.TestWorkflow(
    name='sample-workflow-3',
    scheduling_plan=SCHEDULING_PLAN,
    execution_plan=TEST_EXECUTION_PLAN_3,
)
TEST_WORKFLOW_3_SCHEDULING_PLAN_2 = test_configs_pb2.TestWorkflow(
    name='sample-workflow-3',
    scheduling_plan=SCHEDULING_PLAN_2,
    execution_plan=TEST_EXECUTION_PLAN_3,
)
TEST_TRIGGER_1 = test_configs_pb2.TestTrigger(
    name='sample-test-trigger',
    list=test_configs_pb2.TestWorkflowCollection(
        workflows=[
            test_configs_pb2.TestWorkflow(
                name=TEST_WORKFLOW.name,
                scheduling_plan=test_configs_pb2.TestSchedulingPlan(
                    name=SCHEDULING_PLAN.name
                ),
                execution_plan=test_configs_pb2.TestExecutionPlan(
                    name=TEST_EXECUTION_PLAN.name
                ),
            )
        ]
    ),
)
TEST_TRIGGER_1_REFERENCE_ONLY = test_configs_pb2.TestTrigger(
    name='sample-test-trigger',
    list=test_configs_pb2.TestWorkflowCollection(
        workflows=[
            test_configs_pb2.TestWorkflow(
                name=TEST_WORKFLOW.name,
            )
        ]
    ),
)
TEST_TRIGGER_2 = test_configs_pb2.TestTrigger(
    name='sample-test-trigger-2',
    list=test_configs_pb2.TestWorkflowCollection(
        workflows=[
            test_configs_pb2.TestWorkflow(
                name=TEST_WORKFLOW_2.name,
                scheduling_plan=test_configs_pb2.TestSchedulingPlan(
                    name=SCHEDULING_PLAN.name
                ),
                execution_plan=test_configs_pb2.TestExecutionPlan(
                    name=TEST_EXECUTION_PLAN_2.name
                ),
            ),
            test_configs_pb2.TestWorkflow(
                name=TEST_WORKFLOW_3.name,
                scheduling_plan=test_configs_pb2.TestSchedulingPlan(
                    name=SCHEDULING_PLAN.name
                ),
                execution_plan=test_configs_pb2.TestExecutionPlan(
                    name=TEST_EXECUTION_PLAN_3.name
                ),
            ),
        ]
    ),
)
TEST_TRIGGER_2_REFERENCE_ONLY = test_configs_pb2.TestTrigger(
    name='sample-test-trigger-2',
    list=test_configs_pb2.TestWorkflowCollection(
        workflows=[
            test_configs_pb2.TestWorkflow(
                name=TEST_WORKFLOW_2.name,
            ),
            test_configs_pb2.TestWorkflow(
                name=TEST_WORKFLOW_3.name,
            ),
        ]
    ),
)
TEST_TRIGGER_2_MIXED_SCHEDULING_PLANS = test_configs_pb2.TestTrigger(
    name='sample-test-trigger-2',
    list=test_configs_pb2.TestWorkflowCollection(
        workflows=[
            test_configs_pb2.TestWorkflow(
                name=TEST_WORKFLOW_2.name,
                scheduling_plan=test_configs_pb2.TestSchedulingPlan(
                    name=SCHEDULING_PLAN.name
                ),
                execution_plan=test_configs_pb2.TestExecutionPlan(
                    name=TEST_EXECUTION_PLAN_2.name
                ),
            ),
            test_configs_pb2.TestWorkflow(
                name=TEST_WORKFLOW_3_SCHEDULING_PLAN_2.name,
                scheduling_plan=test_configs_pb2.TestSchedulingPlan(
                    name=SCHEDULING_PLAN_2.name
                ),
                execution_plan=test_configs_pb2.TestExecutionPlan(
                    name=TEST_EXECUTION_PLAN_3.name
                ),
            ),
        ]
    ),
)

TEST_TRIGGER_2_MIXED_SCHEDULING_PLANS_REFERENCE_ONLY = (
    test_configs_pb2.TestTrigger(
        name='sample-test-trigger-2',
        list=test_configs_pb2.TestWorkflowCollection(
            workflows=[
                test_configs_pb2.TestWorkflow(
                    name=TEST_WORKFLOW_2.name,
                ),
                test_configs_pb2.TestWorkflow(
                    name=TEST_WORKFLOW_3_SCHEDULING_PLAN_2.name,
                ),
            ]
        ),
    )
)

INLINE_WORKFLOW_EXECUTION_PLAN = test_configs_pb2.TestExecutionPlan(
    name='sample-inline-workflow_inline_plan',
    tests=[MODULE2_PLAN, MODULE_PLAN_SIMPLE],
)
TEST_TRIGGER_INLINE_WORKFLOW = test_configs_pb2.TestTrigger(
    name='sample-inline-workflow',
    inline=test_configs_pb2.TestWorkflowInline(
        scheduling_plan=SCHEDULING_PLAN,
        tests=[MODULE2_PLAN, MODULE_PLAN_SIMPLE],
    ),
)

SAMPLE_TEST_CONFIG = test_configs_pb2.TestConfigs(
    execution_plans=[
        TEST_EXECUTION_PLAN,
        TEST_EXECUTION_PLAN_2,
        TEST_EXECUTION_PLAN_3,
    ],
    workflows=[TEST_WORKFLOW, TEST_WORKFLOW_2, TEST_WORKFLOW_3],
    triggers=[
        TEST_TRIGGER_1,
        TEST_TRIGGER_2,
    ],
)
SAMPLE_TEST_CONFIG_MIXED_SCHEDULING_PLANS = test_configs_pb2.TestConfigs(
    execution_plans=[
        TEST_EXECUTION_PLAN,
        TEST_EXECUTION_PLAN_2,
        TEST_EXECUTION_PLAN_3,
    ],
    workflows=[TEST_WORKFLOW, TEST_WORKFLOW_2, TEST_WORKFLOW_3],
    triggers=[
        TEST_TRIGGER_1,
        TEST_TRIGGER_2_MIXED_SCHEDULING_PLANS,
    ],
)
# When generating the full test-configs.pb, the triggers field only has the name
# of the workflow populated.
SAMPLE_FULL_TEST_CONFIGS = test_configs_pb2.TestConfigs(
    execution_plans=[
        TEST_EXECUTION_PLAN,
        TEST_EXECUTION_PLAN_2,
        TEST_EXECUTION_PLAN_3,
    ],
    workflows=[TEST_WORKFLOW, TEST_WORKFLOW_2, TEST_WORKFLOW_3],
    triggers=[
        TEST_TRIGGER_1_REFERENCE_ONLY,
        TEST_TRIGGER_2_REFERENCE_ONLY,
    ],
)

MODULE_PLAN_TEST_DETAILS = test_mapping.TestDetail({
    'name': unittest_constants.MODULE_NAME,
    'options': [
        {constants.TF_INCLUDE_FILTER_OPTION: 'include-filter1'},
        {constants.TF_INCLUDE_FILTER_OPTION: 'include-filter2'},
        {constants.TF_EXCLUDE_FILTER_OPTION: 'exclude-filter1'},
        {constants.TF_EXCLUDE_FILTER_OPTION: 'exclude-filter2'},
        {'arg1': 'val1'},
    ],
})
MODULE_PLAN_SIMPLE_TEST_DETAILS = test_mapping.TestDetail(
    {'name': unittest_constants.MODULE_NAME}
)
MODULE2_PLAN_TEST_DETAILS = test_mapping.TestDetail({
    'name': unittest_constants.MODULE2_NAME,
    'options': [
        {'arg2': 'val2'},
    ],
})
MODULE2_PLAN_SIMPLE_TEST_DETAILS = test_mapping.TestDetail(
    {'name': unittest_constants.MODULE2_NAME}
)
