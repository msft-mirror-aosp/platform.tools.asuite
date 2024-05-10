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

"""Unit tests for banner."""

from pathlib import Path
from pyfakefs import fake_filesystem_unittest

from atest import banner


class BannerPrinterTest(fake_filesystem_unittest.TestCase):
  """Tests for BannerPrinter."""

  def setUp(self):
    self.setUpPyfakefs()
    self.config_dir = Path("/config")

  def test_print_already_printed_today_does_not_print(self):
    printed_banners = []
    print_func = lambda m: printed_banners.append(m)
    date_supplier = lambda : "2024-04-16"
    printer_1 = banner.BannerPrinter(self.config_dir)
    printer_1.register("banner message1")
    printer_1.print(print_func=print_func, date_supplier=date_supplier)
    printer_2 = banner.BannerPrinter(self.config_dir)
    printer_2.register("banner message2")

    printer_2.print(print_func=print_func, date_supplier=date_supplier)

    self.assertCountEqual(printed_banners, ["banner message1"])
