use crate::adevice::{Device, Profiler};
use crate::commands::{restart_type, split_string, AdbCommand};
use crate::progress;
use crate::restart_chooser::{RestartChooser, RestartType};
use crate::{fingerprint, time};

use anyhow::{anyhow, bail, Context, Result};
use itertools::Itertools;
use lazy_static::lazy_static;
use regex::Regex;
use serde::__private::ToString;
use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;
use std::process;
use std::thread::sleep;
use std::time::Duration;
use std::time::Instant;
use tracing::{debug, info};

pub struct RealDevice {
    // If set, pass to all adb commands with --serial,
    // otherwise let adb default to the only connected device or use ANDROID_SERIAL env variable.
    android_serial: Option<String>,
}

impl Device for RealDevice {
    /// Runs `adb` with the given args.
    /// If there is a non-zero exit code or non-empty stderr, then
    /// creates a Result Err string with the details.
    fn run_adb_command(&self, cmd: &AdbCommand) -> Result<String> {
        self.run_raw_adb_command(&cmd.args())
    }

    fn reboot(&self) -> Result<String> {
        self.run_raw_adb_command(&["reboot".to_string()])
    }

    fn soft_restart(&self) -> Result<String> {
        self.run_raw_adb_command(&split_string("exec-out start"))
    }

    fn fingerprint(
        &self,
        partitions: &[String],
    ) -> Result<HashMap<PathBuf, fingerprint::FileMetadata>> {
        self.fingerprint_device(partitions)
    }

    /// Get the apks that are installed (i.e. with `adb install`)
    /// Count anything in the /data partition as installed.
    fn get_installed_apks(&self) -> Result<HashSet<String>> {
        // TODO(rbraunstein): See if there is a better way to do this that doesn't look for /data
        let package_manager_output = self
            .run_raw_adb_command(&split_string("exec-out pm list packages -s -f"))
            .context("Running pm list packages")?;

        let packages = apks_from_pm_list_output(&package_manager_output);
        debug!("adb pm list packages found packages: {packages:?}");
        Ok(packages)
    }

    /// Wait for the device to be ready to use.
    /// First ask adb to wait for the device, then poll for sys.boot_completed on the device.
    fn wait(&self, profiler: &mut Profiler) -> Result<String> {
        // Typically the reboot on acloud is 25 secs
        // It can take 130 seconds after for a full boot.
        // Setting timeouts to have at least 2x that.
        progress::start(" * [1/2] Waiting for device to connect.");
        time!(
            {
                let args = self.adjust_adb_args(&["wait-for-device".to_string()]);
                self.wait_for_adb_with_timeout(&args, Duration::from_secs(75))?;
            },
            profiler.wait_for_device
        );

        progress::update(" * [2/2] Waiting for property sys.boot_completed.");
        time!(
            {
                let args = self.adjust_adb_args(&[
                    "wait-for-device".to_string(),
                    "shell".to_string(),
                    "while [[ -z $(getprop sys.boot_completed) ]]; do sleep 1; done".to_string(),
                ]);
                let result = self.wait_for_adb_with_timeout(&args, Duration::from_secs(260));
                progress::stop();
                result
            },
            profiler.wait_for_boot_completed
        )
    }

    fn prep_after_flash(&self, profiler: &mut Profiler) -> Result<()> {
        progress::start(" * [1/2] Remounting device");
        let timeout = Duration::from_secs(60);

        self.run_cmd_with_retry_until_timeout(
            "adb",
            &self.adjust_adb_args(&["root".to_string()]),
            timeout,
        )?;
        // Remount and reboot; rebooting will return status code 255 so ignore error.
        let _ = self.run_raw_adb_command(&["remount".to_string(), "-R".to_string()]);
        progress::stop();
        self.wait(profiler)?;
        self.run_cmd_with_retry_until_timeout(
            "adb",
            &self.adjust_adb_args(&["root".to_string()]),
            timeout,
        )?;
        Ok(())
    }

    /// Runs `adb` with the given args.
    /// If there is a non-zero exit code or non-empty stderr, then
    /// creates a Result Err string with the details.
    fn run_raw_adb_command(&self, cmd: &[String]) -> Result<String> {
        let adjusted_args = self.adjust_adb_args(cmd);
        info!("       -- adb {adjusted_args:?}");
        let output = process::Command::new("adb")
            .args(adjusted_args)
            .output()
            .context("Error running adb commands")?;

        if output.status.success() {
            let stdout = String::from_utf8(output.stdout)?;
            return Ok(stdout);
        }

        // It is some error.
        let status = match output.status.code() {
            Some(code) => format!("Exited with status code: {code}"),
            None => "Process terminated by signal".to_string(),
        };

        // Adb writes bad commands to stderr.  (adb badverb) with status 1
        // Adb writes remount output to stderr (adb remount) but gives status 0
        let stderr = match String::from_utf8(output.stderr) {
            Ok(str) => str,
            Err(e) => return Err(anyhow!("Error translating stderr {}", e)),
        };

        // Adb writes push errors to stdout.
        let stdout = match String::from_utf8(output.stdout) {
            Ok(str) => str,
            Err(e) => return Err(anyhow!("Error translating stdout {}", e)),
        };

        Err(anyhow!("adb error, {status} {stdout} {stderr}"))
    }
}

lazy_static! {
    // Sample output, one installed, one not:
    // % adb exec-out pm list packages  -s -f  | grep shell
    //   package:/product/app/Browser2/Browser2.apk=org.chromium.webview_shell
    //   package:/data/app/~~PxHDtZDEgAeYwRyl-R3bmQ==/com.android.shell--R0z7ITsapIPKnt4BT0xkg==/base.apk=com.android.shell
    // # capture the package name (com.android.shell)
    static ref PM_LIST_PACKAGE_MATCHER: Regex =
        Regex::new(r"^package:/data/app/.*/base.apk=(.+)$").expect("regex does not compile");
}

/// Filter package manager output to figure out if the apk is installed in /data.
fn apks_from_pm_list_output(stdout: &str) -> HashSet<String> {
    let package_match = stdout
        .lines()
        .filter_map(|line| PM_LIST_PACKAGE_MATCHER.captures(line).map(|x| x[1].to_string()))
        .collect();
    package_match
}

impl RealDevice {
    pub fn new(android_serial: Option<String>) -> RealDevice {
        RealDevice { android_serial }
    }

    /// Add -s DEVICE to the adb args based on global options.
    fn adjust_adb_args(&self, args: &[String]) -> Vec<String> {
        match &self.android_serial {
            Some(serial) => [vec!["-s".to_string(), serial.clone()], args.to_vec()].concat(),
            None => args.to_vec(),
        }
    }

    /// Given "partitions" at the root of the device,
    /// return an entry for each file found.  The entry contains the
    /// digest of the file contents and stat-like data about the file.
    /// Typically, dirs = ["system"]
    fn fingerprint_device(
        &self,
        partitions: &[String],
    ) -> Result<HashMap<PathBuf, fingerprint::FileMetadata>> {
        // Ensure we are root or we can't read some files.
        // In userdebug builds, every reboot reverts back to the "shell" user.
        self.run_raw_adb_command(&["root".to_string()])?;
        self.run_raw_adb_command(&["wait-for-device".to_string()])?;
        let mut adb_args = vec![
            "shell".to_string(),
            "/system/bin/adevice_fingerprint".to_string(),
            "-p".to_string(),
        ];
        // -p system,system_ext
        adb_args.push(partitions.join(","));
        let fingerprint_result = self.run_raw_adb_command(&adb_args);
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
                // If pontis is running, add to the error message to check pontis UI
                let pontis_status = process::Command::new("pontis")
                    .args(&vec!["status".to_string()])
                    .output()
                    .context("Error checking pontis status")?;

                let error_msg = format!("Unknown problem running `adevice_fingerprint` on your device: {problem:?}.\n  Your device may still be in a booting state.  Try `adb get-state` to start debugging.");
                if pontis_status.status.success() {
                    let pontis_error_msg = "\n  If you are using go/pontis, make sure the device appears in the Pontis browser UI and if not re-add it there.";
                    bail!("{}{}", error_msg, pontis_error_msg);
                }
                bail!("{}", error_msg);
            }
        }

        let stdout = fingerprint_result.unwrap();

        let result: HashMap<String, fingerprint::FileMetadata> = match serde_json::from_str(&stdout)
        {
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

    /// Run "adb wait-for-device" ... but exit if adb doesn't return
    /// in the `timeout` amount of time.
    pub fn wait_for_adb_with_timeout(&self, args: &[String], timeout: Duration) -> Result<String> {
        self.run_cmd_with_retry_until_timeout("adb", args, timeout)
    }

    /// run command with retry until timeout duration is reached
    pub fn run_cmd_with_retry_until_timeout(
        &self,
        cmd: &str,
        args: &[String],
        timeout: Duration,
    ) -> Result<String> {
        run_process_with_retry_until_timeout(cmd, args, timeout)
    }
}

// Attempts to run a command until the command is either:
// 1) Successful
// 2) The amount of retries exceeds 5
// 3) The timeout (total across all retries) runs out.
// This is used for adb wait-for-device on acloud which may return
// errors the first few times.
// Using timeout binary to simplify (not having to kill process in rust)
// TODO(kevindagostino): fix for windows. Use the wait_timeout crate.

pub fn run_process_with_retry_until_timeout(
    cmd: &str,
    args: &[String],
    timeout: Duration,
) -> Result<String> {
    let start_time = Instant::now();
    let delay = Duration::from_secs(1);
    let max_retries = 5;
    let mut retry_count = 0;

    while retry_count < max_retries {
        let time_left = timeout.saturating_sub(start_time.elapsed());
        if time_left <= Duration::ZERO {
            break;
        }
        retry_count += 1;

        let mut timeout_args = vec![format!("{}", time_left.as_secs()), cmd.to_string()];
        timeout_args.extend_from_slice(args);

        info!("       -- timeout {}", &timeout_args.join(" "));
        let output = std::process::Command::new("timeout")
            .args(timeout_args)
            .output()
            .expect("command executed");
        if output.status.success() {
            let msg = String::from_utf8(output.stdout)?;
            info!("       {} {}", output.status, msg);
            return Ok(msg);
        }

        if retry_count > 1 {
            let update_message = format!("retry attempt {} - {:?}", retry_count, cmd.to_string());
            progress::update(&update_message)
        }

        // error; log and retry if within timeout window
        info!("       {} {:?}", output.status, String::from_utf8(output.stderr).expect("stderr"));
        sleep(delay);
    }
    bail!("Command failed to execute {}", cmd.to_string());
}

pub fn update(
    restart_chooser: &RestartChooser,
    adb_commands: &HashMap<PathBuf, AdbCommand>,
    profiler: &mut Profiler,
    device: &impl Device,
    should_wait: crate::cli::Wait,
) -> Result<()> {
    if adb_commands.is_empty() {
        return Ok(());
    }

    let installed_files =
        adb_commands.keys().map(|p| p.clone().into_os_string().into_string().unwrap()).collect();

    progress::start("Preparing to update files");
    prep_for_push(device, should_wait.clone())?;
    let mut i = 1;
    time!(
        for command in adb_commands.values().cloned().sorted_by(&mkdir_comes_first_rm_dfs) {
            let update_message =
                format!("Updating files [{}/{}] {:?}", i, adb_commands.len(), command.args());
            progress::update(&update_message);
            device.run_adb_command(&command)?;
            i += 1;
        },
        profiler.adb_cmds
    );
    progress::stop();
    println!(" * Update succeeded!");
    println!();

    let rtype = restart_type(restart_chooser, &installed_files);
    profiler.restart_type = format!("{:?}", rtype);
    match rtype {
        RestartType::Reboot => time!(device.reboot(), profiler.restart),
        RestartType::SoftRestart => time!(device.soft_restart(), profiler.restart),
        RestartType::None => {
            tracing::debug!("No restart command");
            return Ok(());
        }
    }?;

    if should_wait.into() {
        device.wait(profiler)?;
    }
    Ok(())
}

/// Common command to prepare a device to receive new files.
/// Always: `exec-out stop`
/// Always: `remount`
///  # A remount may not be needed but doesn't slow things down.
/// If `should_wait`: Set the system property sys.boot_completed to 0.
///  # A reboot would do this anyway, but it doesn't hurt if we do it too.
///  # We poll for that property to be set back to 1.
///  # Both reboot and exec-out start will set it back to 1 when the
///  # system has booted and is ready to receive commands and run tests.
fn prep_for_push(device: &impl Device, should_wait: crate::cli::Wait) -> Result<()> {
    device.run_raw_adb_command(&split_string("exec-out stop"))?;
    // We seem to need a remount after reboots to make the system writable.
    device.run_raw_adb_command(&split_string("remount"))?;
    // Set the prop to the empty string so our "-z" check in wait works.
    if should_wait.into() {
        device.run_raw_adb_command(&[
            "exec-out".to_string(),
            "setprop".to_string(),
            "sys.boot_completed".to_string(),
            "".to_string(),
        ])?;
    }
    Ok(())
}

// 1) Ensure mkdir comes before other commands.
// 2) Do removes as a depth-first-search so we clean children before parents.
// 3) Sort rm before other commands, but it shouldn't matter.
// 4) Remove files before dirs.
//    We would never remove a file or directory we are pushing to.
fn mkdir_comes_first_rm_dfs(a: &AdbCommand, b: &AdbCommand) -> Ordering {
    // Neither is mkdir
    if !a.is_mkdir() && !b.is_mkdir() {
        // Sort rm's with files before their parents.
        let a_cmd = a.args().join(" ");
        let b_cmd = b.args().join(" ");

        if a.is_rm() && b.is_rm() {
            // This also sorts files before dirs because of the "-rf" added to dirs.
            return b_cmd.cmp(&a_cmd);
        }
        if a.is_rm() {
            return Ordering::Less;
        }
        if b.is_rm() {
            return Ordering::Greater;
        }

        // Sort everything by the args.
        return a_cmd.cmp(&b_cmd);
    }
    // If both mkdir:
    //  Just compare the path, parents will come before subdirs.
    if a.is_mkdir() && b.is_mkdir() {
        return a.device_path().cmp(b.device_path());
    }
    if a.is_mkdir() {
        return Ordering::Less;
    }
    if b.is_mkdir() {
        return Ordering::Greater;
    }
    Ordering::Equal
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::commands::AdbAction;
    use anyhow::{bail, Result};
    use core::cmp::Ordering;
    use std::time::Duration;

    // Igoring the tests so they don't cause delays in CI, but can still be run by hand.
    #[ignore]
    #[test]
    fn timeout_returns_when_process_returns() -> Result<()> {
        let timeout = Duration::from_secs(5);
        let sleep_args = &["3".to_string()];
        let output = run_process_with_retry_until_timeout("sleep", sleep_args, timeout);
        match output {
            Ok(_) => Ok(()),
            _ => bail!("Expected an ok status code"),
        }
    }

    #[ignore]
    #[test]
    fn timeout_exits_when_timeout_hit() -> Result<()> {
        let timeout = Duration::from_secs(5);
        let sleep_args = &["7".to_string()];
        let start_time = Instant::now();
        let output = run_process_with_retry_until_timeout("sleep", sleep_args, timeout);

        // smoke test to make sure process ran longer then timeout.
        let duration = start_time.elapsed();
        assert!(
            duration > timeout,
            "Expected process to take longer then timeout. Elapsed: {:?}, Timeout: {:?}",
            duration,
            timeout
        );

        match output {
            Ok(_) => bail!("Expected error status code"),
            _ => Ok(()),
        }
    }

    #[ignore]
    #[test]
    fn timeout_deals_with_process_errors() -> Result<()> {
        let timeout = Duration::from_secs(5);
        let sleep_args = &["--bad-arg".to_string(), "7".to_string()];
        // Add a bad arg so the process we run errs out.
        let output = run_process_with_retry_until_timeout("sleep", sleep_args, timeout);
        match output {
            Ok(_) => bail!("Expected error status code"),
            _ => Ok(()),
        }
    }

    #[ignore]
    #[test]
    fn reboot_wait() -> Result<()> {
        let timeout = Duration::from_secs(5);
        let sleep_args = &["--bad-arg".to_string(), "7".to_string()];
        // Add a bad arg so the process we run errs out.
        let output = run_process_with_retry_until_timeout("sleep", sleep_args, timeout);
        match output {
            Ok(_) => bail!("Expected error status code"),
            _ => Ok(()),
        }
    }

    fn delete_file_cmd(file: &str) -> AdbCommand {
        AdbCommand::from_action(AdbAction::DeleteFile, &PathBuf::from(file))
    }

    fn delete_dir_cmd(dir: &str) -> AdbCommand {
        AdbCommand::from_action(AdbAction::DeleteDir, &PathBuf::from(dir))
    }

    #[test]
    fn deeper_rms_come_first() {
        assert_eq!(
            Ordering::Less,
            mkdir_comes_first_rm_dfs(
                &delete_file_cmd("dir1/dir2/file1"),
                &delete_dir_cmd("dir1/dir2"),
            )
        );
        assert_eq!(
            Ordering::Greater,
            mkdir_comes_first_rm_dfs(
                &delete_dir_cmd("dir1/dir2"),
                &delete_file_cmd("dir1/dir2/file1"),
            )
        );
        assert_eq!(
            Ordering::Less,
            mkdir_comes_first_rm_dfs(
                &delete_dir_cmd("dir1/dir2/dir3"),
                &delete_dir_cmd("dir1/dir2"),
            )
        );
        assert_eq!(
            Ordering::Greater,
            mkdir_comes_first_rm_dfs(
                &delete_dir_cmd("dir1/dir2"),
                &delete_dir_cmd("dir1/dir2/dir3"),
            )
        );
    }
    #[test]
    fn rm_all_files_before_dirs() {
        assert_eq!(
            Ordering::Less,
            mkdir_comes_first_rm_dfs(
                &delete_file_cmd("system/app/FakeOemFeatures/FakeOemFeatures.apk"),
                &delete_dir_cmd("system/app/FakeOemFeatures"),
            )
        );
        assert_eq!(
            Ordering::Greater,
            mkdir_comes_first_rm_dfs(
                &delete_dir_cmd("system/app/FakeOemFeatures"),
                &delete_file_cmd("system/app/FakeOemFeatures/FakeOemFeatures.apk"),
            )
        );
    }

    #[test]
    fn sort_many() {
        let dir = |d| AdbCommand::from_action(AdbAction::DeleteDir, &PathBuf::from(d));
        let file = |d| AdbCommand::from_action(AdbAction::DeleteFile, &PathBuf::from(d));
        let mut adb_commands: Vec<AdbCommand> = vec![
            file("system/STALE_FILE"),
            dir("system/bin/dir1/STALE_DIR"),
            file("system/bin/dir1/STALE_DIR/stalefile1"),
            file("system/bin/dir1/STALE_DIR/stalefile2"),
        ];

        adb_commands.sort_by(&mkdir_comes_first_rm_dfs);
        assert_eq!(
            // Expected sorted order, deepest first.
            // files before dirs.
            vec![
                file("system/bin/dir1/STALE_DIR/stalefile2"),
                file("system/bin/dir1/STALE_DIR/stalefile1"),
                file("system/STALE_FILE"),
                dir("system/bin/dir1/STALE_DIR"),
            ],
            adb_commands
        );
    }

    #[test]
    // NOTE: This test assumes we have adb in our path.
    fn adb_command_success() {
        // Use real device for device tests.
        let result = RealDevice::new(None)
            .run_raw_adb_command(&["version".to_string()])
            .expect("Error running command");
        assert!(
            result.contains("Android Debug Bridge version"),
            "Expected a version string, but received:\n {result}"
        );
    }

    #[test]
    fn adb_command_failure() {
        let result = RealDevice::new(None).run_raw_adb_command(&["improper_cmd".to_string()]);
        if result.is_ok() {
            panic!("Did not expect to succeed");
        }

        let expected_str =
            "adb error, Exited with status code: 1  adb: unknown command improper_cmd\n";
        assert_eq!(expected_str, format!("{:?}", result.unwrap_err()));
    }

    #[test]
    fn package_manager_output_parsing() {
        let actual_output = r#"
package:/product/app/Browser2/Browser2.apk=org.chromium.webview_shell
package:/apex/com.google.aosp_cf_phone.rros/overlay/cuttlefish_overlay_frameworks_base_core.apk=android.cuttlefish.overlay
package:/data/app/~~f_ZzeFPKma_EfXRklotqFg==/com.android.shell-hrjEOvqv3dAautKdfqeAEA==/base.apk=com.android.shell
package:/apex/com.google.aosp_cf_phone.rros/overlay/cuttlefish_phone_overlay_frameworks_base_core.apk=android.cuttlefish.phone.overlay
"#;
        let mut expected: HashSet<String> = HashSet::new();
        expected.insert("com.android.shell".to_string());
        assert_eq!(expected, apks_from_pm_list_output(actual_output));
    }
}
