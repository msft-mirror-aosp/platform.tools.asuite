"""Tests for atest_sponge_client."""

import pathlib
import unittest
from unittest import mock
import uuid

from atest.mobly.sponge import atest_sponge_client
from atest.mobly.sponge import sponge_client
from atest.mobly.sponge import status_aggregation
from atest.mobly.storage import gcs_client
from sponge_artifact_creator import invocation_level_artifact_creator
from sponge_artifact_creator import target_level_artifact_creator


class AtestSpongeClientTest(unittest.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_sponge_client_cls = mock.patch.object(
        sponge_client, 'SpongeClient'
    ).start()
    self.mock_sponge_client = self.mock_sponge_client_cls.return_value

    self.mock_gcs_client_cls = mock.patch.object(
        gcs_client, 'GcsClient'
    ).start()
    self.mock_gcs_client = self.mock_gcs_client_cls.return_value

    self.mock_status_aggregator_cls = mock.patch.object(
        status_aggregation, 'SpongeStatusAggregator'
    ).start()
    self.mock_status_aggregator = self.mock_status_aggregator_cls.return_value

    self.client = atest_sponge_client.AtestSpongeClient(
        False, 'api_key', 'token', 'bucket', 'res_dir'
    )

  def test_init_prod(self):
    client = atest_sponge_client.AtestSpongeClient(
        True, 'api_key', 'token', 'bucket', 'res_dir'
    )
    self.assertEqual(client.sponge_url, atest_sponge_client.PROD_SPONGE_URL)

  def test_init_qa(self):
    client = atest_sponge_client.AtestSpongeClient(
        False, 'api_key', 'token', 'bucket', 'res_dir'
    )
    self.assertEqual(client.sponge_url, atest_sponge_client.QA_SPONGE_URL)

  def tearDown(self):
    mock.patch.stopall()
    super().tearDown()

  def test_create_invocation(self):
    self.mock_sponge_client.create_invocation.return_value = 'inv_name'
    self.client._create_invocation('inv_id')  # pylint: disable=protected-access

    self.assertEqual(self.client.sponge_data.invocation_id, 'inv_id')
    self.assertEqual(self.client.sponge_data.invocation_name, 'inv_name')
    self.mock_sponge_client.create_invocation.assert_called_once_with('inv_id')

  def test_update_invocation_status(self):
    self.client.sponge_data.invocation_name = 'inv_name'
    self.client._update_invocation_status('status')  # pylint: disable=protected-access

    self.mock_sponge_client.update_invocation_status.assert_called_once_with(
        'inv_name', 'status'
    )

  def test_update_invocation_files(self):
    self.client.sponge_data.invocation_name = 'inv_name'
    self.client._update_invocation_files('bucket', 'dir', ['file'])  # pylint: disable=protected-access

    self.mock_sponge_client.update_invocation_files.assert_called_once_with(
        'inv_name', 'bucket', 'dir', ['file']
    )

  def test_create_configuration(self):
    self.client.sponge_data.invocation_name = 'inv_name'
    self.client._create_configuration('config_id')  # pylint: disable=protected-access

    self.assertEqual(self.client.sponge_data.config_id, 'config_id')
    self.mock_sponge_client.create_configuration.assert_called_once_with(
        'inv_name', 'config_id'
    )

  def test_create_target(self):
    self.client.sponge_data.invocation_name = 'inv_name'
    self.mock_sponge_client.create_target.return_value = 'target_name'
    self.client._create_target('target_id')  # pylint: disable=protected-access

    self.assertEqual(self.client.sponge_data.target_id, 'target_id')
    self.assertEqual(self.client.sponge_data.target_name, 'target_name')
    self.mock_sponge_client.create_target.assert_called_once_with(
        'inv_name', 'target_id'
    )

  def test_create_configured_target(self):
    self.client.sponge_data.target_name = 'target_name'
    self.client.sponge_data.config_id = 'config_id'
    self.mock_sponge_client.create_configured_target.return_value = (
        'conf_target_name'
    )
    self.client._create_configured_target()  # pylint: disable=protected-access

    self.assertEqual(
        self.client.sponge_data.configured_target_name, 'conf_target_name'
    )
    self.mock_sponge_client.create_configured_target.assert_called_once_with(
        'target_name', 'config_id'
    )

  def test_update_configured_target_status(self):
    self.client.sponge_data.configured_target_name = 'conf_target_name'
    self.client._update_configured_target_status('status')  # pylint: disable=protected-access

    self.mock_sponge_client.update_configured_target_status.assert_called_once_with(
        'conf_target_name', 'status'
    )

  def test_update_configured_target_timing(self):
    self.client.sponge_data.configured_target_name = 'conf_target_name'
    self.client._update_configured_target_timing(duration='1s')  # pylint: disable=protected-access

    self.mock_sponge_client.update_configured_target_timing.assert_called_once_with(
        'conf_target_name', duration='1s'
    )

  def test_create_action(self):
    self.client.sponge_data.configured_target_name = 'conf_target_name'
    self.mock_sponge_client.create_action.return_value = 'action_name'
    self.client._create_action(  # pylint: disable=protected-access
        'status', 1, 'bucket', 'dir', ['file'], duration='1s'
    )

    self.assertEqual(self.client.sponge_data.action_name, 'action_name')
    self.mock_sponge_client.create_action.assert_called_once_with(
        'conf_target_name',
        'status',
        1,
        'bucket',
        'dir',
        ['file'],
        duration='1s',
    )

  def test_finalize_target(self):
    self.client.sponge_data.target_name = 'target_name'
    self.client._finalize_target()  # pylint: disable=protected-access

    self.mock_sponge_client.finalize_target.assert_called_once_with(
        'target_name'
    )

  def test_finalize_configured_target(self):
    self.client.sponge_data.configured_target_name = 'conf_target_name'
    self.client._finalize_configured_target()  # pylint: disable=protected-access

    self.mock_sponge_client.finalize_configured_target.assert_called_once_with(
        'conf_target_name'
    )

  def test_finalize_invocation(self):
    self.client.sponge_data.invocation_name = 'inv_name'
    self.client._finalize_invocation()  # pylint: disable=protected-access

    self.mock_sponge_client.finalize_invocation.assert_called_once_with(
        'inv_name'
    )

  @mock.patch.object(uuid, 'uuid4')
  def test_preprocess_invocation(self, mock_uuid):
    mock_uuid.side_effect = ['inv_id', 'config_id']
    self.mock_sponge_client.create_invocation.return_value = 'inv_name'

    self.client.preprocess_invocation()

    self.assertEqual(self.client.sponge_data.invocation_id, 'inv_id')
    self.assertEqual(self.client.sponge_data.invocation_name, 'inv_name')
    self.mock_sponge_client.create_invocation.assert_called_once_with('inv_id')
    self.assertEqual(self.client.sponge_data.config_id, 'config_id')
    self.mock_sponge_client.create_configuration.assert_called_once_with(
        'inv_name', 'config_id'
    )

  @mock.patch.object(
      invocation_level_artifact_creator, 'InvocationLevelArtifactCreator'
  )
  def test_postprocess_invocation(self, mock_artifact_creator_cls):
    self.client.sponge_data.invocation_id = 'inv_id'
    self.client.sponge_data.invocation_name = 'inv_name'
    self.mock_status_aggregator.get_current_invocation_status.return_value = (
        'status'
    )
    self.mock_gcs_client.upload_dir.return_value = ['file']

    self.client.postprocess_invocation()

    mock_artifact_creator_cls.assert_called_once()
    mock_artifact_creator_cls.return_value.create_artifacts.assert_called_once()
    self.mock_gcs_client.upload_dir.assert_called_once()
    self.mock_sponge_client.update_invocation_files.assert_called_once_with(
        'inv_name', 'bucket', 'inv_id', ['file']
    )
    self.mock_sponge_client.update_invocation_status.assert_called_once_with(
        'inv_name', 'status'
    )
    self.mock_sponge_client.finalize_invocation.assert_called_once_with(
        'inv_name'
    )

  @mock.patch('time.time')
  def test_preprocess_target(self, mock_time):
    mock_time.return_value = 123.45
    self.client.sponge_data.invocation_name = 'inv_name'
    self.client.sponge_data.config_id = 'config_id'
    self.mock_sponge_client.create_target.return_value = 'target_name'
    self.mock_sponge_client.create_configured_target.return_value = (
        'conf_target_name'
    )

    self.client.preprocess_target('target_id')

    self.assertEqual(self.client.sponge_data.target_id, 'target_id')
    self.assertEqual(self.client.sponge_data.target_name, 'target_name')
    self.mock_sponge_client.create_target.assert_called_once_with(
        'inv_name', 'target_id'
    )
    self.assertEqual(
        self.client.sponge_data.configured_target_name, 'conf_target_name'
    )
    self.mock_sponge_client.create_configured_target.assert_called_once_with(
        'target_name', 'config_id'
    )
    self.assertEqual(self.client.target_start_time, 123.45)

  @mock.patch('time.time')
  def test_postprocess_target(self, mock_time):
    self.client.target_start_time = 100.0
    mock_time.return_value = 105.0
    self.client.sponge_data.configured_target_name = 'conf_target_name'
    self.client.sponge_data.target_name = 'target_name'
    self.mock_status_aggregator.get_current_configured_target_status.return_value = (
        'status'
    )

    self.client.postprocess_target()

    self.mock_sponge_client.update_configured_target_status.assert_called_once_with(
        'conf_target_name', 'status'
    )
    self.mock_sponge_client.update_configured_target_timing.assert_called_once_with(
        'conf_target_name', start_time_str='1970-01-01T00:01:40.000Z', duration='5.00s'
    )
    self.mock_sponge_client.finalize_configured_target.assert_called_once_with(
        'conf_target_name'
    )
    self.mock_sponge_client.finalize_target.assert_called_once_with(
        'target_name'
    )
    self.assertEqual(self.client.target_start_time, 0.0)

  @mock.patch.object(
      target_level_artifact_creator, 'TargetLevelArtifactCreator'
  )
  def test_upload_test_result(self, mock_artifact_creator_cls):
    self.client.sponge_data.invocation_id = 'inv_id'
    self.client.sponge_data.target_id = 'target_id'
    self.client.sponge_data.configured_target_name = 'conf_target_name'
    self.mock_gcs_client.upload_dir.side_effect = [['file1'], ['file2']]
    self.mock_status_aggregator.get_action_status.return_value = 'status'
    self.mock_sponge_client.create_action.return_value = 'action_name'

    self.client.upload_test_result('log_dir', 'summary_file', 1)

    mock_artifact_creator_cls.assert_called_once_with(
        src_dir=pathlib.Path('log_dir'), dst_dir=mock.ANY
    )
    mock_artifact_creator_cls.return_value.create_artifacts.assert_called_once()
    self.assertEqual(self.mock_gcs_client.upload_dir.call_count, 2)
    self.mock_gcs_client.upload_dir.assert_has_calls([
        mock.call(mock.ANY, 'inv_id/target_id/run1'),
        mock.call(
            pathlib.Path('log_dir'), 'inv_id/target_id/run1/undeclared_outputs'
        ),
    ])
    self.mock_sponge_client.create_action.assert_called_once_with(
        'conf_target_name',
        'status',
        1,
        'bucket',
        'inv_id/target_id/run1',
        ['file1', 'file2'],
    )


if __name__ == '__main__':
  unittest.main()
