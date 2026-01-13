import dataclasses


@dataclasses.dataclass(frozen=True)
class RerunOptions:
  """Data class representing rerun options."""

  iterations: int
  rerun_until_failure: bool
  retry_any_failure: bool
