use super::fingerprint;
use crate::commands::AdbCommand;
use crate::tests::{dir_metadata, file_metadata};
use crate::Device;
use crate::Host;
#[cfg(test)]
use anyhow::Result;
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

pub struct FakeHost {}
impl FakeHost {
    pub fn new() -> FakeHost {
        FakeHost {}
    }
}

pub struct FakeDevice {
    installed_apks: HashSet<String>,
}
impl FakeDevice {
    pub fn new() -> FakeDevice {
        FakeDevice { installed_apks: HashSet::new() }
    }
}

impl Host for FakeHost {
    fn fingerprint(
        &self,
        _partition_root: &Path,
        _partitions: &[PathBuf],
    ) -> Result<HashMap<PathBuf, fingerprint::FileMetadata>> {
        // TODO(rbraunstein): This is a placeholder for now. Tests will set it.
        Ok(HashMap::from([
            (PathBuf::from("system/fakefs_default_file"), file_metadata("digest1")),
            (PathBuf::from("system/fakefs_new_file"), file_metadata("digest1")),
            (PathBuf::from("system"), dir_metadata()),
        ]))
    }

    fn tracked_files(
        &self,
        _partitions: &[PathBuf],
        _config: &crate::tracking::Config,
    ) -> Result<Vec<String>> {
        Ok(vec!["system/fakefs_default_file".to_string(), "system/fakefs_new_file".to_string()])
    }
}

impl Device for FakeDevice {
    // Convert "push" into updating the filesystem, ignore everything else.
    fn run_adb_command(&self, _args: &AdbCommand) -> Result<String> {
        Ok(String::new())
    }

    // No need to do anything.
    fn reboot(&self) -> Result<String> {
        Ok(String::new())
    }

    // No need to do anything.
    fn soft_restart(&self) -> Result<String> {
        Ok(String::new())
    }

    fn fingerprint(
        &self,
        _partitions: &[String],
    ) -> Result<HashMap<PathBuf, fingerprint::FileMetadata>> {
        // TODO(rbraunstein): This is a placeholder for now. Tests will set it.
        // Technically, I should filter the result to ensure it only includes `partitions`
        Ok(HashMap::from([
            (PathBuf::from("system/fakefs_default_file"), file_metadata("digest1")),
            (PathBuf::from("system"), dir_metadata()),
        ]))
    }

    fn get_installed_apks(&self) -> Result<HashSet<String>> {
        Ok(self.installed_apks.clone())
    }

    fn wait(&self) -> Result<String> {
        Ok(String::new())
    }
}
