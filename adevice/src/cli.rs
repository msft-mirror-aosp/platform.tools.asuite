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
    Update,
    /// Adds module name to the list of tracked modules.
    /// If an installed file under $ANDROID_PRODUCT_OUT is not
    /// part of a tracked module or the base image, then it will
    /// not be pushed to the device.
    Track(ModuleNames),
    /// Removes module name from list of tracked modules.
    /// See `track` for more details.
    Untrack(ModuleNames),
}

#[derive(Debug, Args)]
pub struct ModuleNames {
    //#[clap(global = true)]
    /// List one or modules, space separated.
    /// Use the module name in Android.bp
    pub modules: Vec<String>,
    // pub n: String,
}

#[derive(Args, Debug)]
pub struct GlobalOptions {
    // TODO(rbraunstein): Revisit all the command name descriptions.
    // TODO(rbraunstein): Add system_other to the default list, but deal gracefully
    // with it not being on the device.
    /// Partitions in the product tree to sync. Repeat arg or comma-separate.
    #[clap(long, short, global = true,
    default_values_t = [String::from("system"), String::from("system_ext")], value_delimiter = ',')]
    pub partitions: Vec<String>,
    // TODO(rbraunstein): Validate relative, not absolute paths.
    /// If unset defaults to ANDROID_PRODUCT_OUT env variable.
    #[clap(long = "product_out", global = true)]
    pub product_out: Option<String>,
    /// Do not make any modification if more than this many are needed
    #[clap(long, short, default_value_t = 20)]
    pub max_allowed_changes: usize,
    // TODO(rbraunstein): Import clap-verbosity-flag crate so we can use -vv instead.
    // Print commands while executing them.
    #[clap(long = "verbose", short, global = true, value_enum, default_value_t=Verbosity::Details)]
    pub verbose: Verbosity,
}

#[derive(clap::ValueEnum, Clone, Debug)]
pub enum Verbosity {
    /// Only show minimal information.
    None,
    /// Show all adb operations, and all timings.
    Details,
    /// For debugging internals of tool
    Debug,
}
