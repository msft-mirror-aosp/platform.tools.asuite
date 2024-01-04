#!/usr/bin/env python3
#
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

"""Unit test for the Snapshot module."""

import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest

from atest.integration_tests.snapshot import Snapshot


class SnapshotTest(unittest.TestCase):
    """Snapshot test class unit test."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_take_snapshot_empty_dir_snapshot_is_created(self):
        """Test taking a snapshot of an empty directory."""
        workspace = self.temp_dir / "workspace"
        workspace.mkdir()
        snapshot = Snapshot(self.temp_dir / "db")

        snapshot.take_snapshot("test", workspace)

        self.assertTrue(
            self.temp_dir.joinpath("db/test_metadata.json").exists()
        )

    def test_take_snapshot_with_files_files_are_recorded(self):
        """Test taking a snapshot of a directory with files."""
        workspace = self.temp_dir / "workspace"
        workspace.mkdir()
        workspace.joinpath("dir1").mkdir()
        workspace.joinpath("dir1", "file1").write_text("test", encoding="utf-8")
        snapshot = Snapshot(self.temp_dir / "db")

        snapshot.take_snapshot("test", workspace)

        with open(
            self.temp_dir / "db" / "test_metadata.json", encoding="utf-8"
        ) as f:
            file_infos = json.load(f)
        self.assertEqual(len(file_infos), 2)
        self.assertIn("dir1/file1", file_infos)
        self.assertIn("dir1", file_infos)

    def test_take_snapshot_with_include_paths(self):
        """Test taking a snapshot with include paths."""
        workspace = self.temp_dir / "workspace"
        workspace.mkdir()
        workspace.joinpath("dir1").mkdir()
        workspace.joinpath("dir1", "file1").write_text("test", encoding="utf-8")
        workspace.joinpath("dir2").mkdir()
        workspace.joinpath("dir2", "file2").write_text("test", encoding="utf-8")
        snapshot = Snapshot(self.temp_dir / "db")

        snapshot.take_snapshot("test", workspace, include_paths=["dir2"])

        with open(
            self.temp_dir / "db" / "test_metadata.json", encoding="utf-8"
        ) as f:
            file_infos = json.load(f)
        self.assertEqual(len(file_infos), 2)
        self.assertIn("dir2", file_infos)
        self.assertIn("dir2/file2", file_infos)

    def test_take_snapshot_with_exclude_paths(self):
        """Test taking a snapshot with exclude paths."""
        workspace = self.temp_dir / "workspace"
        workspace.mkdir()
        workspace.joinpath("dir1").mkdir()
        workspace.joinpath("dir1", "file1").write_text("test", encoding="utf-8")
        workspace.joinpath("dir2").mkdir()
        workspace.joinpath("dir2", "file2").write_text("test", encoding="utf-8")
        snapshot = Snapshot(self.temp_dir / "db")

        snapshot.take_snapshot("test", workspace, exclude_paths=["dir1"])

        with open(
            self.temp_dir / "db" / "test_metadata.json", encoding="utf-8"
        ) as f:
            file_infos = json.load(f)
        self.assertEqual(len(file_infos), 2)
        self.assertIn("dir2", file_infos)
        self.assertIn("dir2/file2", file_infos)

    def test_take_snapshot_with_include_and_exclude_paths(self):
        """Test taking a snapshot with include and exclude paths."""
        workspace = self.temp_dir / "workspace"
        workspace.mkdir()
        workspace.joinpath("dir1").mkdir()
        workspace.joinpath("dir1", "file1").write_text("test", encoding="utf-8")
        workspace.joinpath("dir2").mkdir()
        workspace.joinpath("dir2", "file2").write_text("test", encoding="utf-8")
        snapshot = Snapshot(self.temp_dir / "db")

        snapshot.take_snapshot(
            "test",
            workspace,
            include_paths=["dir1"],
            exclude_paths=["dir1/file1"],
        )

        with open(
            self.temp_dir / "db" / "test_metadata.json", encoding="utf-8"
        ) as f:
            file_infos = json.load(f)
        self.assertEqual(len(file_infos), 1)
        self.assertIn("dir1", file_infos)

    def test_restore_snapshot_empty_dir(self):
        """Test restoring a snapshot of an empty directory."""
        workspace = self.temp_dir / "workspace"
        workspace.mkdir()
        workspace.joinpath("dir1").mkdir()
        snapshot = Snapshot(self.temp_dir / "db")
        snapshot.take_snapshot("test", workspace)

        restore_dir = self.temp_dir / "restore"
        snapshot.restore_snapshot("test", restore_dir)

        self.assertTrue(restore_dir.joinpath("dir1").exists())

    def test_restore_snapshot_with_deleted_files(self):
        """Test restoring a snapshot with deleted files."""
        workspace = self.temp_dir / "workspace"
        workspace.mkdir()
        workspace.joinpath("dir1").mkdir()
        workspace.joinpath("dir1", "file1").write_text("test", encoding="utf-8")
        snapshot = Snapshot(self.temp_dir / "db")
        snapshot.take_snapshot("test", workspace)
        workspace.joinpath("dir1", "file1").unlink()

        snapshot.restore_snapshot("test", workspace)

        self.assertTrue(workspace.joinpath("dir1", "file1").exists())

    def test_restore_snapshot_with_extra_files(self):
        """Test restoring a snapshot with extra files."""
        workspace = self.temp_dir / "workspace"
        workspace.mkdir()
        workspace.joinpath("dir1").mkdir()
        workspace.joinpath("dir1", "file1").write_text("test", encoding="utf-8")
        snapshot = Snapshot(self.temp_dir / "db")
        snapshot.take_snapshot("test", workspace)
        workspace.joinpath("dir1", "file2").write_text("test", encoding="utf-8")

        snapshot.restore_snapshot("test", workspace)

        self.assertTrue(workspace.joinpath("dir1", "file1").exists())
        self.assertFalse(workspace.joinpath("dir1", "file2").exists())

    def test_restore_snapshot_with_modified_files(self):
        """Test restoring a snapshot with modified files."""
        workspace = self.temp_dir / "workspace"
        workspace.mkdir()
        workspace.joinpath("dir1").mkdir()
        workspace.joinpath("dir1", "file1").write_text(
            "test1", encoding="utf-8"
        )
        snapshot = Snapshot(self.temp_dir / "db")
        snapshot.take_snapshot("test", workspace)
        # Sleep 10 milliseconds because the file change check is based on
        # the file's modified timestamp
        time.sleep(0.01)
        workspace.joinpath("dir1", "file1").write_text(
            "test2", encoding="utf-8"
        )

        snapshot.restore_snapshot("test", workspace)

        self.assertTrue(
            workspace.joinpath("dir1", "file1").read_text("utf-8") == "test1"
        )


if __name__ == "__main__":
    unittest.main()
