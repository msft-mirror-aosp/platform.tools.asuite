//! Update an Android device with local build changes.
mod cli;
mod commands;
mod device;
mod fingerprint;
mod restart_chooser;
mod tracking;

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
    let total_time = std::time::Instant::now();
    let cli = cli::Cli::parse();
    init_logger(&cli.global_options);

    let product_out = match &cli.global_options.product_out {
        Some(po) => PathBuf::from(po),
        None => get_product_out_from_env().ok_or(anyhow!(
            "ANDROID_PRODUCT_OUT is not set. Please run source build/envsetup.sh and lunch."
        ))?,
    };

    let track_time = std::time::Instant::now();
    let home = std::env::var("HOME").context("HOME env variable must be set.")?;
    let mut config = tracking::Config::load_or_default(home)?;

    // Early return for track/untrack commands.
    match cli.command {
        Commands::Track(names) => return config.track(&names.modules),
        Commands::Untrack(names) => return config.untrack(&names.modules),
        _ => (),
    }
    config.print();

    let droid_installed_files = config.tracked_files()?;

    debug!("IF: {:?}", droid_installed_files.len());
    info!("Stale file tracking took {} millis", track_time.elapsed().as_millis());

    let partitions: Vec<PathBuf> =
        cli.global_options.partitions.iter().map(PathBuf::from).collect();
    let now = std::time::Instant::now();
    let device_tree = fingerprint_device(&cli.global_options.partitions)?;
    info!("Fingerprinting device took {} millis", now.elapsed().as_millis());

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
            diff_base_with_build_tree(&droid_installed_files, &build_tree);
            report_diffs("Device Needs", &changes.device_needs);
            report_diffs("Device Diffs", &changes.device_diffs);
            report_diffs("Device Extra", &changes.device_extra);
        }
        Commands::Update => {
            // TODO(rbraunstein): Add some notification for the deletes we are skipping.
            info!("Actions: {} files.", commands.len());
            device::update(
                &RestartChooser::from(&product_out.join("module-info.json"))?,
                commands,
            )?;
        }
        _ => (),
    }
    info!("Total update time {} secs", total_time.elapsed().as_secs());
    Ok(())
}

/// Given the set of installed files derived from modules we track
/// and the set of files found in the Product Out tree on the host,
/// Print the files on the host that are not in the installed set.
/// Also print the files in the installed set that are not on the host.
fn diff_base_with_build_tree(
    droid_installed_files: &[String],
    build_tree: &HashMap<PathBuf, FileMetadata>,
) {
    let build_sorted_names: BTreeSet<PathBuf> = BTreeSet::from_iter(
        build_tree
            .iter()
            .filter_map(|(key, metadata)| {
                if metadata.file_type != fingerprint::FileType::Directory {
                    Some(PathBuf::from(key))
                } else {
                    None
                }
            })
            .collect::<BTreeSet<PathBuf>>(),
    );
    let droid_sorted_names: BTreeSet<PathBuf> = BTreeSet::from_iter(
        droid_installed_files.iter().map(PathBuf::from).collect::<BTreeSet<PathBuf>>(),
    );

    let build_extra: Vec<PathBuf> =
        build_sorted_names.difference(&droid_sorted_names).cloned().collect();
    println!("BUILD (build out tree #files: {}) HAS: {build_extra:?}", build_sorted_names.len());

    let droid_extra: Vec<PathBuf> =
        droid_sorted_names.difference(&build_sorted_names).cloned().collect();
    println!("DROID (sync-set #files: {}) HAS: {droid_extra:?}", droid_sorted_names.len());
}

fn report_diffs(category: &str, file_names: &HashMap<PathBuf, FileMetadata>) {
    let sorted_names = BTreeSet::from_iter(file_names.keys());
    println!("{category}: {} files.", sorted_names.len());

    for value in sorted_names.iter().take(10) {
        println!("\t{}", value.display());
    }
}

fn get_product_out_from_env() -> Option<PathBuf> {
    match std::env::var("ANDROID_PRODUCT_OUT") {
        Ok(x) if !x.is_empty() => Some(PathBuf::from(x)),
        _ => None,
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
        // I actually want different logging channels for timing vs adb commands.
        .filter_level(match &global_options.verbose {
            cli::Verbosity::Debugging => log::LevelFilter::Debug,
            cli::Verbosity::None => log::LevelFilter::Warn,
            cli::Verbosity::Details => log::LevelFilter::Info,
        })
        .write_style(env_logger::WriteStyle::Auto)
        .init();
}
