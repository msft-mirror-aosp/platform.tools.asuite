//! Update an Android device with local build changes.
mod cli;
mod fingerprint;

use clap::Parser;
use cli::Commands;

use std::collections::HashMap;
use std::io::{self, Write};
use std::path::{Path, PathBuf};

// TODO(rbraunstein): Remove all allow(unused) when implementing functions.
#[allow(unused)]
fn main() {
    let adb = Adb {};
    let cli = cli::Cli::parse();

    let product_out = match &cli.global_options.product_out {
        Some(po) => PathBuf::from(po),
        None => get_product_out_from_env()
            .ok_or("ANDROID_PRODUCT_OUT is not set. Please run source build/envsetup.sh and lunch.")
            .unwrap(),
    };

    let device_tree = fingerprint_device(&cli.global_options.partitions, &adb).unwrap();
    let build_tree =
        fingerprint_host_product_out(&cli.global_options.partitions, &product_out).unwrap();
    match &cli.command {
        Commands::Status => {
            let changes = fingerprint::diff(&build_tree, &device_tree);
            io::stdout().write_all(&format!("{changes:?}").into_bytes());
        }
        Commands::ShowActions => {}
        Commands::UpdateDevice { verbose, reboot } => {}
    }
}

fn get_product_out_from_env() -> Option<PathBuf> {
    match std::env::var("ANDROID_PRODUCT_OUT") {
        Ok(x) => {
            if x.is_empty() {
                None
            } else {
                // TODO(rbraunstein); remove trailing slash?
                Some(PathBuf::from(x))
            }
        }
        Err(_) => None,
    }
}

/// Given partitions in the top level of the product out directory,
/// return an entry for each file in the partition.  The entry contains the
/// digest of the file contents and stat-like data about the file.
/// Typically, dirs = ["system"]
#[allow(unused)]
fn fingerprint_host_product_out(
    partitions: &[String],
    product_out: &Path,
) -> Result<HashMap<String, fingerprint::FileMetadata>, String> {
    Err("use fingerprint command in upcoming PR".to_string())
}

/// Given "partitions" at the root of the device,
/// return an entry for each file found.  The entry contains the
/// digest of the file contents and stat-like data about the file.
/// Typically, dirs = ["system"]
#[allow(unused)]
fn fingerprint_device(
    partitions: &[String],
    adb: &Adb,
) -> Result<HashMap<String, fingerprint::FileMetadata>, String> {
    // Call our helper binary running on device, return errors if we can't contact it.
    Err("use adb hashdevice command in upcoming PR".to_string())
}

struct Adb {
    // Just a placeholder for now.
}
