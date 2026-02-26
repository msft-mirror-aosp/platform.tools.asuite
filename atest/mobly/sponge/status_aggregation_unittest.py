import os
import unittest
from unittest import mock

from atest import unittest_constants
from atest.mobly.sponge import status_aggregation

MOBLY_SUMMARY_FILE = os.path.join(
    unittest_constants.TEST_DATA_DIR, "mobly", "sample_test_summary.yaml"
)


class StatusAggregationTest(unittest.TestCase):

  def test_aggregate_mobly_status_failed_error(self):
    summary = {
        status_aggregation.MoblySummaryKeys.ERROR.value: 1,
        status_aggregation.MoblySummaryKeys.FAILED.value: 0,
        status_aggregation.MoblySummaryKeys.REQUESTED.value: 10,
        status_aggregation.MoblySummaryKeys.SKIPPED.value: 0,
        status_aggregation.MoblySummaryKeys.PASSED.value: 9,
        status_aggregation.MoblySummaryKeys.EXECUTED.value: 9,
    }
    self.assertEqual(
        status_aggregation.aggregate_mobly_status(summary),
        status_aggregation.SpongeStatus.FAILED,
    )

  def test_aggregate_mobly_status_failed_failure(self):
    summary = {
        status_aggregation.MoblySummaryKeys.ERROR.value: 0,
        status_aggregation.MoblySummaryKeys.FAILED.value: 1,
        status_aggregation.MoblySummaryKeys.REQUESTED.value: 10,
        status_aggregation.MoblySummaryKeys.SKIPPED.value: 0,
        status_aggregation.MoblySummaryKeys.PASSED.value: 9,
        status_aggregation.MoblySummaryKeys.EXECUTED.value: 10,
    }
    self.assertEqual(
        status_aggregation.aggregate_mobly_status(summary),
        status_aggregation.SpongeStatus.FAILED,
    )

  def test_aggregate_mobly_status_skipped(self):
    summary = {
        status_aggregation.MoblySummaryKeys.ERROR.value: 0,
        status_aggregation.MoblySummaryKeys.FAILED.value: 0,
        status_aggregation.MoblySummaryKeys.REQUESTED.value: 10,
        status_aggregation.MoblySummaryKeys.SKIPPED.value: 10,
        status_aggregation.MoblySummaryKeys.PASSED.value: 0,
        status_aggregation.MoblySummaryKeys.EXECUTED.value: 0,
    }
    self.assertEqual(
        status_aggregation.aggregate_mobly_status(summary),
        status_aggregation.SpongeStatus.SKIPPED,
    )

  def test_aggregate_mobly_status_passed(self):
    summary = {
        status_aggregation.MoblySummaryKeys.ERROR.value: 0,
        status_aggregation.MoblySummaryKeys.FAILED.value: 0,
        status_aggregation.MoblySummaryKeys.REQUESTED.value: 10,
        status_aggregation.MoblySummaryKeys.SKIPPED.value: 0,
        status_aggregation.MoblySummaryKeys.PASSED.value: 10,
        status_aggregation.MoblySummaryKeys.EXECUTED.value: 10,
    }
    self.assertEqual(
        status_aggregation.aggregate_mobly_status(summary),
        status_aggregation.SpongeStatus.PASSED,
    )

  def test_aggregate_mobly_status_skipped_passed(self):
    summary = {
        status_aggregation.MoblySummaryKeys.ERROR.value: 0,
        status_aggregation.MoblySummaryKeys.FAILED.value: 0,
        status_aggregation.MoblySummaryKeys.REQUESTED.value: 10,
        status_aggregation.MoblySummaryKeys.SKIPPED.value: 5,
        status_aggregation.MoblySummaryKeys.PASSED.value: 5,
        status_aggregation.MoblySummaryKeys.EXECUTED.value: 5,
    }
    self.assertEqual(
        status_aggregation.aggregate_mobly_status(summary),
        status_aggregation.SpongeStatus.PASSED,
    )

  def test_aggregate_mobly_status_zero_requested(self):
    summary = {
        status_aggregation.MoblySummaryKeys.ERROR.value: 0,
        status_aggregation.MoblySummaryKeys.FAILED.value: 0,
        status_aggregation.MoblySummaryKeys.REQUESTED.value: 0,
        status_aggregation.MoblySummaryKeys.SKIPPED.value: 0,
        status_aggregation.MoblySummaryKeys.PASSED.value: 0,
        status_aggregation.MoblySummaryKeys.EXECUTED.value: 0,
    }
    self.assertEqual(
        status_aggregation.aggregate_mobly_status(summary),
        status_aggregation.SpongeStatus.PASSED,
    )

  def test_aggregate_mobly_status_unknown(self):
    summary = {
        status_aggregation.MoblySummaryKeys.ERROR.value: 0,
        status_aggregation.MoblySummaryKeys.FAILED.value: 0,
        status_aggregation.MoblySummaryKeys.REQUESTED.value: 10,
        status_aggregation.MoblySummaryKeys.SKIPPED.value: 1,
        status_aggregation.MoblySummaryKeys.PASSED.value: 8,
        status_aggregation.MoblySummaryKeys.EXECUTED.value: 9,
    }
    self.assertEqual(
        status_aggregation.aggregate_mobly_status(summary),
        status_aggregation.SpongeStatus.UNKNOWN,
    )

  def test_get_sponge_action_status_from_file(self):
    status = status_aggregation.get_sponge_action_status(MOBLY_SUMMARY_FILE)
    self.assertEqual(status, status_aggregation.SpongeStatus.FAILED)

  @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="")
  def test_get_sponge_action_status_no_summary(self, _):
    status = status_aggregation.get_sponge_action_status("summary.yaml")
    self.assertEqual(status, status_aggregation.SpongeStatus.UNKNOWN)

  def test_aggregate_sponge_status(self):
    test_cases = [
        (
            [
                status_aggregation.SpongeStatus.PASSED,
                status_aggregation.SpongeStatus.PASSED,
            ],
            status_aggregation.SpongeStatus.PASSED,
        ),
        (
            [
                status_aggregation.SpongeStatus.PASSED,
                status_aggregation.SpongeStatus.FAILED,
            ],
            status_aggregation.SpongeStatus.FAILED,
        ),
        (
            [
                status_aggregation.SpongeStatus.SKIPPED,
                status_aggregation.SpongeStatus.SKIPPED,
            ],
            status_aggregation.SpongeStatus.SKIPPED,
        ),
        (
            [
                status_aggregation.SpongeStatus.PASSED,
                status_aggregation.SpongeStatus.SKIPPED,
            ],
            status_aggregation.SpongeStatus.PASSED,
        ),
        (
            [
                status_aggregation.SpongeStatus.UNKNOWN,
                status_aggregation.SpongeStatus.PASSED,
            ],
            status_aggregation.SpongeStatus.UNKNOWN,
        ),
        (
            [],
            status_aggregation.SpongeStatus.PASSED,
        ),
    ]

    for statuses, expected_status in test_cases:
      with self.subTest(statuses=statuses):
        self.assertEqual(
            status_aggregation.aggregate_sponge_status(statuses),
            expected_status,
        )

  @mock.patch("atest.mobly.sponge.status_aggregation.get_sponge_action_status")
  def test_sponge_status_aggregator(self, mock_get_status):
    aggregator = status_aggregation.SpongeStatusAggregator()

    # Action 1: Passed
    mock_get_status.return_value = status_aggregation.SpongeStatus.PASSED
    self.assertEqual(aggregator.get_action_status("summary1.yaml"), "PASSED")

    # Action 2: Skipped
    mock_get_status.return_value = status_aggregation.SpongeStatus.SKIPPED
    self.assertEqual(aggregator.get_action_status("summary2.yaml"), "SKIPPED")

    # Configured Target 1: Aggregate (PASSED, SKIPPED) -> PASSED
    self.assertEqual(aggregator.get_current_configured_target_status(), "PASSED")

    # Action 3: Failed
    mock_get_status.return_value = status_aggregation.SpongeStatus.FAILED
    self.assertEqual(aggregator.get_action_status("summary3.yaml"), "FAILED")

    # Configured Target 2: Aggregate (FAILED) -> FAILED
    self.assertEqual(aggregator.get_current_configured_target_status(), "FAILED")

    # Invocation: Aggregate (PASSED, FAILED) -> FAILED
    self.assertEqual(aggregator.get_current_invocation_status(), "FAILED")


if __name__ == "__main__":
  unittest.main()
