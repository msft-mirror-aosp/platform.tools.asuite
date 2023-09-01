use clap::{Args, Parser, Subcommand};

#[derive(Parser)]
#[command(about = "Tool to push your rebuilt modules to your device.")]
#[command(version = "0.1")]
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
    /// Change the base module we are tracking from `droid` to something else.
    TrackBase(BaseModule),
    /// Removes module name from list of tracked modules.
    /// See `track` for more details.
    Untrack(ModuleNames),
    /// Removes untracked files from the device.
    CleanDevice {
        #[clap(long, short)]
        force: bool,
    },
}

#[derive(Debug, Args)]
pub struct ModuleNames {
    /// List one or modules, space separated.
    /// Use the module name in Android.bp
    pub modules: Vec<String>,
}

#[derive(Debug, Args)]
pub struct BaseModule {
    /// The module name the system image is built from like 'droid' or 'sync'.
    /// It can also be an unbundled mainline module name.
    pub base: String,
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
    #[clap(long, short, default_value_t = 100)]
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
    /// Show all adb operations.
    Details,
    /// For debugging internals of tool and timings.
    Debug,
}
