use clap::{Args, Parser, Subcommand};

#[derive(Parser)]
#[command(about = "Tool to push your rebuilt modules to your device.")]
#[command(propagate_version = true)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,
    #[clap(flatten)]
    pub global_options: GlobalOptions,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Shows the file differences between build tree and host.
    Status,
    /// Show the actions that would be run.
    ShowActions,
    /// Update the device
    UpdateDevice { verbose: Option<bool>, reboot: Option<bool> },
}

#[derive(Debug, Args)]
pub struct GlobalOptions {
    // TODO(rbraunstein): Revisit all the command name descriptions.
    /// Partitions in the product tree to sync. Repeat arg or comma-separate.
    #[clap(long, short, global = true,
    default_values_t = [String::from("system")], value_delimiter = ',')]
    pub partitions: Vec<String>,
    // TODO(rbraunstein): Validate relative, not absolute paths.
    #[clap(global = true)]
    /// If unset defaults to ANDROID_PRODUCT_OUT env variable.
    pub product_out: Option<String>,
    // Path of file to write out with the status update or dump of device or build tree
    // hashes.
    pub dump_file_prefix: Option<String>,
}