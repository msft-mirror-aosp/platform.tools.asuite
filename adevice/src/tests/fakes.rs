use super::fingerprint::FileMetadata;
use crate::commands::AdbCommand;
use crate::metrics::MetricSender;
use crate::Device;
use crate::Host;
#[cfg(test)]
use anyhow::Result;
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

#[derive(Default)]
pub struct FakeHost {
    /// Files on the filesystem, relative to PRODUCT_OUT
    files: HashMap<PathBuf, FileMetadata>,
    /// Dependencies from ninja, relative to PRODUCT_OUT
    tracked_files: Vec<String>,
}
impl FakeHost {
    pub fn new(files: &HashMap<PathBuf, FileMetadata>, tracked_files: &[String]) -> FakeHost {
        FakeHost { files: files.clone(), tracked_files: tracked_files.to_owned() }
    }
}

pub struct FakeDevice {
    installed_apks: HashSet<String>,
    /// Files on the filesystem.
    /// User passes some to start, but "push" and "clean" commands will affect it.
    files: HashMap<PathBuf, FileMetadata>,
}
impl FakeDevice {
    pub fn new(files: &HashMap<PathBuf, FileMetadata>) -> FakeDevice {
        FakeDevice { installed_apks: HashSet::new(), files: files.clone() }
    }
}

impl Host for FakeHost {
    fn fingerprint(
        &self,
        _partition_root: &Path,
        _partitions: &[PathBuf],
    ) -> Result<HashMap<PathBuf, FileMetadata>> {
        // TODO(rbraunstein): filter to partitions
        Ok(self.files.clone())
    }

    fn tracked_files(
        &self,
        _partitions: &[PathBuf],
        _config: &crate::tracking::Config,
    ) -> Result<Vec<String>> {
        // TODO(rbraunstein): filter to partitions
        Ok(self.tracked_files.clone())
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

    fn fingerprint(&self, _partitions: &[String]) -> Result<HashMap<PathBuf, FileMetadata>> {
        // Technically, I should filter the result to ensure it only includes `partitions`
        Ok(self.files.clone())
    }

    fn get_installed_apks(&self) -> Result<HashSet<String>> {
        Ok(self.installed_apks.clone())
    }

    fn wait(&self) -> Result<String> {
        Ok(String::new())
    }
}

pub struct FakeMetricSender {}
impl FakeMetricSender {
    pub fn new() -> Self {
        FakeMetricSender {}
    }
}
impl MetricSender for FakeMetricSender {
    // TODO: Capture and test metrics.
    fn add_start_event(&mut self, _command_line: &str) {}
}
