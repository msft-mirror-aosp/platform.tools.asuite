use adevice::adevice::{Device, Host};
use adevice::commands::{AdbAction, AdbCommand};
use adevice::fingerprint::FileMetadata;
use adevice::metrics::MetricSender;
use adevice::tracking::Config;
use anyhow::Result;
use std::cell::RefCell;
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

    /// Returns true iff `path` starts with one of the `partitions`
    fn on_a_partition(path: &Path, partitions: &[PathBuf]) -> bool {
        for p in partitions {
            if path.starts_with(p) {
                return true;
            }
        }
        false
    }
}

#[derive(Default)]
pub struct FakeDevice {
    /// Apks that are installed with "adb install" on the /data partition.
    /// Used to see if we should warn the user about potential problems.
    installed_apks: HashSet<String>,

    /// Files on the filesystem.
    /// User passes some to start, but "push" and "clean" commands will affect it.
    files: HashMap<PathBuf, FileMetadata>,

    // Files pushed to the device via an `adb_command`
    pushes: RefCell<Vec<PathBuf>>,
    // Files and directories removed from the device via `adb_command`
    removes: RefCell<Vec<PathBuf>>,
}
impl FakeDevice {
    pub fn new(files: &HashMap<PathBuf, FileMetadata>) -> FakeDevice {
        FakeDevice { files: files.clone(), ..Default::default() }
    }

    /// Returns the ordered list of all removed files or dirs.
    pub fn removes(&self) -> Vec<PathBuf> {
        self.removes.borrow().clone()
    }

    /// Returns orderd list of all pushed files.
    #[allow(dead_code)]
    pub fn pushes(&self) -> Vec<PathBuf> {
        self.pushes.borrow().clone()
    }
}

impl Host for FakeHost {
    fn fingerprint(
        &self,
        _partition_root: &Path,
        partitions: &[PathBuf],
    ) -> Result<HashMap<PathBuf, FileMetadata>> {
        let mut files = self.files.clone();
        files.retain(|path, _m| Self::on_a_partition(path, partitions));
        Ok(files)
    }

    fn tracked_files(&self, _config: &Config) -> Result<Vec<String>> {
        Ok(self.tracked_files.clone())
    }
}

impl Device for FakeDevice {
    // Convert "push" into updating the filesystem, ignore everything else.
    fn run_adb_command(&self, cmd: &AdbCommand) -> Result<String> {
        match cmd.action {
            AdbAction::Push { .. } => self.pushes.borrow_mut().push(cmd.file.clone()),
            AdbAction::DeleteDir { .. } | AdbAction::DeleteFile => {
                self.removes.borrow_mut().push(cmd.file.clone())
            }
            _ => (),
        }
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

    fn prep_after_flash(&self) -> Result<()> {
        Ok(())
    }

    fn prep_for_push(&self) -> Result<String> {
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
