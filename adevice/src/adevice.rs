//! Update an Android device with local build changes.
mod cli;
mod commands;
mod device;
mod fingerprint;
mod logger;
mod restart_chooser;
mod tracking;

use crate::restart_chooser::RestartChooser;
use anyhow::{anyhow, bail, Context, Result};
use clap::Parser;
use cli::Commands;
use commands::{run_adb_command, split_string};
use fingerprint::FileMetadata;
use itertools::Itertools;
use log::{debug, info};

use std::collections::{HashMap, HashSet};
use std::io::stdin;
use std::path::PathBuf;
use std::time::Duration;

fn main() -> Result<()> {
    let total_time = std::time::Instant::now();
    let cli = cli::Cli::parse();
    logger::init_logger(&cli.global_options);
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

    println!(" * Checking for files to push to device");
    let ninja_installed_files = time!(config.tracked_files()?, profiler.ninja_deps_computer);

    debug!("Stale file tracking took {} millis", track_time.elapsed().as_millis());

    let partitions: Vec<PathBuf> =
        cli.global_options.partitions.iter().map(PathBuf::from).collect();
    let device_tree =
        time!(fingerprint_device(&cli.global_options.partitions)?, profiler.device_fingerprint);

    let host_tree = time!(
        fingerprint::fingerprint_partitions(&product_out, &partitions)?,
        profiler.host_fingerprint
    );
    let commands = get_update_commands(
        &device_tree,
        &host_tree,
        &ninja_installed_files,
        product_out.clone(),
        &config,
    )?;

    let max_changes = cli.global_options.max_allowed_changes;
    if matches!(cli.command, Commands::CleanDevice { .. }) {
        let deletes = commands.deletes;
        if deletes.is_empty() {
            println!("   Nothing to clean.");
            return Ok(());
        }
        if deletes.len() > max_changes {
            bail!("Your device would have {} files deleted is more than the suggested amount of {}. Pass `--max-allowed-changes={} or consider reflashing.", deletes.len(), max_changes, deletes.len());
        }
        if matches!(cli.command, Commands::CleanDevice { force } if !force) {
            println!(
                "You are about to delete {} [untracked pushed] files. Are you sure? y/N",
                deletes.len()
            );
            let mut should_delete = String::new();
            stdin().read_line(&mut should_delete)?;
            if should_delete.trim().to_lowercase() != "y" {
                bail!("Not deleting");
            }
        }

        // Consider always reboot instead of soft restart after a clean.
        let restart_chooser = &RestartChooser::from(&product_out.join("module-info.json"))?;
        device::update(restart_chooser, &deletes, &mut profiler)?;
    }

    if matches!(cli.command, Commands::Update) {
        let upserts = commands.upserts;
        // Status
        if upserts.is_empty() {
            println!("   Device already up to date.");
            return Ok(());
        }
        if upserts.len() > max_changes {
            bail!("Your device needs {} changes which is more than the suggested amount of {}. Pass `--max-allowed-changes={} or consider reflashing.", upserts.len(), max_changes, upserts.len());
        }
        println!(" * Updating {} files on device.", upserts.len());

        device::update(
            &RestartChooser::from(&product_out.join("module-info.json"))?,
            &upserts,
            &mut profiler,
        )?;
    }
    profiler.total = total_time.elapsed(); // Avoid wrapping the block in the macro.
    info!("Finished in {} secs", profiler.total.as_secs());
    debug!("{}", profiler.to_string());
    Ok(())
}

/// Returns the commands to update the device for every file that should be updated.
/// If there are errors, like some files in the staging set have not been built, then
/// an error result is returned.
fn get_update_commands(
    device_tree: &HashMap<PathBuf, FileMetadata>,
    host_tree: &HashMap<PathBuf, FileMetadata>,
    ninja_installed_files: &[String],
    product_out: PathBuf,
    _config: &tracking::Config,
) -> Result<commands::Commands> {
    // NOTE: The Ninja deps list can be _ahead_of_ the product tree output list.
    //      i.e. m `nothing` will update our ninja list even before someone
    //      does a build to populate product out.
    //      We don't have a way to know if we are in this case or if the user
    //      ever did a `m droid`

    // We add implicit dirs to the tracked set so the set matches the staging set.
    let mut ninja_installed_dirs: HashSet<PathBuf> =
        ninja_installed_files.iter().flat_map(|p| parents(p)).collect();
    ninja_installed_dirs.remove(&PathBuf::from(""));
    let tracked_set: HashSet<PathBuf> =
        ninja_installed_files.iter().map(PathBuf::from).chain(ninja_installed_dirs).collect();
    let host_set: HashSet<PathBuf> = host_tree.keys().map(PathBuf::clone).collect();

    // Files that are in the tracked set but NOT in the build directory. These need
    // to be built.
    let needs_building: HashSet<&PathBuf> = tracked_set.difference(&host_set).collect();
    print_status(&collect_status_per_file(&tracked_set, host_tree, device_tree));

    #[allow(clippy::len_zero)]
    if needs_building.len() > 0 {
        bail!("Please build needed modules before updating.");
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

    let filtered_changes = fingerprint::diff(&filtered_host_set, device_tree);
    Ok(commands::compose(&filtered_changes, &product_out))
}

#[derive(Clone, PartialEq)]
enum PushState {
    Push,
    /// File is tracked and the device and host fingerprints match.
    UpToDate,
    /// File is not tracked but exists on device and host.
    TrackOrClean,
    /// File is on the device, but not host and not tracked.
    TrackAndBuildOrClean,
    /// File is tracked and on host but not on device.
    //PushNew,
    /// File is on host, but not tracked and not on device.
    TrackOrMakeClean,
    /// File is tracked and on the device, but is not in the build tree.
    /// `m` the module to build it.
    UntrackOrBuild,
}

impl PushState {
    /// Message to print indicating what actions the user should take based on the
    /// state of the file.
    pub fn get_action_msg(self) -> &'static str {
        match self {
	    PushState::Push => "Ready to push:\n  (These files are out of date on the device and will be pushed when you run `adevice update`)",
	    // Note: we don't print up to date files.
	    PushState::UpToDate => "Up to date:  (These files are up to date on the device. There is nothing to do.)",
	    PushState::TrackOrClean => "Untracked pushed files:\n  (These files are not tracked but exist on the device and host.)\n  (Use `adevice track` for the appropriate module to have them pushed.)",
	    PushState::TrackAndBuildOrClean => "Stale device files:\n  (These files are on the device, but not built or tracked.)\n  (You might want to run `adevice clean` to remove them.)",
	    PushState::TrackOrMakeClean => "Untracked built files:\n  (These files are in the build tree but not tracked or on the device.)\n  (You might want to `adevice track` the module.  It is safe to do nothing.)",
	    PushState::UntrackOrBuild => "Unbuilt files:\n  (These files should be rebuilt.)\n  (Rebuild and `adevice update`)",
	}
    }
}

/// Group each file by state and print the state message followed by the files in that state.
fn print_status(files: &HashMap<PathBuf, PushState>) {
    for state in [
        PushState::Push,
        // Skip UpToDat, don't print those.
        PushState::TrackOrClean,
        PushState::TrackAndBuildOrClean,
        PushState::TrackOrMakeClean,
        PushState::UntrackOrBuild,
    ] {
        print_files_in_state(files, state);
    }
}

/// Go through all files that exist on the host, device, and tracking set.
/// Ignore any file that is in all three and has the same fingerprint on the host and device.
/// States where the user should take action:
///   Build
///   Clean
///   Track
///   Untrack
fn collect_status_per_file(
    tracked_set: &HashSet<PathBuf>,
    host_tree: &HashMap<PathBuf, FileMetadata>,
    device_tree: &HashMap<PathBuf, FileMetadata>,
) -> HashMap<PathBuf, PushState> {
    let all_files: Vec<&PathBuf> =
        host_tree.keys().chain(device_tree.keys()).chain(tracked_set.iter()).collect();
    let mut states: HashMap<PathBuf, PushState> = HashMap::new();
    for f in all_files
        .iter()
        .sorted_by(|a, b| a.display().to_string().cmp(&b.display().to_string()))
        .dedup()
    {
        let on_device = device_tree.contains_key(*f);
        let on_host = host_tree.contains_key(*f);
        let tracked = tracked_set.contains(*f);

        // I think keeping tracked/untracked else is clearer than collapsing.
        #[allow(clippy::collapsible_else_if)]
        let push_state = if tracked {
            if on_device && on_host {
                if device_tree.get(*f) != host_tree.get(*f) {
                    // PushDiff
                    PushState::Push
                } else {
                    // else normal case, do nonthing
                    PushState::UpToDate
                }
            } else if !on_host {
                // We don't care if it is on the device or not, it has to built if it isn't
                // on the host.
                PushState::UntrackOrBuild
            } else {
                assert!(
                    !on_device && on_host,
                    "Unexpected state for file: {f:?}, tracked: {tracked} on_device: {on_device}, on_host: {on_host}"
                );
                // PushNew
                PushState::Push
            }
        } else {
            if on_device && on_host {
                PushState::TrackOrClean
            } else if on_device && !on_host {
                PushState::TrackAndBuildOrClean
            } else {
                // Note: case of !tracked, !on_host, !on_device is not possible.
                // So only one case left.
                assert!(
                    !on_device && on_host,
                    "Unexpected state for file: {f:?}, tracked: {tracked} on_device: {on_device}, on_host: {on_host}"
                );
                PushState::TrackOrMakeClean
            }
        };

        states.insert(PathBuf::from(f), push_state);
    }
    states
}

/// Find all files in a given state, and if that file list is not empty, print the
/// state message and all the files (sorted).
fn print_files_in_state(files: &HashMap<PathBuf, PushState>, push_state: PushState) {
    let filtered_files: HashMap<&PathBuf, &PushState> =
        files.iter().filter(|(_, state)| *state == &push_state).collect();

    if filtered_files.is_empty() {
        return;
    }
    println!("{}", push_state.get_action_msg());
    filtered_files.keys().sorted().for_each(|path| println!("\t{}", path.display()));
    println!();
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
        [
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

        let results =
            get_update_commands(&device_files, &host_files, &ninja_deps, product_out, &config)?;
        assert_eq!(results.upserts.values().len(), 0);
        Ok(())
    }

    #[test]
    fn host_and_ninja_file_not_on_device() -> Result<()> {
        let tmpdir = TempDir::new().unwrap();
        let home = tmpdir.path();

        // Relative to product out?
        let product_out = PathBuf::from("");
        let config = Config::load_or_default(home.display().to_string())?;

        let results = get_update_commands(
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
        assert_eq!(results.upserts.values().len(), 2);
        Ok(())
    }

    #[test]
    fn on_host_not_in_tracked_on_device() -> Result<()> {
        let results = call_update(&FakeState {
            device_data: &["system/f1"],
            host_data: &["system/f1"],
            tracked_set: &[],
        })?
        .upserts;
        assert_eq!(0, results.values().len());
        Ok(())
    }

    #[test]
    fn in_host_not_in_tracked_not_on_device() -> Result<()> {
        let results = call_update(&FakeState {
            device_data: &[""],
            host_data: &["system/f1"],
            tracked_set: &[],
        })?
        .upserts;
        assert_eq!(0, results.values().len());
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
    fn call_update(fake_state: &FakeState) -> Result<commands::Commands> {
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

        get_update_commands(&device_files, &host_files, &tracked_set, product_out, &config)
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
    // TODO(rbraunstein): Add tests for collect_status_per_file after we decide on output.
}
