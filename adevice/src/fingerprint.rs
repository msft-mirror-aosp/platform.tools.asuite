//! Recursively hash the contents of a directory
use hex::encode;
use ring::digest::{Context, SHA256};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::{self, Read};
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum FileType {
    File,
    Symlink,
    Directory,
}

// Represents a file or symlink found in the directory.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Fingerprint {
    pub file_name: String,

    pub file_type: FileType,

    // path that this symlinks to or ""
    #[serde(skip_serializing_if = "String::is_empty", default)]
    pub symlink: String,

    #[serde(skip_serializing_if = "String::is_empty", default)]
    pub digest: String,
}

#[derive(Debug, Default, PartialEq)]
pub struct Diffs {
    // Files on host, but not on device
    pub device_needs: Vec<Fingerprint>,
    // Files on device, but not host.
    pub device_extra: Vec<Fingerprint>,
    // Files that are different between host and device.
    pub device_diffs: Vec<Fingerprint>,
}

/// Compute the files that need to be added, removed or updated on the device.
/// Each file should land in of the three categories (i.e. updated, not
/// removed and added);
// Rust newbie; all the `a is about lifetimes.  Basically instead of copying
// the Entry, we are store references to it, but we have to tell rustc the
// reference we use and shove in the output won't last longer than the inputs.
#[allow(unused)]
pub fn diff(host_files: &[Fingerprint], device_files: &[Fingerprint]) -> Diffs {
    // TODO(rbraunstein): revisit implementation, can do with one pass on filenames rather than 3.
    // (i.e. what Joe is already doing)
    // Just doing some simple set math to compute diffs, code will probably change,
    // but this allows us to write some unit tests for TDD
    let host_map: HashMap<String, Fingerprint> =
        host_files.iter().map(|e| (e.file_name.clone(), e.clone())).collect();
    let device_map: HashMap<String, Fingerprint> =
        device_files.iter().map(|e| (e.file_name.clone(), e.clone())).collect();

    let host_set: HashSet<String> = host_files.iter().map(|e| e.file_name.clone()).collect();
    let device_set: HashSet<String> = device_files.iter().map(|e| e.file_name.clone()).collect();

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

/// Compute the sha256 and return it as a lowercase hex string.
// TODO(rbraunstein): Remove allow_unused after we call from code, not just tests.
#[allow(unused)]
fn compute_digest(file_path: &Path) -> Result<String, io::Error> {
    let input = fs::File::open(file_path)?;
    let mut reader = io::BufReader::new(input);
    let mut context = Context::new(&SHA256);
    let mut buffer = [0; 4096];

    loop {
        let num_bytes_read = reader.read(&mut buffer)?;
        if num_bytes_read == 0 {
            break;
        }
        context.update(&buffer[..num_bytes_read]);
    }

    Ok(encode(context.finish().as_ref()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn empty_inputs() {
        assert_eq!(diff(&Vec::new(), &Vec::new()), Diffs::default());
    }

    #[test]
    fn same_inputs() {
        let file_entry: Vec<Fingerprint> = vec![Fingerprint {
            file_name: "a/b/foo.so".to_string(),
            file_type: FileType::File,
            digest: "deadbeef".to_string(),
            symlink: "".to_string(),
        }];
        assert_eq!(diff(&file_entry, &file_entry.clone()), Diffs::default());
    }

    #[test]
    fn different_file_type() {
        let file_entry = Fingerprint {
            file_name: "a/b/foo.so".to_string(),
            file_type: FileType::File,
            digest: "deadbeef".to_string(),
            symlink: "".to_string(),
        };
        let mut dir_entry = file_entry.clone();
        dir_entry.file_type = FileType::Directory;

        // TODO(rbraunstein); The equals gives a nice error saying which field differs,
        // figure out how to check it:
        //     failures:
        //        fingerprint::different_file_type

        assert_ne!(diff(&[file_entry], &[dir_entry]), Diffs::default());
    }

    #[test]
    fn compute_digest_empty_file() {
        assert_eq!(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855".to_string(),
            compute_digest(&PathBuf::from("testdata/empty")).unwrap()
        );
    }

    #[test]
    fn compute_digest_small_file() {
        assert_eq!(
            "a519d054afdf2abfbdd90a738d248f606685d6c187e96390bde22e958240449e".to_string(),
            compute_digest(&PathBuf::from("testdata/small")).unwrap()
        );
    }

    // Generate some files near the buffer size to check for off-by-one errors
    // and compute the digest and store here.
    //   head -c 4095 /dev/urandom > testdata/4095_bytes
    //    sha256sum testdata/4095_bytes
    #[test]
    fn verify_edge_case_digests() {
        for (file_name, digest) in [
            ("4095_bytes", "6e98025b7dce0b3c40c5210573d678f7fcac895714590a57f838c16802d164c3"),
            ("4096_bytes", "684625cc0fb22cb3c4f82c82542984444dea202cc1325abf48e19230db6b75c3"),
            ("4097_bytes", "c30a5bc5bf6e1967fecd9e1b73ad52075dc15474e4e1fc06347e17722dfd14a7"),
        ] {
            let computed_digest = compute_digest(&Path::new("testdata").join(file_name)).unwrap();
            assert_eq!(
                digest.to_string(),
                computed_digest,
                "Digest for file {file_name} was computed as {computed_digest}, expected {digest}"
            );
        }
    }

    // TODO(rbraunstein): assertables crates for bags/containers.
    // TODO(rbraunstein): a bunch more tests:
}
