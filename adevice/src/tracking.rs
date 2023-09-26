/// Module to keep track of which files should be pushed to a device.
/// Composed of:
///  1) A tracking config that lets user specify modules to
///     augment a base image (droid).
///  2) Integration with ninja to derive "installed" files from
///     this module set.
use anyhow::{Context, Result};
use lazy_static::lazy_static;
use log::{debug, warn};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::BufReader;
use std::path::PathBuf;
use std::process;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Config {
    pub base: String,
    pub modules: Vec<String>,
    #[serde(default, skip_serializing, skip_deserializing)]
    home_dir: String,
}

/// Object representing the files that are _tracked_. These are files that the
/// build system indicates should be on the device.  Sometimes stale files
/// get left in the Product Out tree or extra modules get built into the Product Out tree.
/// This tracking config helps us call ninja to distinguish declared depdencies for
/// `droid` and what has been built.
/// TODO(rbraunstein): Rewrite above clearer.
impl Config {
    /// Load set of tracked modules from User's homedir or return a default one.
    pub fn load_or_default(home_dir: String) -> Result<Self> {
        if let Ok(file) = fs::File::open(Self::path(&home_dir)?) {
            let mut config: Config = serde_json::from_reader(BufReader::new(file))
                .context(format!("Parsing config {:?}", Self::path(&home_dir)?))?;
            config.home_dir = home_dir;
            return Ok(config);
        }
        // Lets not create a default config file until they actually track a module.
        Ok(Config { base: "droid".to_string(), modules: Vec::new(), home_dir })
    }

    pub fn print(&self) {
        debug!("Tracking base: `{}` and modules {:?}", self.base, self.modules);
    }

    /// Returns the full path to the serialized config file.
    pub fn path(home: &str) -> Result<String> {
        fs::create_dir_all(format!("{home}/.config/asuite"))?;
        Ok(format!("{home}/.config/asuite/adevice-tracking.json"))
    }

    /// Adds the module name to the config and saves it.
    pub fn track(&mut self, module_names: &[String]) -> Result<()> {
        // TODO(rbraunstein): Validate the module names and warn on bad names.
        self.modules.extend_from_slice(module_names);
        self.modules.sort();
        self.modules.dedup();
        self.print();
        self.clear_cache();
        Self::save(self)
    }

    /// Update the base module and saves it.
    pub fn trackbase(&mut self, base: &str) -> Result<()> {
        // TODO(rbraunstein): Validate the module names and warn on bad names.
        self.base = base.to_string();
        self.print();
        self.clear_cache();
        Self::save(self)
    }

    /// Removes the module name from the config and saves it.
    pub fn untrack(&mut self, module_names: &[String]) -> Result<()> {
        // TODO(rbraunstein): Report if not found?
        self.modules.retain(|m| !module_names.contains(m));
        self.print();
        self.clear_cache();
        Self::save(self)
    }

    // Store the config as json in the HOME/.config/asuite/adevice-tracking.json
    fn save(&self) -> Result<()> {
        let mut file = fs::File::create(Self::path(&self.home_dir)?)
            .context(format!("Creating file {:?}", Self::path(&self.home_dir)?))?;
        serde_json::to_writer_pretty(&mut file, &self).context("Writing config file")?;
        debug!("Wrote config file {:?}", Self::path(&self.home_dir)?);
        // Remove the dep cache because we will be changing the arguments to ninja
        // when we track or untrack new modules.

        Ok(())
    }

    /// Return all files that are part of the tracked set under ANDROID_PRODUCT_OUT.
    /// Implementation:
    ///   Runs `ninja` to get all transitive intermediate targets for `droid`.
    ///   These intermediate targets contain all the apks and .sos, etc that
    ///   that get packaged for flashing.
    ///   Filter all the inputs returned by ninja to just those under
    ///   ANDROID_PRODUCT_OUT and explicitly ask for modules in our tracking set.
    ///   Extra or stale files in ANDROID_PRODUCT_OUT from builds will not be part
    ///   of the result.
    ///   The combined.ninja file will be found under:
    ///        ${ANDROID_BUILD_TOP}/${OUT_DIR}/combined-${TARGET_PRODUCT}.ninja
    ///   Tracked files inside that file are relative to $OUT_DIR/target/product/*/
    ///   The final element of the path can be derived from the final element of ANDROID_PRODUCT_OUT,
    ///   but matching against */target/product/* is enough.
    /// Store all ninja deps in the cache and filter out partitions per run.
    pub fn tracked_files(&self, partitions: &Vec<PathBuf>) -> Result<Vec<String>> {
        if let Ok(cache) = self.read_cache() {
            Ok(filter_partitions(&cache, partitions))
        } else {
            let ninja_output = self.ninja_output(
                &self.src_root()?,
                &self.ninja_args(&self.target_product()?, &self.out_dir()),
            )?;
            let unfiltered_tracked_files = tracked_files(&ninja_output)?;
            self.write_cache(&unfiltered_tracked_files)
                .unwrap_or_else(|e| warn!("Error writing tracked file cache: {e}"));
            Ok(filter_partitions(&unfiltered_tracked_files, partitions))
        }
    }

    fn src_root(&self) -> Result<String> {
        std::env::var("ANDROID_BUILD_TOP")
            .context("ANDROID_BUILD_TOP must be set. Be sure to run lunch.")
    }

    fn target_product(&self) -> Result<String> {
        std::env::var("TARGET_PRODUCT").context("TARGET_PRODUCT must be set. Be sure to run lunch.")
    }

    fn out_dir(&self) -> String {
        std::env::var("OUT_DIR").unwrap_or("out".to_string())
    }

    // Prepare the ninja command line args, creating the right ninja file name and
    // appending all the modules.
    fn ninja_args(&self, target_product: &str, out_dir: &str) -> Vec<String> {
        // Create `ninja -f combined.ninja -t input -i BASE MOD1 MOD2 ....`
        // The `-i` for intermediary is what gives the PRODUCT_OUT files.
        let mut args = vec![
            "-f".to_string(),
            format!("{out_dir}/combined-{target_product}.ninja"),
            "-t".to_string(),
            "inputs".to_string(),
            "-i".to_string(),
            self.base.clone(),
        ];
        for module in self.modules.clone() {
            args.push(module);
        }
        args
    }

    // Call ninja.
    fn ninja_output(&self, src_root: &str, args: &[String]) -> Result<process::Output> {
        // TODO(rbraunstein): Deal with non-linux-x86.
        let path = "prebuilts/build-tools/linux-x86/bin/ninja";
        debug!("Running {path} {args:?}");
        process::Command::new(path)
            .current_dir(src_root)
            .args(args)
            .output()
            .context("Running ninja to get base files")
    }

    pub fn clear_cache(&self) {
        let path = self.cache_path();
        if path.is_err() {
            warn!("Error getting the cache path {:?}", path.err().unwrap());
            return;
        }
        match std::fs::remove_file(path.unwrap()) {
            Ok(_) => (),
            Err(e) => {
                // Probably the cache has already been cleared and we can't remove it again.
                debug!("Error clearing the cache {e}");
            }
        }
    }

    // If our cache (in the out_dir) is newer than the ninja file, then use it rather
    // than rerun ninja.  Saves about 2 secs.
    // Returns Err if cache not found or if cache is stale.
    // Otherwise returns the stdout from the ninja command.
    // TODO(rbraunstein): I don't think the cache is effective.  I think the combined
    // ninja file gets touched after every `m`.  Either use the subninja or just turn off caching.
    fn read_cache(&self) -> Result<Vec<String>> {
        let cache_path = self.cache_path()?;
        let ninja_file_path = PathBuf::from(&self.src_root()?)
            .join(self.out_dir())
            .join(format!("combined-{}.ninja", self.target_product()?));
        // cache file is too old.
        // TODO(rbraunstein): Need integration tests for this.
        // Adding and removing tracked modules affects the cache too.
        debug!("Reading cache {cache_path}");
        let cache_time = fs::metadata(&cache_path)?.modified()?;
        debug!("Reading ninja  {ninja_file_path:?}");
        let ninja_file_time = fs::metadata(ninja_file_path)?.modified()?;
        if cache_time.lt(&ninja_file_time) {
            debug!("Cache is too old: {cache_time:?}, ninja file time {ninja_file_time:?}");
            anyhow::bail!("cache is stale");
        }
        debug!("Using ninja file cache");
        Ok(fs::read_to_string(&cache_path)?.split('\n').map(|s| s.to_string()).collect())
    }

    fn cache_path(&self) -> Result<String> {
        Ok([
            self.src_root()?,
            self.out_dir(),
            format!("adevice-ninja-deps-{}.cache", self.target_product()?),
        ]
        // TODO(rbraunstein): Fix OS separator.
        .join("/"))
    }

    // Unconditionally write the given byte stream to the cache file
    // overwriting whatever is there.
    fn write_cache(&self, data: &[String]) -> Result<()> {
        let cache_path = self.cache_path()?;
        debug!("Wrote cache file: {cache_path:?}");
        fs::write(cache_path, data.join("\n"))?;
        Ok(())
    }
}

/// Iterate through the `ninja -t input -i MOD...` output
/// to find files in the PRODUCT_OUT directory.
fn tracked_files(output: &process::Output) -> Result<Vec<String>> {
    let stdout = &output.stdout;
    let stderr = &output.stderr;
    debug!("NINJA calculated deps: {}", stdout.len());
    if output.status.code().unwrap() > 0 || !stderr.is_empty() {
        warn!("code: {} {:?}", output.status, String::from_utf8(stderr.to_owned()));
    }
    Ok(String::from_utf8(stdout.to_owned())?
        .lines()
        .filter_map(|line| {
            if let Some(device_path) = strip_product_prefix(line) {
                return Some(device_path);
            }
            None
        })
        .collect())
}

/// Iterate through all ninja deps which are already filtered to and relative to ANDROID_PRODUCT_OUT
/// Return only those whose path starts with a partition.
fn filter_partitions(ninja_deps: &[String], partitions: &Vec<PathBuf>) -> Vec<String> {
    ninja_deps
        .iter()
        .filter_map(|dep| {
            for p in partitions {
                if PathBuf::from(dep).starts_with(p) {
                    return Some(dep.clone());
                }
            }
            None
        })
        .collect()
}

// The ninja output for the files we are interested in will look like this:
//     % OUT_DIR=innie m nothing
//     % (cd $ANDROID_BUILD_TOP;prebuilts/build-tools/linux-x86/bin/ninja -f innie/combined-aosp_cf_x86_64_phone.ninja -t inputs -i droid | grep innie/target/product/vsoc_x86_64/system) | grep apk | head
//     innie/target/product/vsoc_x86_64/system/app/BasicDreams/BasicDreams.apk
//     innie/target/product/vsoc_x86_64/system/app/BluetoothMidiService/BluetoothMidiService.apk
//     innie/target/product/vsoc_x86_64/system/app/BookmarkProvider/BookmarkProvider.apk
//     innie/target/product/vsoc_x86_64/system/app/CameraExtensionsProxy/CameraExtensionsProxy.apk
// Match any files with target/product as the second and third dir paths and capture
// everything from 5th path element to the end.
lazy_static! {
    static ref NINJA_OUT_PATH_MATCHER: Regex =
        Regex::new(r"^[^/]+/target/product/[^/]+/(.+)$").expect("regex does not compile");
}

fn strip_product_prefix(path: &str) -> Option<String> {
    NINJA_OUT_PATH_MATCHER.captures(path).map(|x| x[1].to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn load_creates_new_config_with_droid() -> Result<()> {
        let home_dir = TempDir::new()?;
        let config = Config::load_or_default(path(&home_dir));
        assert_eq!("droid", config?.base);
        Ok(())
    }

    #[test]
    fn track_updates_config_file() -> Result<()> {
        let home_dir = TempDir::new()?;
        let mut config = Config::load_or_default(path(&home_dir))?;
        config.track(&["supermod".to_string()])?;
        config.track(&["another".to_string()])?;
        // Updates in-memory version, which gets sorted and deduped.
        assert_eq!(vec!["another".to_string(), "supermod".to_string()], config.modules);

        // Check the disk version too.
        let config2 = Config::load_or_default(path(&home_dir))?;
        assert_eq!(config, config2);
        Ok(())
    }

    #[test]
    fn untrack_updates_config() -> Result<()> {
        let home_dir = TempDir::new()?;
        std::fs::write(
            Config::path(&path(&home_dir)).context("Writing config")?,
            r#"{"base": "droid",  "modules": [ "mod_one", "mod_two" ]}"#,
        )?;
        let mut config = Config::load_or_default(path(&home_dir)).context("LOAD")?;
        assert_eq!(2, config.modules.len());
        // Updates in-memory version.
        config.untrack(&["mod_two".to_string()]).context("UNTRACK")?;
        assert_eq!(vec!["mod_one"], config.modules);
        // Updates on-disk version.
        Ok(())
    }

    #[test]
    fn ninja_args_updated_based_on_config() {
        let config = Config { base: s("DROID"), modules: vec![s("ADEVICE_FP")], home_dir: s("") };
        assert_eq!(
            crate::commands::split_string(
                "-f outdir/combined-lynx.ninja -t inputs -i DROID ADEVICE_FP"
            ),
            config.ninja_args("lynx", "outdir")
        );
        // Find the args passed to ninja
    }

    #[test]
    fn ninja_output_filtered_to_android_product_out() -> Result<()> {
        // Ensure only paths matching */target/product/ remain
        let fake_out = vec![
            // 2 good ones
            "innie/target/product/vsoc_x86_64/system/app/BasicDreams/BasicDreams.apk\n",
            "innie/target/product/vsoc_x86_64/system/app/BookmarkProvider/BookmarkProvider.apk\n",
            // Target/product not at right position
            "innie/nested/target/product/vsoc_x86_64/system/NOT_FOUND\n",
            // Different partition
            "innie/target/product/vsoc_x86_64/OTHER_PARTITION/app/BasicDreams/BasicDreams2.apk\n",
            // Good again.
            "innie/target/product/vsoc_x86_64/system_ext/ok_file\n",
        ];

        let output = process::Command::new("echo")
            .args(&fake_out)
            .output()
            .context("Running ECHO to generate output")?;

        assert_eq!(
            vec![
                "system/app/BasicDreams/BasicDreams.apk",
                "system/app/BookmarkProvider/BookmarkProvider.apk",
                "OTHER_PARTITION/app/BasicDreams/BasicDreams2.apk",
                "system_ext/ok_file",
            ],
            tracked_files(&output)?
        );
        Ok(())
    }

    #[test]
    fn test_partition_filtering() {
        let ninja_deps = vec![
            "system/file1".to_string(),
            "system_ext/file2".to_string(),
            "file3".to_string(),
            "system/dir2/file1".to_string(),
            "data/sys/file4".to_string(),
        ];
        assert_eq!(
            vec![
                "system/file1".to_string(),
                "system/dir2/file1".to_string(),
                "data/sys/file4".to_string(),
            ],
            crate::tracking::filter_partitions(
                &ninja_deps,
                &vec![PathBuf::from("system"), PathBuf::from("data")]
            )
        );
    }

    // Ensure we match the whole path component, i.e. "sys" should not match system.
    #[test]
    fn test_partition_filtering_partition_name_matches_path_component() {
        let ninja_deps = vec![
            "system/file1".to_string(),
            "system_ext/file2".to_string(),
            "file3".to_string(),
            "data/sys/file4".to_string(),
        ];
        assert_eq!(
            Vec::<String>::new(),
            crate::tracking::filter_partitions(&ninja_deps, &vec![PathBuf::from("sys")])
        );
    }

    // Convert TempDir to string we can use for fs::write/read.
    fn path(dir: &TempDir) -> String {
        dir.path().display().to_string()
    }

    // Tired of typing to_string()
    fn s(str: &str) -> String {
        str.to_string()
    }
}
