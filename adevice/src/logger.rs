use crate::cli;
use env_logger::{Builder, Target};
use std::io::Write;

pub fn init_logger(global_options: &cli::GlobalOptions) {
    Builder::from_default_env()
        .target(Target::Stdout)
        .format_module_path(false)
        .format_target(false)
        // I actually want different logging channels for timing vs adb commands.
        .filter_level(match &global_options.verbose {
            cli::Verbosity::Debug => log::LevelFilter::Debug,
            cli::Verbosity::None => log::LevelFilter::Warn,
            cli::Verbosity::Details => log::LevelFilter::Info,
        })
        .write_style(env_logger::WriteStyle::Auto)
        .format(move |buf, record| writeln!(buf, "{:?}", record.args()))
        .init();
}
