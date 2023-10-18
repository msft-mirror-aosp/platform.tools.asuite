//! Update an Android device with locally built changes.
mod adevice;
mod cli;
mod commands;
mod device;
mod fingerprint;
mod logger;
mod metrics;
mod restart_chooser;
mod tracking;

use crate::adevice::RealHost;
use crate::device::RealDevice;
use crate::metrics::Metrics;
use clap::Parser;

use anyhow::Result;

fn main() -> Result<()> {
    let host = RealHost::new();
    let cli = cli::Cli::parse();
    let device = RealDevice::new(cli.global_options.serial.clone());
    let mut metrics = Metrics::default();

    crate::adevice::adevice(&host, &device, &cli, &mut std::io::stdout(), &mut metrics)
}
