use crate::commands::{restart_type, run_adb_command, split_string, AdbCommand};
use crate::restart_chooser::RestartType;
use crate::RestartChooser;

use anyhow::Result;
use itertools::Itertools;
use std::cmp::Ordering;
use std::collections::HashMap;
use std::path::PathBuf;

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
    run_adb_command(&split_string("exec-out setprop sys.boot_completed 0"))
}

/// Wait for the device to be ready to use.
/// First ask adb to wait for the device, then poll for sys.boot_completed
/// to be set back to 1.
fn wait() -> Result<String> {
    // TODO(rbraunstein): Add a timeout here so we don't wait forever and
    // display a reasonable message to the user if wait too long.
    log::info!("Waiting on device to reboot");
    let result = run_adb_command(&vec!["wait-for-device".to_string()]);
    while run_adb_command(&split_string("exec-out getprop sys.boot_completed"))?.trim() != "1" {
        std::thread::sleep(std::time::Duration::from_secs(1));
    }
    result
}

pub fn update(
    restart_chooser: &RestartChooser,
    adb_commands: &HashMap<PathBuf, AdbCommand>,
) -> Result<()> {
    if adb_commands.is_empty() {
        return Ok(());
    }

    let installed_files =
        adb_commands.keys().map(|p| p.clone().into_os_string().into_string().unwrap()).collect();

    setup_push()?;
    for command in adb_commands.values().cloned().sorted_by(&mkdir_comes_first) {
        run_adb_command(&command)?;
    }

    match restart_type(restart_chooser, &installed_files) {
        RestartType::Reboot => reboot(),
        RestartType::SoftRestart => soft_restart(),
        RestartType::None => anyhow::bail!("There should be a restart command"),
    }?;
    // TODO(rbraunstein): Add timeout with reasonable error message on wait.
    wait()?;
    Ok(())
}

// Ensure mkdir comes before other commands.
// TODO(rbraunstein): This is temporary, either partition out the mkdirs or save
// the AdbCommand along with the commands so we don't have to check the strings.
// Too much thinking here.
fn mkdir_comes_first(a: &AdbCommand, b: &AdbCommand) -> Ordering {
    let a_is_mkdir = a[..2] == vec!["shell".to_string(), "mkdir".to_string()];
    let b_is_mkdir = b[..2] == vec!["shell".to_string(), "mkdir".to_string()];
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
