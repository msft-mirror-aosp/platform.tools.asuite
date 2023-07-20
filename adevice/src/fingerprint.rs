//! Recursively hash the contents of a directory
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum EntryType {
    File,
    Symlink,
    Directory,
}

// Represents a file or symlink found in the directory.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Entry {
    pub filename: String,

    pub entry_type: EntryType,

    // path that this symlinks to or ""
    #[serde(skip_serializing_if = "String::is_empty", default)]
    pub symlink: String,

    #[serde(skip_serializing_if = "String::is_empty", default)]
    pub hash: String,
}

#[derive(Debug, Default, PartialEq)]
pub struct Diffs {
    // Files on host, but not on device
    pub device_needs: Vec<Entry>,
    // Files on device, but not host.
    pub device_extra: Vec<Entry>,
    // Files that are different between host and device.
    pub device_diffs: Vec<Entry>,
}

/// Compute the files that need to be added, removed or updated on the device.
/// Each file should land in of the three categories (i.e. updated, not
/// removed and added);
// Rust newbie; all the `a is about lifetimes.  Basically instead of copying
// the Entry, we are store references to it, but we have to tell rustc the
// reference we use and shove in the output won't last longer than the inputs.
#[allow(unused)]
pub fn diff(host_files: &[Entry], device_files: &[Entry]) -> Diffs {
    // TODO(rbraunstein): revisit implementation, can do with one pass on filenames rather than 3.
    // (i.e. what Joe is already doing)
    // Just doing some simple set math to compute diffs, code will probably change,
    // but this allows us to write some unit tests for TDD
    let host_map: HashMap<String, Entry> =
        host_files.iter().map(|e| (e.filename.clone(), e.clone())).collect();
    let device_map: HashMap<String, Entry> =
        device_files.iter().map(|e| (e.filename.clone(), e.clone())).collect();

    let host_set: HashSet<String> = host_files.iter().map(|e| e.filename.clone()).collect();
    let device_set: HashSet<String> = device_files.iter().map(|e| e.filename.clone()).collect();

    Diffs {
        device_needs: host_set
            .difference(&device_set)
            // Missing device file -> entry from host_map
            .map(|filename| host_map.get(filename).unwrap().clone())
            .collect(),
        // TODO(rbraunstein): implement device_extra for deletes.
        device_extra: vec![],
        device_diffs: host_set
            .intersection(&device_set)
            // For all files in both, check to see if the entries are different.
            .filter_map(|filename| {
                let host_entry = host_map.get(filename).unwrap().clone();
                let device_entry = device_map.get(filename).unwrap().clone();
                if (host_entry == device_entry) {
                    return None;
                }
                Some(host_entry)
            })
            .collect(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn empty_inputs() {
        assert_eq!(diff(&Vec::new(), &Vec::new()), Diffs::default());
    }

    #[test]
    fn same_inputs() {
        let file_entry = vec![Entry {
            filename: "a/b/foo.so".to_string(),
            entry_type: EntryType::File,
            hash: "deadbeef".to_string(),
            symlink: "".to_string(),
        }];
        assert_eq!(diff(&file_entry, &file_entry.clone()), Diffs::default());
    }

    #[test]
    fn different_file_type() {
        let file_entry = Entry {
            filename: "a/b/foo.so".to_string(),
            entry_type: EntryType::File,
            hash: "deadbeef".to_string(),
            symlink: "".to_string(),
        };
        let mut dir_entry = file_entry.clone();
        dir_entry.entry_type = EntryType::Directory;

        // TODO(rbraunstein); The equals gives a nice error saying which field differs,
        // figure out how to check it:
        //     failures:
        //        fingerprint::different_file_type

        assert_ne!(diff(&[file_entry], &[dir_entry]), Diffs::default());
    }

    // TODO(rbraunstein): assertables crates for bags/containers.
    // TODO(rbraunstein): a bunch more tests:
}
