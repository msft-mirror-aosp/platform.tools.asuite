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
    Update,
}

#[derive(Debug, Args)]
pub struct GlobalOptions {
    // TODO(rbraunstein): Revisit all the command name descriptions.
    // TODO(rbraunstein): Add system_other to the default list, but deal gracefully
    // with it not being on the device.
    /// Partitions in the product tree to sync. Repeat arg or comma-separate.
    #[clap(long, short, global = true,
    default_values_t = [String::from("system"), String::from("system_ext")], value_delimiter = ',')]
    pub partitions: Vec<String>,
    // TODO(rbraunstein): Validate relative, not absolute paths.
    #[clap(global = true)]
    /// If unset defaults to ANDROID_PRODUCT_OUT env variable.
    pub product_out: Option<String>,
    /// Do not make any modification if more than this many are needed
    #[clap(long, short, default_value_t = 20)]
    pub max_allowed_changes: usize,
    // TODO(rbraunstein): Import clap-verbosity-flag crate so we can use -vv instead
    // of having two flags. Or add an output level enum.
    /// Print commands while executing them.
    #[clap(long = "verbose", short, default_value_t = false, global = true)]
    pub verbose: bool,
    /// Print commands while executing them.
    #[clap(long = "debug", short, default_value_t = false, global = true)]
    pub debug: bool,
}
