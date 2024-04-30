# Copyright 2024, The Android Open Source Project
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

"""Classes used to handle banners."""

from __future__ import annotations

from datetime import date
import json
import logging
from pathlib import Path
from typing import Any, Callable

from atest import atest_utils
from atest import constants


class BannerHistory:
  """A history for banner handling."""

  _LAST_BANNER_PROMPT_DATE = 'last_banner_prompt_date'

  @staticmethod
  def create(config_dir: Path) -> BannerHistory:
    config_dir.mkdir(parents=True, exist_ok=True)
    history_file = config_dir.joinpath('banner.json')

    if not history_file.exists():
      history_file.touch()
      history = {}
    else:
      try:
        history = json.loads(history_file.read_text())
      except json.JSONDecodeError as e:
        atest_utils.print_and_log_error(
            'Banner history json file is in a bad format: %s', e
        )
        history = {}

    return BannerHistory(history_file, history)

  def __init__(self, history_file: Path, history: dict):
    self._history_file = history_file
    self._history = history

  def get_last_banner_prompt_date(self) -> str:
    """Get the last date when banner was prompt."""
    return self._history.get(BannerHistory._LAST_BANNER_PROMPT_DATE, '')

  def set_last_banner_prompt_date(self, date: str):
    """Set the last date when banner was prompt."""
    self._history[BannerHistory._LAST_BANNER_PROMPT_DATE] = date
    self._history_file.write_text(json.dumps(self._history))


class BannerPrinter:
  """A printer used to collect and print banners."""

  @staticmethod
  def create() -> BannerPrinter:
    return BannerPrinter(atest_utils.get_config_folder())

  def __init__(self, config_dir: Path):
    self._messages = []
    self._config_dir = config_dir

  def register(self, message: str):
    """Register a banner message."""
    self._messages.append(message)

  def print(self, print_func: Callable = None, date_supplier: Callable = None):
    """Print the banners."""

    if not self._messages:
      return

    if not print_func:
      print_func = lambda m: atest_utils.colorful_print(m, constants.YELLOW)

    if not date_supplier:
      date_supplier = lambda: str(date.today())

    today = date_supplier()
    history = BannerHistory.create(self._config_dir)
    if history.get_last_banner_prompt_date() != today:
      for message in self._messages:
        print_func(message)

      history.set_last_banner_prompt_date(today)
