import enum
import logging
from typing import Any
import yaml


class MoblySummaryKeys(enum.Enum):
  TYPE = "Type"
  PASSED = "Passed"
  FAILED = "Failed"
  SKIPPED = "Skipped"
  ERROR = "Error"
  EXECUTED = "Executed"
  REQUESTED = "Requested"


class MoblySummaryValues(enum.Enum):
  SUMMARY = "Summary"


class SpongeStatus(enum.Enum):
  PASSED = "PASSED"
  FAILED = "FAILED"
  SKIPPED = "SKIPPED"
  UNKNOWN = "UNKNOWN"


def aggregate_mobly_status(summary: dict[str, Any]) -> SpongeStatus:
  """Aggregates the Mobly test status."""
  if summary[MoblySummaryKeys.ERROR.value] > 0:
    return SpongeStatus.FAILED
  if summary[MoblySummaryKeys.FAILED.value] > 0:
    return SpongeStatus.FAILED
  if (
      (requested := summary[MoblySummaryKeys.REQUESTED.value]) > 0
      and summary[MoblySummaryKeys.SKIPPED.value] == requested
  ):
    return SpongeStatus.SKIPPED
  if (
      summary[MoblySummaryKeys.PASSED.value]
      == summary[MoblySummaryKeys.EXECUTED.value]
  ):
    return SpongeStatus.PASSED
  return SpongeStatus.UNKNOWN


def get_sponge_action_status(summary_filepath: str) -> SpongeStatus:
  """Returns the Sponge status of a Mobly test action."""
  with open(summary_filepath, "r", encoding="utf-8") as f:
    summary_data = list(yaml.safe_load_all(f))

  summary = [
      entry
      for entry in summary_data
      if entry[MoblySummaryKeys.TYPE.value] == MoblySummaryValues.SUMMARY.value
  ]

  if not summary:
    logging.warning(
        "No summary found in %s",
        summary_filepath,
    )
    return SpongeStatus.UNKNOWN
  return aggregate_mobly_status(summary[0])


def aggregate_sponge_status(statuses: list[SpongeStatus]) -> SpongeStatus:
  """Aggregates the Sponge status."""
  if SpongeStatus.FAILED in statuses:
    return SpongeStatus.FAILED
  if SpongeStatus.UNKNOWN in statuses:
    return SpongeStatus.UNKNOWN
  if statuses and all(status == SpongeStatus.SKIPPED for status in statuses):
    return SpongeStatus.SKIPPED
  return SpongeStatus.PASSED


class SpongeStatusAggregator:
  """A class for aggregating Sponge statuses."""

  def __init__(self):
    self.action_statuses = []
    self.configured_target_statuses = []

  def get_action_status(self, summary_filepath: str) -> str:
    """Returns the Sponge action status."""
    status = get_sponge_action_status(summary_filepath)
    self.action_statuses.append(status)
    return status.value

  def get_current_configured_target_status(self) -> str:
    """Returns the Sponge configured target status."""
    status = aggregate_sponge_status(self.action_statuses)
    self.configured_target_statuses.append(status)
    # Clear the action statuses after aggregating them.
    self.action_statuses = []
    return status.value

  def get_current_invocation_status(self) -> str:
    """Returns the Sponge invocation status."""
    status = aggregate_sponge_status(self.configured_target_statuses)
    # Clear the configured target statuses after aggregating them.
    self.configured_target_statuses = []
    return status.value
