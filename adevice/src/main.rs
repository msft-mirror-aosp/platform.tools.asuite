//! Update an Android device with locally built changes.
mod adevice;
mod cli;
mod commands;
mod device;
mod fingerprint;
mod metrics;
mod restart_chooser;
mod tracking;

use crate::adevice::Profiler;
use crate::adevice::RealHost;
use crate::device::RealDevice;
use crate::metrics::Metrics;
use clap::Parser;
use std::fs::File;
use std::path::PathBuf;

use anyhow::Result;

fn main() -> Result<()> {
    let host = RealHost::new();
    let cli = cli::Cli::parse();
    let mut profiler = Profiler::default();
    let device = RealDevice::new(cli.global_options.serial.clone());
    let mut metrics = Metrics::default();
    crate::adevice::adevice(
        &host,
        &device,
        &cli,
        &mut std::io::stdout(),
        &mut metrics,
        log_file(),
        &mut profiler,
    )
}

/// Return a file open at $ANDROID_BUILD_TOP/out/adevice.log or None
/// Ideally, use the file_rotate crate: https://docs.rs/file-rotate/latest/file_rotate/ as well.
fn log_file() -> Option<File> {
    match std::env::var("ANDROID_BUILD_TOP") {
        Ok(top) if !top.is_empty() => {
            let path = PathBuf::from(top).join("out").join("adevice.log");
            File::create(path).ok()
        }
        _ => None,
    }
}
