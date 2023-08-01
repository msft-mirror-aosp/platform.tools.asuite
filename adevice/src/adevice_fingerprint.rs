//! Tool to fingerprint the files on the device's filesystem.
// Run with:
//   m adevice_helper
//   adb push $ANDROID_PRODUCT_OUT/system/bin/adevice_helper /data/bin/adevice_helper
//   adb shell /data/bin/adevice_helper --partitions system

use clap::Parser;
use std::io;
use std::path::PathBuf;
use std::process;

mod fingerprint;

fn main() {
    let cli = HelperCli::parse();
    let partitions: Vec<PathBuf> = cli.partitions.iter().map(PathBuf::from).collect();
    let root = PathBuf::from("/");

    let infos = fingerprint::fingerprint_partitions(&root, &partitions).unwrap_or_else(|err| {
        eprintln!("Error scanning directories: {}", err);
        process::exit(1);
    });

    serde_json::to_writer(io::stdout(), &infos).unwrap_or_else(|err| {
        eprintln!("Error writing json: {}", err);
        process::exit(1);
    });
}

#[derive(Parser, Debug)]
struct HelperCli {
    /// Partitions in the product tree to report. Repeat or comma-separate.
    #[arg(long, short, global = true,
    default_values_t = [String::from("system")], value_delimiter = ',')]
    partitions: Vec<String>,
}

#[cfg(test)]
#[allow(unused)]
mod tests {
    use crate::fingerprint;
    use std::path::PathBuf;

    // TODO(rbraunstein): Write better device tests.
    #[test]
    fn fingerprint_apex() {
        // Walking system fails on permssion denied because the test isn't run as root.
        // TODO(rbraunstein): figure out how to run as root and deal better with filesystem errors.
        /*
            let partitions: Vec<PathBuf> = Vec::from([PathBuf::from("system")]);
            let root = PathBuf::from("/");

            let infos = fingerprint::fingerprint_partitions(&root, &partitions).unwrap();
            assert!(infos.len() > 2000);
        */
    }
}