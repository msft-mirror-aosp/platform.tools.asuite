from atest import result_reporter


def add_result_link(
    result_link: str, reporter: result_reporter.ResultReporter
):
  """Add the invocation link to the result reporter.

  Args:
      result_link: The result link to add.
      reporter: The result reporter to add to.
  """
  if isinstance(reporter.test_result_link, list):
    reporter.test_result_link.append(result_link)
  elif isinstance(reporter.test_result_link, str):
    reporter.test_result_link = [reporter.test_result_link, result_link]
  else:
    reporter.test_result_link = [result_link]
