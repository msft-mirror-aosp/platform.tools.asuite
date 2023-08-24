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
use commands::{run_adb_command, split_string, AdbCommand};
use env_logger::{Builder, Target};
use fingerprint::FileMetadata;
use log::info;

use std::collections::{BTreeSet, HashMap, HashSet};
use std::path::PathBuf;
use std::time::Duration;

fn main() -> Result<()> {
    let total_time = std::time::Instant::now();
    let cli = cli::Cli::parse();
    init_logger(&cli.global_options);
    let mut profiler = Profiler::default();

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
        Commands::TrackBase(base) => return config.trackbase(&base.base),
        Commands::Untrack(names) => return config.untrack(&names.modules),
        _ => (),
    }
    config.print();

    let ninja_installed_files = time!(config.tracked_files()?, profiler.ninja_deps_computer);

    info!("Stale file tracking took {} millis", track_time.elapsed().as_millis());

    let partitions: Vec<PathBuf> =
        cli.global_options.partitions.iter().map(PathBuf::from).collect();
    let device_tree =
        time!(fingerprint_device(&cli.global_options.partitions)?, profiler.device_fingerprint);

    let host_tree = time!(
        fingerprint::fingerprint_partitions(&product_out, &partitions)?,
        profiler.host_fingerprint
    );
    let commands =
        update(&device_tree, &host_tree, &ninja_installed_files, product_out.clone(), &config)?;

    if matches!(cli.command, Commands::Update) {
        // Status
        let max_changes = cli.global_options.max_allowed_changes;
        if commands.is_empty() {
            info!("Device up to date, no actions to perform.");
            return Ok(());
        }
        if commands.len() > max_changes {
            bail!("Your device needs {} changes which is more than the suggested amount of {}. Pass `--max-allowed-changes={} or consider reflashing.", commands.len(), max_changes, commands.len());
        }
        info!("Actions: {} files to update.", commands.len());

        device::update(
            &RestartChooser::from(&product_out.join("module-info.json"))?,
            &commands,
            &mut profiler,
        )?;
    }
    profiler.total = total_time.elapsed(); // Avoid wrapping the block in the macro.
    info!("{}", profiler.to_string());
    Ok(())
}

/// Returns the commands to update the device for every file that should be updated.
/// If there are errors, like some files in the staging set have not been built, then
/// an error result is returned.
fn update(
    device_tree: &HashMap<PathBuf, FileMetadata>,
    host_tree: &HashMap<PathBuf, FileMetadata>,
    ninja_installed_files: &[String],
    product_out: PathBuf,
    config: &tracking::Config,
) -> Result<HashMap<PathBuf, AdbCommand>> {
    let changes = fingerprint::diff(host_tree, device_tree);

    // NOTE: The Ninja deps list can be _ahead_of_ the product tree output list.
    //      i.e. m `nothing` will update our ninja list even before someone
    //      does a build to populate product out.
    //      We don't have a way to know if we are in this case or if the user
    //      ever did a `m droid`.

    // We add implicit dirs to the tracked set so the set matches the staging set.
    let mut ninja_installed_dirs: HashSet<PathBuf> =
        ninja_installed_files.iter().flat_map(|p| parents(p)).collect();
    ninja_installed_dirs.remove(&PathBuf::from(""));
    let tracked_set: HashSet<PathBuf> =
        ninja_installed_files.iter().map(PathBuf::from).chain(ninja_installed_dirs).collect();
    let host_set: HashSet<PathBuf> = host_tree.keys().map(PathBuf::clone).collect();
    let device_set: HashSet<PathBuf> = device_tree.keys().map(PathBuf::clone).collect();

    //  Print warnings for untracked staging and/or device files.
    print_warnings(
        &host_set.difference(&tracked_set).collect(),
        "\n * Files on Host but not part of a tracked target.",
    );
    print_warnings(
        &device_set.difference(&tracked_set).collect(),
        "\n * Files on Device but not part of a tracked target",
    );

    // Files that are in the tracked set but NOT in the build directory. These need
    // to be built.
    let needs_building: HashSet<&PathBuf> = tracked_set.difference(&host_set).collect();
    #[allow(clippy::len_zero)]
    if needs_building.len() > 0 {
        print_warnings(
            &needs_building,
            &format!(
                "These files need to be rebuilt. Please run:  m {} {:?}",
                config.base, config.modules
            ),
        );
        bail!("Please build needed modules and try again.");
    }

    // Restrict the host set down to the ones that are in the update set.
    let filtered_host_set: HashMap<PathBuf, FileMetadata> = host_tree
        .iter()
        .filter_map(|(key, value)| {
            if tracked_set.contains(key) {
                Some((key.clone(), value.clone()))
            } else {
                None
            }
        })
        .collect();

    report_diffs("Device Needs", &changes.device_needs);
    report_diffs("Outdated Device files", &changes.device_diffs);
    report_diffs("Device Extra", &changes.device_extra);
    // NOTE: We intentionally avoid deletes for now.
    let filtered_changes = fingerprint::diff(&filtered_host_set, device_tree);
    let all_filtered_commands = commands::compose(&filtered_changes, &product_out);
    Ok(all_filtered_commands.upserts)
}

fn print_warnings(set: &HashSet<&PathBuf>, msg: &str) {
    if set.is_empty() {
        return;
    }

    let mut sorted: Vec<&PathBuf> = set.iter().copied().collect();
    sorted.sort();
    println!("{msg}");
    for f in sorted {
        println!("\t{f:?}");
    }
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
    let fingerprint_result = run_adb_command(&adb_args);
    // Deal with some bootstrapping errors, like adevice_fingerprint isn't installed
    // by printing diagnostics and exiting.
    if let Err(problem) = fingerprint_result {
        if problem
            .root_cause()
            .to_string()
            // TODO(rbraunstein): Will this work in other locales?
            .contains("adevice_fingerprint: inaccessible or not found")
        {
            // If it doesn't look they are running a eng build, let them know and exit.
            if let Some(root_ins) = check_eng_build() {
                bail!("\n  Thank you for testing out adevice.\n  {root_ins}");
            }
            // Running as root, but adevice_fingerprint not found.
            // This should not happen after we tag it as an "eng" module.
            bail!("\n  Thank you for testing out adevice.\n  Please bootstrap by doing the following:\n\t ` adb remount; m adevice_fingerprint adevice && adb push $ANDROID_PRODUCT_OUT/system/bin/adevice_fingerprint system/bin/adevice_fingerprint`");
        } else {
            bail!("Unknown problem running `adevice_fingerprint` on your device: {problem:?}");
        }
    }

    let stdout = fingerprint_result.unwrap();

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

/// Check to see if the current image looks like an "eng" image and
/// return a string to with instructions.
/// There may be other properties to search for eng vs userdata:
///   https://source.android.com/docs/setup/create/new-device#build-variants
///   or just $TARGET_BUILD_VARIANT
fn check_eng_build() -> Option<String> {
    match run_adb_command(&split_string("exec-out whoami")) {
	Ok(user) if user.trim() == "root" => None,
	Ok(other_user) => Some(format!("Expected to run as user 'root', but the device is running as user '{}'.\n  Please flash an `eng` build or run commands: `adb root; adb remount; adb reboot; adb root ;adb remount`", other_user.trim())),
	Err(e) => Some(format!("Can not determine device user {e:?}"))
    }
}

fn parents(file_path: &str) -> Vec<PathBuf> {
    PathBuf::from(file_path).ancestors().map(PathBuf::from).collect()
}

#[allow(missing_docs)]
#[derive(Default)]
pub struct Profiler {
    pub device_fingerprint: Duration,
    pub host_fingerprint: Duration,
    pub ninja_deps_computer: Duration,
    pub adb_cmds: Duration,
    pub reboot: Duration,
    pub restart_after_boot: Duration,
    pub total: Duration,
}

impl std::string::ToString for Profiler {
    fn to_string(&self) -> String {
        vec![
            " Operation profile: (secs)".to_string(),
            format!("Device Fingerprint - {}", self.device_fingerprint.as_secs()),
            format!("Host fingerprint - {}", self.host_fingerprint.as_secs()),
            format!("Ninja - {}", self.ninja_deps_computer.as_secs()),
            format!("Adb Cmds - {}", self.adb_cmds.as_secs()),
            format!("Reboot - {}", self.reboot.as_secs()),
            format!("Restart - {}", self.restart_after_boot.as_secs()),
            format!("TOTAL - {}", self.total.as_secs()),
        ]
        .join("\n\t")
    }
}

fn init_logger(global_options: &cli::GlobalOptions) {
    Builder::from_default_env()
        .target(Target::Stdout)
        .format_level(false)
        .format_module_path(false)
        .format_target(false)
        // I actually want different logging channels for timing vs adb commands.
        .filter_level(match &global_options.verbose {
            cli::Verbosity::Debug => log::LevelFilter::Debug,
            cli::Verbosity::None => log::LevelFilter::Warn,
            cli::Verbosity::Details => log::LevelFilter::Info,
        })
        .write_style(env_logger::WriteStyle::Auto)
        .init();
}

/// Time how long it takes to run the function and store the
/// result in the given profiler field.
// TODO(rbraunstein): Ideally, use tracing or flamegraph crate or
// use Map rather than name all the fields.
#[macro_export]
macro_rules! time {
    ($fn:expr, $ident:expr) => {{
        let start = std::time::Instant::now();
        let result = $fn;
        $ident = start.elapsed();
        result
    }};
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::tracking::Config;
    use std::path::PathBuf;
    use tempfile::TempDir;

    // TODO(rbraunstein): Capture/test stdout and logging.
    //  Test stdout: https://users.rust-lang.org/t/how-to-test-functions-that-use-println/67188/5
    #[test]
    fn empty_inputs() -> Result<()> {
        let tmpdir = TempDir::new().unwrap();
        let home = tmpdir.path();
        let device_files: HashMap<PathBuf, FileMetadata> = HashMap::new();
        let host_files: HashMap<PathBuf, FileMetadata> = HashMap::new();
        let ninja_deps: Vec<String> = vec![];
        let product_out = PathBuf::from("");
        let config = Config::load_or_default(home.display().to_string())?;

        let results = update(&device_files, &host_files, &ninja_deps, product_out, &config)?;
        assert_eq!(results.values().len(), 0);
        Ok(())
    }

    #[test]
    fn host_and_ninja_file_not_on_device() -> Result<()> {
        let tmpdir = TempDir::new().unwrap();
        let home = tmpdir.path();

        // Relative to product out?
        let product_out = PathBuf::from("");
        let config = Config::load_or_default(home.display().to_string())?;

        let results = update(
            // Device files
            &HashMap::new(),
            // Host files
            &HashMap::from([
                (PathBuf::from("system/myfile"), file_metadata("digest1")),
                (PathBuf::from("system"), dir_metadata()),
            ]),
            // Ninja deps
            &["system".to_string(), "system/myfile".to_string()],
            product_out,
            &config,
        )?;
        assert_eq!(results.values().len(), 2);
        Ok(())
    }

    #[test]
    fn on_host_not_in_tracked_on_device() -> Result<()> {
        let results = call_update(&FakeState {
            device_data: &["system/f1"],
            host_data: &["system/f1"],
            tracked_set: &[],
        });
        assert_eq!(0, results?.values().len());
        Ok(())
    }

    #[test]
    fn in_host_not_in_tracked_not_on_device() -> Result<()> {
        let results = call_update(&FakeState {
            device_data: &[""],
            host_data: &["system/f1"],
            tracked_set: &[],
        });
        assert_eq!(0, results?.values().len());
        Ok(())
    }

    // TODO(rbraunstein): Test case where on device and up to date, but not tracked.

    struct FakeState {
        device_data: &'static [&'static str],
        host_data: &'static [&'static str],
        tracked_set: &'static [&'static str],
    }

    // Helper to call update.
    // Uses filename for the digest in the fingerprint
    // Add directories for every file on the host like walkdir would do.
    // `update` adds the directories for the tracked set so we don't do that here.
    fn call_update(fake_state: &FakeState) -> Result<HashMap<PathBuf, AdbCommand>> {
        let product_out = PathBuf::from("");
        let config = Config::fake();

        let mut device_files: HashMap<PathBuf, FileMetadata> = HashMap::new();
        let mut host_files: HashMap<PathBuf, FileMetadata> = HashMap::new();
        for d in fake_state.device_data {
            // Set the digest to the filename for now.
            device_files.insert(PathBuf::from(d), file_metadata(d));
        }
        for h in fake_state.host_data {
            // Set the digest to the filename for now.
            host_files.insert(PathBuf::from(h), file_metadata(h));
            // Add the dir too.
        }

        let tracked_set: Vec<String> =
            fake_state.tracked_set.iter().map(|s| s.to_string()).collect();

        update(&device_files, &host_files, &tracked_set, product_out, &config)
    }

    fn file_metadata(digest: &str) -> FileMetadata {
        FileMetadata {
            file_type: fingerprint::FileType::File,
            digest: digest.to_string(),
            symlink: "".to_string(),
        }
    }
    fn dir_metadata() -> FileMetadata {
        FileMetadata {
            file_type: fingerprint::FileType::Directory,
            digest: "".to_string(),
            symlink: "".to_string(),
        }
    }
}
