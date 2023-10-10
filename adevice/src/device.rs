use crate::commands::{restart_type, split_string, AdbCommand};
use crate::restart_chooser::RestartType;
use crate::Device;
use crate::RestartChooser;
use crate::{fingerprint, time};

use anyhow::{anyhow, bail, Context, Result};
use itertools::Itertools;
use lazy_static::lazy_static;
use log::{debug, info};
use regex::Regex;
use serde::__private::ToString;
use std::cmp::Ordering;
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;
use std::process;
use std::time::Duration;

pub struct RealDevice {
    // If set, pass to all adb commands with --serial,
    // otherwise let adb default to the only connected device or use ANDROID_SERIAL env variable.
    android_serial: Option<String>,
}

impl Device for RealDevice {
    /// Runs `adb` with the given args.
    /// If there is a non-zero exit code or non-empty stderr, then
    /// creates a Result Err string with the details.
    fn run_adb_command(&self, args: &AdbCommand) -> Result<String> {
        let adjusted_args = self.adjust_adb_args(args);
        info!("       -- adb {adjusted_args:?}");
        let output = process::Command::new("adb")
            .args(adjusted_args)
            .output()
            .context("Error running adb commands")?;

        if output.status.success() && output.stderr.is_empty() {
            let stdout = String::from_utf8(output.stdout)?;
            return Ok(stdout);
        }

        // Adb remount returns status 0, but writes the mounts to stderr.
        // Just swallow the useless output and return ok.
        if let Some(cmd) = args.get(0) {
            if output.status.success() && cmd == "remount" {
                return Ok("".to_string());
            }
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

    fn reboot(&self) -> Result<String> {
        self.run_adb_command(&vec!["reboot".to_string()])
    }

    fn soft_restart(&self) -> Result<String> {
        self.run_adb_command(&split_string("exec-out start"))
    }

    fn fingerprint(
        &self,
        partitions: &[String],
    ) -> Result<HashMap<PathBuf, fingerprint::FileMetadata>> {
        crate::fingerprint_device(self, partitions)
    }

    /// Get the apks that are installed (i.e. with `adb install`)
    /// Count anything in the /data partition as installed.
    fn get_installed_apks(&self) -> Result<HashSet<String>> {
        // TODO(rbraunstein): See if there is a better way to do this that doesn't look for /data
        let package_manager_output = std::process::Command::new("adb")
            .args(self.adjust_adb_args(&split_string("exec-out pm list packages -s -f")))
            .output()
            .context("Running pm list packages")?;

        if !package_manager_output.status.success() {
            let stderr = String::from_utf8(package_manager_output.stderr)?;
            bail!("Unable to pm list packages get installed packages {:?}", stderr);
        }

        match apks_from_pm_list_output(package_manager_output.stdout) {
            Ok(packages) => {
                debug!("adb pm list packages found packages: {packages:?}");
                Ok(packages)
            }
            Err(e) => bail!("Unable to run aapt2 to get package information {e:?}"),
        }
    }

    /// Wait for the device to be ready to use.
    /// First ask adb to wait for the device, then poll for sys.boot_completed on the device.
    fn wait(&self) -> Result<String> {
        println!(" * Waiting for device to restart");

        let args = self.adjust_adb_args(&vec![
            "wait-for-device".to_string(),
            "shell".to_string(),
            "while [[ -z $(getprop sys.boot_completed) ]]; do sleep 1; done".to_string(),
        ]);
        let timeout = Duration::from_secs(120);
        let output = run_process_with_timeout(timeout, "adb", &args);

        match output {
            Ok(finished) if finished.status.success() => Ok("".to_string()),
            Ok(finished) if matches!(finished.status.code(), Some(124)) => {
                bail!("Waited {timeout:?} seconds for device to restart, but it hasn't yet.")
            }
            Ok(finished) => {
                let stderr = match String::from_utf8(finished.stderr) {
                    Ok(str) => str,
                    Err(e) => bail!("Error translating stderr {}", e),
                };

                // Adb writes push errors to stdout.
                let stdout = match String::from_utf8(finished.stdout) {
                    Ok(str) => str,
                    Err(e) => bail!("Error translating stdout {}", e),
                };

                bail!("Waiting for device has unexpected result: {:?}\nSTDOUT {stdout}\n STDERR {stderr}.", finished.status)
            }
            Err(_) => bail!("Problem checking on device after reboot."),
        }
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
fn apks_from_pm_list_output(stdout: Vec<u8>) -> Result<HashSet<String>> {
    let package_match = String::from_utf8(stdout)?
        .lines()
        .filter_map(|line| PM_LIST_PACKAGE_MATCHER.captures(line).map(|x| x[1].to_string()))
        .collect();
    Ok(package_match)
}

impl RealDevice {
    pub fn new(android_serial: Option<String>) -> RealDevice {
        RealDevice { android_serial }
    }

    /// Add -s DEVICE to the adb args based on global options.
    fn adjust_adb_args(&self, args: &AdbCommand) -> AdbCommand {
        match &self.android_serial {
            Some(serial) => [vec!["-s".to_string(), serial.clone()], args.clone()].concat(),
            None => args.clone(),
        }
    }
}

/// Common command to prepare a device to receive new files.
/// Always: `exec-out stop`
/// Always: `remount`
///  # A remount may not be needed but doesn't slow things down.
/// Always: Set the system property sys.boot_completed to 0.
///  # A reboot would do this anyway, but it doesn't hurt if we do it too.
///  # We poll for that property to be set back to 1.
///  # Both reboot and exec-out start will set it back to 1 when the
///  # system has booted and is ready to receive commands and run tests.
fn setup_push(device: &impl Device) -> Result<String> {
    device.run_adb_command(&split_string("exec-out stop"))?;
    // We seem to need a remount after reboots to make the system writable.
    device.run_adb_command(&split_string("remount"))?;
    // Set the prop to the empty string so our "-z" check in wait works.
    device.run_adb_command(&vec![
        "exec-out".to_string(),
        "setprop".to_string(),
        "sys.boot_completed".to_string(),
        "".to_string(),
    ])
}

// Rather than spawn and kill processes in rust, use the `timeout` command
// to do it for us.
// TODO(rbraunstein): fix for windows. Use the wait_timeout crate.
fn run_process_with_timeout(
    timeout: Duration,
    cmd: &str,
    args: &[String],
) -> Result<std::process::Output> {
    // Run timeout instead of `cmd` and add `cmd` to the arg list for timeout.
    let mut timeout_args = vec![format!("{}", timeout.as_secs()), cmd.to_string()];
    timeout_args.extend_from_slice(args);

    info!("    -- timeout {}", &timeout_args.join(" "));
    Ok(std::process::Command::new("timeout").args(timeout_args).output()?)
}

pub fn update(
    restart_chooser: &RestartChooser,
    adb_commands: &HashMap<PathBuf, AdbCommand>,
    profiler: &mut crate::Profiler,
    device: &impl Device,
) -> Result<()> {
    if adb_commands.is_empty() {
        return Ok(());
    }

    let installed_files =
        adb_commands.keys().map(|p| p.clone().into_os_string().into_string().unwrap()).collect();

    setup_push(device)?;
    time!(
        for command in adb_commands.values().cloned().sorted_by(&mkdir_comes_first_rm_dfs) {
            device.run_adb_command(&command)?;
        },
        profiler.adb_cmds
    );

    match restart_type(restart_chooser, &installed_files) {
        RestartType::Reboot => time!(device.reboot(), profiler.reboot),
        RestartType::SoftRestart => device.soft_restart(),
        RestartType::None => {
            log::debug!("No restart command");
            return Ok(());
        }
    }?;

    time!(device.wait()?, profiler.restart_after_boot);
    Ok(())
}

// Ensure mkdir comes before other commands.
// TODO(rbraunstein): This is temporary, either partition out the mkdirs or save
// the AdbCommand along with the commands so we don't have to check the strings.
// Too much thinking here.
fn mkdir_comes_first_rm_dfs(a: &AdbCommand, b: &AdbCommand) -> Ordering {
    let a_is_mkdir = a.len() > 1 && a[..2] == vec!["shell".to_string(), "mkdir".to_string()];
    let b_is_mkdir = b.len() > 1 && b[..2] == vec!["shell".to_string(), "mkdir".to_string()];
    if !a_is_mkdir && !b_is_mkdir {
        // Sort rm's with files before their parents.
        let a_cmd = a.join(" ");
        let b_cmd = b.join(" ");
        // clean and push/mkdir aren't mixed so we don't check when comparing.
        if a_cmd.contains("shell rm") && b_cmd.contains("shell rm") {
            return b_cmd.cmp(&a_cmd);
        }

        return a_cmd.cmp(&b_cmd);
    }
    // If both mkdir:
    //  Just compare the path.
    if a_is_mkdir && b_is_mkdir {
        return a[2].cmp(&b[2]);
    }
    if a_is_mkdir {
        return Ordering::Less;
    }
    if b_is_mkdir {
        return Ordering::Greater;
    }
    Ordering::Equal
}

#[cfg(test)]
mod tests {
    use super::*;
    use anyhow::{bail, Result};
    use core::cmp::Ordering;
    use std::time::Duration;

    // Igoring the tests so they don't cause delays in CI, but can still be run by hand.
    #[ignore]
    #[test]
    fn timeout_returns_when_process_returns() -> Result<()> {
        let timeout = Duration::from_secs(5);
        let sleep_args = &["3".to_string()];
        let output = run_process_with_timeout(timeout, "sleep", sleep_args);
        match output {
            Ok(finished) if finished.status.success() => Ok(()),
            _ => bail!("Expected an ok status code"),
        }
    }

    #[ignore]
    #[test]
    fn timeout_exits_when_timeout_hit() -> Result<()> {
        let timeout = Duration::from_secs(5);
        let sleep_args = &["7".to_string()];
        let output = run_process_with_timeout(timeout, "sleep", sleep_args);
        match output {
            Ok(finished) if matches!(finished.status.code(), Some(124)) => {
                // Expect this timeout case
                Ok(())
            }
            _ => bail!("Expected timeout to hit."),
        }
    }

    #[ignore]
    #[test]
    fn timeout_deals_with_process_errors() -> Result<()> {
        let timeout = Duration::from_secs(5);
        let sleep_args = &["--bad-arg".to_string(), "7".to_string()];
        // Add a bad arg so the process we run errs out.
        let output = run_process_with_timeout(timeout, "sleep", sleep_args);
        match output {
            Ok(finished) if finished.status.success() => bail!("Expected error"),
            Ok(finished) if matches!(finished.status.code(), Some(124)) => bail!("Expected error"),

            Ok(finished) => {
                let stderr = match String::from_utf8(finished.stderr) {
                    Ok(str) => str,
                    Err(e) => bail!("Error translating stderr {}", e),
                };
                assert!(stderr.contains("unrecognized option"));
                Ok(())
            }
            _ => bail!("Expected to catch err in stderr"),
        }
    }

    #[test]
    fn deeper_rms_come_first() {
        assert_eq!(
            Ordering::Less,
            mkdir_comes_first_rm_dfs(
                &split_string("shell rm -rf dir1/dir2/file1"),
                &split_string("shell rm -rf dir1/dir2"),
            )
        );
        assert_eq!(
            Ordering::Greater,
            mkdir_comes_first_rm_dfs(
                &split_string("shell rm -rf dir1/dir2"),
                &split_string("shell rm -rf dir1/dir2/file1"),
            )
        );
    }
    #[test]
    fn rm_all_files_before_dirs() {
        assert_eq!(
            Ordering::Less,
            mkdir_comes_first_rm_dfs(
                &split_string("shell rm system/app/FakeOemFeatures/FakeOemFeatures.apk"),
                &split_string("shell rm -rf system/app/FakeOemFeatures"),
            )
        );
        assert_eq!(
            Ordering::Greater,
            mkdir_comes_first_rm_dfs(
                &split_string("shell rm -rf system/app/FakeOemFeatures"),
                &split_string("shell rm system/app/FakeOemFeatures/FakeOemFeatures.apk"),
            )
        );
    }

    #[test]
    // NOTE: This test assumes we have adb in our path.
    fn adb_command_success() {
        // Use real device for device tests.
        let result = RealDevice::new(None)
            .run_adb_command(&vec!["version".to_string()])
            .expect("Error running command");
        assert!(
            result.contains("Android Debug Bridge version"),
            "Expected a version string, but received:\n {result}"
        );
    }

    #[test]
    fn adb_command_failure() {
        let result = RealDevice::new(None).run_adb_command(&vec!["improper_cmd".to_string()]);
        if result.is_ok() {
            panic!("Did not expect to succeed");
        }

        let expected_str =
            "adb error, Exited with status code: 1  adb: unknown command improper_cmd\n";
        assert_eq!(expected_str, format!("{:?}", result.unwrap_err()));
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
}
