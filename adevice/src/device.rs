use crate::commands::{restart_type, run_adb_command, split_string, AdbCommand};
use crate::restart_chooser::RestartType;
use crate::time;
use crate::RestartChooser;

use anyhow::{bail, Result};
use itertools::Itertools;
use log::info;
use std::cmp::Ordering;
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::Duration;

// TODO(rbraunstein): Combine this file with commands or adb command.
fn reboot() -> Result<String> {
    run_adb_command(&vec!["reboot".to_string()])
}

fn soft_restart() -> Result<String> {
    run_adb_command(&split_string("exec-out start"))
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
fn setup_push() -> Result<String> {
    run_adb_command(&split_string("exec-out stop"))?;
    // We seem to need a remount after reboots to make the system writable.
    run_adb_command(&split_string("remount"))?;
    info!("{}", run_adb_command(&split_string("shell getprop sys.boot_completed"))?);
    // Set the prop to the empty string so our "-z" check in wait works.
    run_adb_command(&vec![
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

    info!("Running timeout {}", &timeout_args.join(" "));
    Ok(std::process::Command::new("timeout").args(timeout_args).output()?)
}

/// Wait for the device to be ready to use.
/// First ask adb to wait for the device, then poll for sys.boot_completed on the device.
pub fn wait() -> Result<String> {
    info!("Waiting for device to restart");

    let args = vec![
        "wait-for-device".to_string(),
        "shell".to_string(),
        "while [[ -z $(getprop sys.boot_completed) ]]; do sleep 1; done".to_string(),
    ];
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

pub fn update(
    restart_chooser: &RestartChooser,
    adb_commands: &HashMap<PathBuf, AdbCommand>,
    profiler: &mut crate::Profiler,
) -> Result<()> {
    if adb_commands.is_empty() {
        return Ok(());
    }

    let installed_files =
        adb_commands.keys().map(|p| p.clone().into_os_string().into_string().unwrap()).collect();

    setup_push()?;
    time!(
        for command in adb_commands.values().cloned().sorted_by(&mkdir_comes_first) {
            run_adb_command(&command)?;
        },
        profiler.adb_cmds
    );

    match restart_type(restart_chooser, &installed_files) {
        RestartType::Reboot => time!(reboot(), profiler.reboot),
        RestartType::SoftRestart => soft_restart(),
        RestartType::None => anyhow::bail!("There should be a restart command"),
    }?;

    time!(wait()?, profiler.restart_after_boot);
    Ok(())
}

// Ensure mkdir comes before other commands.
// TODO(rbraunstein): This is temporary, either partition out the mkdirs or save
// the AdbCommand along with the commands so we don't have to check the strings.
// Too much thinking here.
fn mkdir_comes_first(a: &AdbCommand, b: &AdbCommand) -> Ordering {
    let a_is_mkdir = a.len() > 1 && a[..2] == vec!["shell".to_string(), "mkdir".to_string()];
    let b_is_mkdir = b.len() > 1 && b[..2] == vec!["shell".to_string(), "mkdir".to_string()];
    if !a_is_mkdir && !b_is_mkdir {
        return Ordering::Equal;
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
    use super::run_process_with_timeout;
    use anyhow::{bail, Result};
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
}
