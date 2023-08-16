//! Update an Android device with local build changes.
mod cli;
mod commands;
mod device;
mod fingerprint;
mod restart_chooser;

use crate::restart_chooser::RestartChooser;
use anyhow::{anyhow, bail, Context, Result};
use clap::Parser;
use cli::Commands;
use commands::run_adb_command;
use env_logger::{Builder, Target};
use fingerprint::FileMetadata;
use log::{debug, info};

use std::collections::{BTreeSet, HashMap};
use std::path::PathBuf;

fn main() -> Result<()> {
    let cli = cli::Cli::parse();
    init_logger(&cli.global_options);

    let product_out = match &cli.global_options.product_out {
        Some(po) => PathBuf::from(po),
        None => get_product_out_from_env().ok_or(anyhow!(
            "ANDROID_PRODUCT_OUT is not set. Please run source build/envsetup.sh and lunch."
        ))?,
    };

    let partitions: Vec<PathBuf> =
        cli.global_options.partitions.iter().map(PathBuf::from).collect();
    let now = std::time::Instant::now();
    let device_tree = fingerprint_device(&cli.global_options.partitions)?;
    debug!("fingerprinting device took {} millis", now.elapsed().as_millis());

    let build_tree = fingerprint::fingerprint_partitions(&product_out, &partitions)?;
    let changes = fingerprint::diff(&build_tree, &device_tree);
    let all_commands = commands::compose(&changes, &product_out);
    // NOTE: We intentionally avoid deletes for now.
    let commands = &all_commands.upserts;

    if matches!(cli.command, Commands::Update) {
        if commands.is_empty() {
            info!("Device up to date, no actions to perform.");
            return Ok(());
        }
        if commands.len() > cli.global_options.max_allowed_changes {
            bail!("Your device needs {} changes which is more than the suggested amount of {}. Consider reflashing instead.", commands.len(), cli.global_options.max_allowed_changes);
        }
    }

    match &cli.command {
        Commands::Status => {
            report_diffs("Device Needs", &changes.device_needs);
            report_diffs("Device Diffs", &changes.device_diffs);
            report_diffs("Device Extra", &changes.device_extra);
        }
        // TODO(rbraunstein): Show reboot/wait commands too.
        Commands::ShowActions => report_actions(commands),

        Commands::Update => {
            // TODO(rbraunstein): Add some notification for the deletes we are skipping.
            info!("Actions: {} files.", commands.len());
            device::update(
                &RestartChooser::from(&product_out.join("module-info.json"))?,
                commands,
            )?;
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
    // -p system,system_ext
    adb_args.push(partitions.join(","));
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

fn init_logger(global_options: &cli::GlobalOptions) {
    Builder::from_default_env()
        .target(Target::Stdout)
        .format_level(false)
        .format_module_path(false)
        .format_target(false)
        // TODO(rbraunstein): Change to single verbose option.
        .filter_level(match &global_options.debug {
            true => log::LevelFilter::Debug,
            false => match &global_options.verbose {
                true => log::LevelFilter::Info,
                false => log::LevelFilter::Warn,
            },
        })
        .write_style(env_logger::WriteStyle::Auto)
        .init();
}
