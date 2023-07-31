//! Update an Android device with local build changes.
mod cli;
mod fingerprint;

use anyhow::{anyhow, bail, Context, Result};
use clap::Parser;
use cli::Commands;
use fingerprint::FileMetadata;

use std::collections::{BTreeSet, HashMap};
use std::io::BufReader;
use std::path::PathBuf;
use std::process;

fn main() -> Result<()> {
    let cli = cli::Cli::parse();

    let product_out = match &cli.global_options.product_out {
        Some(po) => PathBuf::from(po),
        None => get_product_out_from_env().ok_or(anyhow!(
            "ANDROID_PRODUCT_OUT is not set. Please run source build/envsetup.sh and lunch."
        ))?,
    };

    let partitions: Vec<PathBuf> =
        cli.global_options.partitions.iter().map(PathBuf::from).collect();
    let device_tree = fingerprint_device(&cli.global_options.partitions)?;
    let build_tree = fingerprint::fingerprint_partitions(&product_out, &partitions)?;

    match &cli.command {
        Commands::Status => {
            let changes = fingerprint::diff(&build_tree, &device_tree);
            report_diffs("Device Needs", &changes.device_needs);
            report_diffs("Device Diffs", &changes.device_diffs);
            report_diffs("Device Extra", &changes.device_extra);
        }
        Commands::ShowActions => {}
        #[allow(unused)]
        Commands::UpdateDevice { verbose, reboot } => {}
    }
    Ok(())
}

fn report_diffs(category: &str, file_names: &HashMap<PathBuf, FileMetadata>) {
    let sorted_names = BTreeSet::from_iter(file_names.keys());
    println!("{category}: {} files.", sorted_names.len());

    for (index, value) in sorted_names.iter().enumerate() {
        if index > 10 {
            break;
        }
        println!("\t{}", value.display());
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

/// Given "partitions" at the root of the device,
/// return an entry for each file found.  The entry contains the
/// digest of the file contents and stat-like data about the file.
/// Typically, dirs = ["system"]
fn fingerprint_device(
    partitions: &[String],
) -> Result<HashMap<PathBuf, fingerprint::FileMetadata>> {
    let mut args =
        vec!["shell".to_string(), "/system/bin/adevice_fingerprint".to_string(), "-p".to_string()];
    args.extend_from_slice(partitions);
    let mut adb = process::Command::new("adb")
        .args(args)
        .stdout(process::Stdio::piped())
        .spawn()
        .context("Error running adb")?;
    let stdout = adb.stdout.take().ok_or(anyhow!("Unable to read stdout from adb"))?;
    let result: HashMap<String, fingerprint::FileMetadata> =
        match serde_json::from_reader(BufReader::new(stdout)) {
            Err(err) if err.line() == 1 && err.column() == 0 && err.is_eof() => {
                // This means there was no data. Print a different error, and adb
                // probably also just printed a line.
                bail!("Device didn't return any data.");
            }
            Err(err) => bail!("Error reading json {}", err),
            Ok(file_map) => file_map,
        };
    adb.wait()?;
    Ok(result.into_iter().map(|(path, metadata)| (PathBuf::from(path), metadata)).collect())
}
