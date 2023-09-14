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
use commands::run_adb_command;
use fingerprint::FileMetadata;
use itertools::Itertools;
use lazy_static::lazy_static;
use log::{debug, info};
use regex::Regex;

use std::collections::{HashMap, HashSet};
use std::ffi::OsString;
use std::io::stdin;
use std::path::{Path, PathBuf};
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
        &get_installed_apks()?,
    )?;

    let max_changes = cli.global_options.max_allowed_changes;
    if matches!(cli.command, Commands::Clean { .. }) {
        let deletes = commands.deletes;
        if deletes.is_empty() {
            println!("   Nothing to clean.");
            return Ok(());
        }
        if deletes.len() > max_changes {
            bail!("There are {} files to be deleted which exceeds the configured limit of {}.\n  It is recommended that you reimage your device instead.  For small increases in the limit, you can run `adevice clean --max-allowed-changes={}.", deletes.len(), max_changes, deletes.len());
        }
        if matches!(cli.command, Commands::Clean { force } if !force) {
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
            bail!("There are {} files out of date on the device, which exceeds the configured limit of {}.\n  It is recommended to reimage your device.  For small increases in the limit, you can run `adevice update --max-allowed-changes={}.", upserts.len(), max_changes, upserts.len());
        }
        println!(" * Updating {} files on device.", upserts.len());

        // Send the update commands, but retry once if we need to remount rw an extra time after a flash.
        for retry in 0..=1 {
            let update_result = device::update(
                &RestartChooser::from(&product_out.join("module-info.json"))?,
                &upserts,
                &mut profiler,
            );
            if update_result.is_ok() {
                break;
            }

            if let Err(problem) = update_result {
                if retry == 1 {
                    bail!(" !! Not expecting errors after a retry.|n  Error:{:?}", problem);
                }
                // TODO(rbraunstein): Avoid string checks. Either check mounts directly for this case
                // or return json with the error message and code from adevice_fingerprint.
                if problem.root_cause().to_string().contains("Read-only file system") {
                    println!(" !! The device has a read-only file system.\n !! After a fresh image, the device needs an extra `remount` and `reboot` to adb push files.  Performing the remount and reboot now.");
                }
                // We already did the remount, but it doesn't hurt to do it again.
                run_adb_command(&vec!["remount".to_string()])?;
                run_adb_command(&vec!["reboot".to_string()])?;
                device::wait()?;
                run_adb_command(&vec!["root".to_string()])?;
            }
            println!("\n * Trying update again after remount and reboot.");
        }
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
    installed_packages: &HashSet<String>,
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
    let status_per_file = &collect_status_per_file(
        &tracked_set,
        host_tree,
        device_tree,
        &product_out,
        installed_packages,
    )?;
    print_status(status_per_file);
    // Shadowing apks are apks that are installed outside the system partition with `adb install`
    // If they exist, we should not push the apk that would be shadowed.
    let shadowing_apks: HashSet<&PathBuf> = status_per_file
        .iter()
        .filter_map(
            |(path, push_state)| {
                if *push_state == PushState::ApkInstalled {
                    Some(path)
                } else {
                    None
                }
            },
        )
        .collect();

    #[allow(clippy::len_zero)]
    if needs_building.len() > 0 {
        println!("WARNING: Please build needed [unbuilt] modules before updating.");
    }

    // Restrict the host set down to the ones that are in the tracked set and not installed in the data partition.
    let filtered_host_set: HashMap<PathBuf, FileMetadata> = host_tree
        .iter()
        .filter_map(|(key, value)| {
            if tracked_set.contains(key) && !shadowing_apks.contains(key) {
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
    /// The apk was `installed` on top of the system image.  It will shadow any push
    /// we make to the system partitions.  It should be explicitly installed or uninstalled, not pushed.
    // TODO(rbraunstein): Store package name and path to file on disk so we can print a better
    // message to the user.
    ApkInstalled,
}

impl PushState {
    /// Message to print indicating what actions the user should take based on the
    /// state of the file.
    pub fn get_action_msg(self) -> String {
        match self {
	    PushState::Push => "Ready to push:\n  (These files are out of date on the device and will be pushed when you run `adevice update`)".to_string(),
	    // Note: we don't print up to date files.
	    PushState::UpToDate => "Up to date:  (These files are up to date on the device. There is nothing to do.)".to_string(),
	    PushState::TrackOrClean => "Untracked pushed files:\n  (These files are not tracked but exist on the device and host.)\n  (Use `adevice track` for the appropriate module to have them pushed.)".to_string(),
	    PushState::TrackAndBuildOrClean => "Stale device files:\n  (These files are on the device, but not built or tracked.)\n  (You might want to run `adevice clean` to remove them.)".to_string(),
	    PushState::TrackOrMakeClean => "Untracked built files:\n  (These files are in the build tree but not tracked or on the device.)\n  (You might want to `adevice track` the module.  It is safe to do nothing.)".to_string(),
	    PushState::UntrackOrBuild => "Unbuilt files:\n  (These files should be built so the device can be updated.)\n  (Rebuild and `adevice update`)".to_string(),
	    PushState::ApkInstalled => format!("ADB Installed files:\n{RED_WARNING_LINE}  (These files were installed with `adb install` or similar.  Pushing to the system partition will not make them available.)\n  (Either `adb uninstall` the package or `adb install` by hand.`)"),
	}
    }
}

// TODO(rbraunstein): Create a struct for each of the sections above for better formatting.
const RED_WARNING_LINE: &str = "  \x1b[1;31m!! Warning: !!\x1b[0m\n";

/// Group each file by state and print the state message followed by the files in that state.
fn print_status(files: &HashMap<PathBuf, PushState>) {
    for state in [
        PushState::Push,
        // Skip UpToDat, don't print those.
        PushState::TrackOrClean,
        PushState::TrackAndBuildOrClean,
        PushState::TrackOrMakeClean,
        PushState::UntrackOrBuild,
        PushState::ApkInstalled,
    ] {
        print_files_in_state(files, state);
    }
}

/// Determine if file is an apk and decide if we need to give a warning
/// about pushing to a system directory because it is already installed in /data
/// and will shadow a system apk if we push it.
fn installed_apk_action(
    file: &Path,
    product_out: &Path,
    installed_packages: &HashSet<String>,
) -> Result<PushState> {
    if file.extension() != Some(OsString::from("apk").as_os_str()) {
        return Ok(PushState::Push);
    }
    // See if this file was installed.
    if is_apk_installed(&product_out.join(file), installed_packages)? {
        Ok(PushState::ApkInstalled)
    } else {
        Ok(PushState::Push)
    }
}

/// Determine if the given apk has been installed via `adb install`.
/// This will allow us to decide if pushing to /system will cause problems because the
/// version we push would be shadowed by the `installed` version.
/// Run PackageManager commands from the shell to check if something is installed.
/// If this is a problem, we can build something in to adevice_fingerprint that
/// calls PackageManager#getInstalledApplications.
/// adb exec-out pm list packages  -s -f
fn is_apk_installed(host_path: &Path, installed_packages: &HashSet<String>) -> Result<bool> {
    let host_apk_path = host_path.as_os_str().to_str().unwrap();
    let aapt_output = std::process::Command::new("aapt")
        .args(["dump", "permissions", host_apk_path])
        .output()
        .context("Running appt on host to see if apk installed")?;

    if !aapt_output.status.success() {
        let stderr = String::from_utf8(aapt_output.stderr)?;
        bail!("Unable to run aapt to get installed packages {:?}", stderr);
    }

    match package_from_aapt_dump_output(aapt_output.stdout) {
        Ok(package) => {
            debug!("AAPT dump found package: {package}");
            Ok(installed_packages.contains(&package))
        }
        Err(e) => bail!("Unable to run aapt to get package information {e:?}"),
    }
}

lazy_static! {
    static ref AAPT_PACKAGE_MATCHER: Regex =
        Regex::new(r"^package: (.+)$").expect("regex does not compile");

    // Sample output, one installed, one not:
    // % adb exec-out pm list packages  -s -f  | grep shell
    //   package:/product/app/Browser2/Browser2.apk=org.chromium.webview_shell
    //   package:/data/app/~~PxHDtZDEgAeYwRyl-R3bmQ==/com.android.shell--R0z7ITsapIPKnt4BT0xkg==/base.apk=com.android.shell
    // # capture the package name (com.android.shell)
    static ref PM_LIST_PACKAGE_MATCHER: Regex =
        Regex::new(r"^package:/data/app/.*/base.apk=(.+)$").expect("regex does not compile");
}

/// Filter aapt dump output to parse out the package name for the apk.
fn package_from_aapt_dump_output(stdout: Vec<u8>) -> Result<String> {
    let package_match = String::from_utf8(stdout)?
        .lines()
        .filter_map(|line| AAPT_PACKAGE_MATCHER.captures(line).map(|x| x[1].to_string()))
        .collect();
    Ok(package_match)
}

/// Filter package manager output to figure out if the apk is installed in /data.
fn apks_from_pm_list_output(stdout: Vec<u8>) -> Result<HashSet<String>> {
    let package_match = String::from_utf8(stdout)?
        .lines()
        .filter_map(|line| PM_LIST_PACKAGE_MATCHER.captures(line).map(|x| x[1].to_string()))
        .collect();
    Ok(package_match)
}

/// Get the apks that are installed (i.e. with `adb install`)
/// Count anything in the /data partition as installed.
fn get_installed_apks() -> Result<HashSet<String>> {
    // TODO(rbraunstein): See if there is a better way to do this that doesn't look for /data
    let package_manager_output = std::process::Command::new("adb")
        .args(["exec-out", "pm", "list", "packages", "-s", "-f"])
        .output()
        .context("Running appt on host to see if apk installed")?;

    if !package_manager_output.status.success() {
        let stderr = String::from_utf8(package_manager_output.stderr)?;
        bail!("Unable to pm list packages get installed packages {:?}", stderr);
    }

    match apks_from_pm_list_output(package_manager_output.stdout) {
        Ok(packages) => {
            debug!("adb pm list packages found packages: {packages:?}");
            Ok(packages)
        }
        Err(e) => bail!("Unable to run aapt to get package information {e:?}"),
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
    product_out: &Path,
    installed_packages: &HashSet<String>,
) -> Result<HashMap<PathBuf, PushState>> {
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
                    installed_apk_action(f, product_out, installed_packages)?
                } else {
                    // Else normal case, do nothing.
                    // TODO(rbraunstein): Do we need to check for installed apk and warn.
                    // 1) User updates apk
                    // 2) User adb install
                    // 3) User reverts code and builds
                    //   (host and device match but installed apk shadows system version).
                    // For now, don't look for extra problems.
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
                // TODO(rbraunstein): Is it possible for an apk to be adb installed, but not in the system image?
                // I guess so, but seems weird.  Add check InstalledApk here too.
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
    Ok(states)
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
    // Ensure we are root or we can't read some files.
    // In userdebug builds, every reboot reverts back to the "shell" user.
    run_adb_command(&vec!["root".to_string()])?;
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
            // Running as root, but adevice_fingerprint not found.
            // This should not happen after we tag it as an "eng" module.
            bail!("\n  Thank you for testing out adevice.\n  Flashing a recent image should install the needed `adevice_fingerprint` binary.\n  Otherwise, you can bootstrap by doing the following:\n\t ` adb remount; m adevice_fingerprint adevice && adb push $ANDROID_PRODUCT_OUT/system/bin/adevice_fingerprint system/bin/adevice_fingerprint`");
        } else {
            bail!("Unknown problem running `adevice_fingerprint` on your device: {problem:?}.\n  Your device may still be in a booting state.  Try `adb get-state` to start debugging.");
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
    use std::path::PathBuf;

    // TODO(rbraunstein): Capture/test stdout and logging.
    //  Test stdout: https://users.rust-lang.org/t/how-to-test-functions-that-use-println/67188/5
    #[test]
    fn empty_inputs() -> Result<()> {
        let device_files: HashMap<PathBuf, FileMetadata> = HashMap::new();
        let host_files: HashMap<PathBuf, FileMetadata> = HashMap::new();
        let ninja_deps: Vec<String> = vec![];
        let product_out = PathBuf::from("");
        let installed_apks = HashSet::<String>::new();

        let results = get_update_commands(
            &device_files,
            &host_files,
            &ninja_deps,
            product_out,
            &installed_apks,
        )?;
        assert_eq!(results.upserts.values().len(), 0);
        Ok(())
    }

    #[test]
    fn host_and_ninja_file_not_on_device() -> Result<()> {
        // Relative to product out?
        let product_out = PathBuf::from("");
        let installed_apks = HashSet::<String>::new();

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
            &installed_apks,
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

    #[test]
    fn package_manager_output_parsing() -> Result<()> {
        let actual_output = r#"
package:/product/app/Browser2/Browser2.apk=org.chromium.webview_shell
package:/apex/com.google.aosp_cf_phone.rros/overlay/cuttlefish_overlay_frameworks_base_core.apk=android.cuttlefish.overlay
package:/data/app/~~f_ZzeFPKma_EfXRklotqFg==/com.android.shell-hrjEOvqv3dAautKdfqeAEA==/base.apk=com.android.shell
package:/apex/com.google.aosp_cf_phone.rros/overlay/cuttlefish_phone_overlay_frameworks_base_core.apk=android.cuttlefish.phone.overlay
"#;
        let mut expected: HashSet<String> = HashSet::new();
        expected.insert("com.android.shell".to_string());
        assert_eq!(expected, apks_from_pm_list_output(Vec::from(actual_output.as_bytes()))?);
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
        let installed_apks = HashSet::<String>::new();

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

        get_update_commands(&device_files, &host_files, &tracked_set, product_out, &installed_apks)
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
    // TODO(rbraunstein): Add tests for shadowing apks and ensure we don't install the system version.
}
