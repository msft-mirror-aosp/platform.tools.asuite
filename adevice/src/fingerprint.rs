//! Recursively hash the contents of a directory
use hex::encode;
use ring::digest::{Context, SHA256};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::io::{self, Read};
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum FileType {
    File,
    Symlink,
    Directory,
}

/// Represents a file, directory, or symlink.
/// We need enough information to be able to tell if:
///   1) A regular file changes to a directory or symlink.
///   2) A symlink's target file path changes.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct FileMetadata {
    pub file_type: FileType,

    // path that this symlinks to or ""
    #[serde(skip_serializing_if = "String::is_empty", default)]
    pub symlink: String,

    // sha256 of contents for regular files.
    #[serde(skip_serializing_if = "String::is_empty", default)]
    pub digest: String,
}

#[derive(Debug, Default, PartialEq)]
pub struct Diffs {
    // Files on host, but not on device
    pub device_needs: HashMap<String, FileMetadata>,
    // Files on device, but not host.
    pub device_extra: HashMap<String, FileMetadata>,
    // Files that are different between host and device.
    pub device_diffs: HashMap<String, FileMetadata>,
}

/// Compute the files that need to be added, removed or updated on the device.
/// Each file should land in of the three categories (i.e. updated, not
/// removed and added);
pub fn diff(
    host_files: &HashMap<String, FileMetadata>,
    device_files: &HashMap<String, FileMetadata>,
) -> Diffs {
    let mut diffs = Diffs {
        device_needs: HashMap::new(),
        device_extra: HashMap::new(),
        device_diffs: HashMap::new(),
    };

    // Files on the host, but not on the device or
    // file on the host that are different on the device.
    for (file_name, metadata) in host_files {
        // TODO(rbraunstein): Can I make the logic clearer without nesting?
        if let Some(device_metadata) = device_files.get(file_name) {
            if device_metadata != metadata {
                diffs.device_diffs.insert(file_name.clone(), metadata.clone());
            } else {
                // NO diff, nothing to do.
            };
        } else {
            diffs.device_needs.insert(file_name.clone(), metadata.clone());
        };
    }

    // Files on the device, but not one the host.
    for (file_name, metadata) in device_files {
        if host_files.get(file_name).is_none() {
            diffs.device_extra.insert(file_name.clone(), metadata.clone());
        }
    }
    diffs
}

#[allow(unused)]
fn fingerprint_file(file_path: &Path) -> Result<FileMetadata, io::Error> {
    let metadata = fs::symlink_metadata(file_path)?;

    if metadata.is_dir() {
        Ok(FileMetadata {
            file_type: FileType::Directory,
            symlink: String::from(""),
            digest: String::from(""),
        })
    } else if metadata.is_symlink() {
        let link = fs::read_link(file_path)?;
        // TODO(rbraunstein): Deal with multiple error types rather than use
        // unwrap and panic (on bizzare symlink target names)
        // https://doc.rust-lang.org/rust-by-example/error/multiple_error_types.html
        let target_path_string = link.into_os_string().into_string().unwrap();
        Ok(FileMetadata {
            file_type: FileType::Symlink,
            symlink: target_path_string,
            digest: String::from(""),
        })
    } else {
        Ok(FileMetadata {
            file_type: FileType::File,
            symlink: String::from(""),
            digest: compute_digest(file_path)?,
        })
    }
}

/// Compute the sha256 and return it as a lowercase hex string.
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
    use std::collections::BTreeSet;
    use std::env;
    use std::path::PathBuf;

    #[test]
    fn empty_inputs() {
        assert_eq!(diff(&HashMap::new(), &HashMap::new()), Diffs::default());
    }

    #[test]
    fn same_inputs() {
        let file_entry = HashMap::from([(
            "a/b/foo.so".to_string(),
            FileMetadata {
                file_type: FileType::File,
                digest: "deadbeef".to_string(),
                symlink: "".to_string(),
            },
        )]);
        assert_eq!(diff(&file_entry, &file_entry.clone()), Diffs::default());
    }

    #[test]
    fn different_file_type() {
        let host_map_with_filename_as_file = HashMap::from([(
            "a/b/foo.so".to_string(),
            FileMetadata {
                file_type: FileType::File,
                digest: "deadbeef".to_string(),
                symlink: "".to_string(),
            },
        )]);

        let device_map_with_filename_as_dir = HashMap::from([(
            "a/b/foo.so".to_string(),
            FileMetadata {
                file_type: FileType::Directory,
                digest: "".to_string(),
                symlink: "".to_string(),
            },
        )]);

        let diffs = diff(&host_map_with_filename_as_file, &device_map_with_filename_as_dir);
        assert_eq!(
            diffs.device_diffs.get("a/b/foo.so").expect("Missing file"),
            // `diff` returns FileMetadata for host, but we really only care that the
            // file name was found.
            &FileMetadata {
                file_type: FileType::File,
                digest: "deadbeef".to_string(),
                symlink: "".to_string(),
            },
        );
    }

    #[test]
    fn diff_simple_trees() {
        let host_map = HashMap::from([
            ("matching_file".to_string(), file_metadata("digest_matching_file")),
            ("path/to/diff_file".to_string(), file_metadata("digest_file2")),
            ("path/to/new_file".to_string(), file_metadata("digest_new_file")),
            ("same_link".to_string(), link_metadata("matching_file")),
            ("diff_link".to_string(), link_metadata("targetxx")),
            ("new_link".to_string(), link_metadata("new_target")),
            ("matching dir".to_string(), dir_metadata()),
            ("new_dir".to_string(), dir_metadata()),
        ]);

        let device_map = HashMap::from([
            ("matching_file".to_string(), file_metadata("digest_matching_file")),
            ("path/to/diff_file".to_string(), file_metadata("digest_file2_DIFF")),
            ("path/to/deleted_file".to_string(), file_metadata("digest_deleted_file")),
            ("same_link".to_string(), link_metadata("matching_file")),
            ("diff_link".to_string(), link_metadata("targetxx_DIFF")),
            ("deleted_link".to_string(), link_metadata("new_target")),
            ("matching dir".to_string(), dir_metadata()),
            ("deleted_dir".to_string(), dir_metadata()),
        ]);

        let diffs = diff(&host_map, &device_map);
        // TODO(rbraunstein): Be terser with a helper func or asserts on containers/bags.
        assert_eq!(
            BTreeSet::from_iter(diffs.device_diffs.keys()),
            BTreeSet::from([&"diff_link".to_string(), &"path/to/diff_file".to_string()])
        );
        assert_eq!(
            BTreeSet::from_iter(diffs.device_needs.keys()),
            BTreeSet::from([
                &"path/to/new_file".to_string(),
                &"new_link".to_string(),
                &"new_dir".to_string()
            ])
        );
        assert_eq!(
            BTreeSet::from_iter(diffs.device_extra.keys()),
            BTreeSet::from([
                &"path/to/deleted_file".to_string(),
                &"deleted_link".to_string(),
                &"deleted_dir".to_string()
            ])
        );
    }

    #[test]
    fn diff_different_file_names() {
        // TODO(rbraunstein): Write test for non-printable filename
        // TODO(rbraunstein): Write tests for utf8 filenames.
    }

    #[test]
    fn compute_digest_empty_file() {
        let tmpdir = tempfile::TempDir::new().unwrap();
        let file_path = tmpdir.path().join("empty_file");
        fs::write(&file_path, "").unwrap();
        assert_eq!(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855".to_string(),
            compute_digest(&file_path).unwrap()
        );
    }

    #[test]
    fn compute_digest_small_file() {
        let tmpdir = tempfile::TempDir::new().unwrap();
        let file_path = tmpdir.path().join("small_file");
        fs::write(&file_path, "This is a test\nof a small file.\n").unwrap();
        assert_eq!(
            "a519d054afdf2abfbdd90a738d248f606685d6c187e96390bde22e958240449e".to_string(),
            compute_digest(&file_path).unwrap()
        );
    }

    // Generate some files near the buffer size to check for off-by-one errors
    // and compute the digest and store here.
    // We can't check these into testdata and read from testdata unless we serialize
    // all the tests. Some tests to `cd` to create relative symlinks and that affects
    // any tests that want to read from testdata.
    #[test]
    fn verify_edge_case_digests() {
        let tmpdir = tempfile::TempDir::new().unwrap();
        // We could use a RNG with a seed, but lets just create simple files of bytes.
        let raw_bytes: &[u8; 10] = &[0, 1, 17, 200, 11, 8, 0, 32, 9, 10];
        let mut boring_buff = Vec::new();
        for _ in 1..1000 {
            boring_buff.extend_from_slice(raw_bytes);
        }

        for (num_bytes, digest) in
            &[(4095, "a0e88b2743"), (4096, "b2e324aac3"), (4097, "70fcbe6a8d")]
        {
            let file_path = tmpdir.path().join(num_bytes.to_string());
            fs::write(&file_path, &boring_buff[0..*num_bytes]).unwrap();
            assert!(
                compute_digest(&file_path).unwrap().starts_with(digest),
                "Expected file {:?} to have a digest starting with {:?}",
                file_path,
                digest
            );
        }
    }

    #[test]
    fn fingerprint_file_for_file() {
        let partition_root = tempfile::TempDir::new().unwrap();
        let file_path = partition_root.path().join("small_file");
        fs::write(&file_path, "This is a test\nof a small file.\n").unwrap();

        let entry = fingerprint_file(&file_path).unwrap();

        assert_eq!(
            FileMetadata {
                file_type: FileType::File,
                digest: "a519d054afdf2abfbdd90a738d248f606685d6c187e96390bde22e958240449e"
                    .to_string(),
                symlink: "".to_string(),
            },
            entry
        )
    }

    #[test]
    fn fingerprint_file_for_relative_symlink() {
        let partition_root = tempfile::TempDir::new().unwrap();
        let file_path = partition_root.path().join("small_file");
        fs::write(file_path, "This is a test\nof a small file.\n").unwrap();

        let link = create_symlink(
            &PathBuf::from("small_file"),
            "link_to_small_file",
            partition_root.path(),
        );

        let entry = fingerprint_file(&link).unwrap();
        assert_eq!(
            FileMetadata {
                file_type: FileType::Symlink,
                digest: "".to_string(),
                symlink: "small_file".to_string(),
            },
            entry
        )
    }

    #[test]
    fn fingerprint_file_for_absolute_symlink() {
        let partition_root = tempfile::TempDir::new().unwrap();
        let link = create_symlink(&PathBuf::from("/tmp"), "link_to_tmp", partition_root.path());

        let entry = fingerprint_file(&link).unwrap();
        assert_eq!(
            FileMetadata {
                file_type: FileType::Symlink,
                digest: "".to_string(),
                symlink: "/tmp".to_string(),
            },
            entry
        )
    }

    #[test]
    fn fingerprint_file_for_directory() {
        let partition_root = tempfile::TempDir::new().unwrap();
        let newdir_path = partition_root.path().join("some_dir");
        fs::create_dir(&newdir_path).expect("Should have create 'some_dir' in temp dir");

        let entry = fingerprint_file(&newdir_path).unwrap();
        assert_eq!(
            FileMetadata {
                file_type: FileType::Directory,
                digest: "".to_string(),
                symlink: "".to_string(),
            },
            entry
        )
    }

    #[test]
    fn fingerprint_file_on_bad_path_reports_err() {
        if fingerprint_file(Path::new("testdata/not_exist")).is_ok() {
            panic!("Should have failed on invalid path")
        }
    }

    #[test]
    fn fingerprint_file_on_dangling_symlink() {
        // TODO(rbraunstein): create two types of dangling symlinks
        // 1) relative dangling to nowhere
        // 2) absolute dangling on host to /system that would resolve on device
        // 3) not dangling ,but self link.
        // I can't submit any of these as testsdata, I need to create in the test.
        // Do it as apart of the PR where I do a fingerprint_partition test.
        // TODO(rbraunstein): investigate why adding/removing testdata files causes
        // module-info to rebuild.
    }

    // Create a symlink in `directory` named `link_name` that points to `target`.
    // Returns the absolute path to the created symlink.
    fn create_symlink(target: &Path, link_name: &str, directory: &Path) -> PathBuf {
        let orig_dir = env::current_dir().unwrap();
        env::set_current_dir(directory).expect("Could not change to dir {directory:?}");

        fs::soft_link(target, link_name)
            .unwrap_or_else(|e| println!("Could not symlink to {:?} {:?}", directory, e));

        env::set_current_dir(orig_dir).unwrap();
        directory.join(Path::new(link_name))
    }

    fn file_metadata(digest: &str) -> FileMetadata {
        FileMetadata {
            file_type: FileType::File,
            digest: digest.to_string(),
            symlink: "".to_string(),
        }
    }

    fn link_metadata(target: &str) -> FileMetadata {
        FileMetadata {
            file_type: FileType::Symlink,
            digest: target.to_string(),
            symlink: "".to_string(),
        }
    }

    fn dir_metadata() -> FileMetadata {
        FileMetadata {
            file_type: FileType::Directory,
            digest: "".to_string(),
            symlink: "".to_string(),
        }
    }

    // TODO(rbraunstein): assertables crates for bags/containers.
    // TODO(rbraunstein): a bunch more tests:
}
