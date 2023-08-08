//! Update an Android device with local build changes.
mod cli;
mod commands;
mod fingerprint;

use anyhow::{anyhow, bail, Context, Result};
use clap::Parser;
use cli::Commands;
use commands::run_adb_command;
use fingerprint::FileMetadata;

use std::collections::{BTreeSet, HashMap};
use std::path::PathBuf;

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
    let changes = fingerprint::diff(&build_tree, &device_tree);
    let all_commands = commands::compose(&changes, &product_out);
    // NOTE: We intentionally avoid deletes for now.
    let commands = &all_commands.upserts;

    match &cli.command {
        Commands::Status => {
            report_diffs("Device Needs", &changes.device_needs);
            report_diffs("Device Diffs", &changes.device_diffs);
            report_diffs("Device Extra", &changes.device_extra);
        }
        Commands::ShowActions => report_actions(commands),
        #[allow(unused)]
        Commands::Sync { dryrun, verbose, max_allowed_changes } => {
            if commands.is_empty() {
                println!("Device up to date, no actions to perform.");
                return Ok(());
            }
            println!("Actions: {} files.", commands.len());

            if (commands.len() > *max_allowed_changes) {
                bail!("Your device needs {} changes which more than the suggested amount of {}. Consider reflashing instead.", commands.len(), max_allowed_changes);
            }
            let should_print = matches!(verbose, show if *show);
            // TODO(rbraunstein): Add some notification for the deletes we are skipping.
            for command in commands.values() {
                // TODO(rbraunstein): log this to a file and clearcut, wrap this in a loggger rather
                // than sprinkle should_print.
                if should_print {
                    println!("\tRunning: adb {}", command.join(" "));
                }
                let result = commands::run_adb_command(command)?;
                if should_print {
                    println!("\t{}", result);
                }
            }
        }
    }
    Ok(())
}

fn report_diffs(category: &str, file_names: &HashMap<PathBuf, FileMetadata>) {
    let sorted_names = BTreeSet::from_iter(file_names.keys());
    println!("{category}: {} files.", sorted_names.len());

    for value in sorted_names.iter().take(10) {
        println!("\t{}", value.display());
    }
}

fn report_actions(actions: &HashMap<PathBuf, Vec<String>>) {
    let action_files = BTreeSet::from_iter(actions.keys());
    println!("Actions: {} files.", action_files.len());

    for value in action_files.iter().take(10) {
        println!("\tadb {}", actions.get(value.to_owned()).expect("missing lookup").join(" "));
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
    let mut adb_args =
        vec!["shell".to_string(), "/system/bin/adevice_fingerprint".to_string(), "-p".to_string()];
    adb_args.extend_from_slice(partitions);
    let stdout = run_adb_command(&adb_args)?;
    let result: HashMap<String, fingerprint::FileMetadata> = match serde_json::from_str(&stdout) {
        Err(err) if err.line() == 1 && err.column() == 0 && err.is_eof() => {
            // This means there was no data. Print a different error, and adb
            // probably also just printed a line.
            bail!("Device didn't return any data.");
        }
        Err(err) => return Err(err).context("Error reading json"),
        Ok(file_map) => file_map,
    };
    Ok(result.into_iter().map(|(path, metadata)| (PathBuf::from(path), metadata)).collect())
}
