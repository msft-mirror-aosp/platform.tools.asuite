//! Crate to provide the AppClass for an installed file.
/// The current implementation parses module info and creates
/// a map from installed file to its highest ranking "class".
/// Later the AppClass will be mapped to a restart level.
use anyhow::{Context, Result};
use lazy_static::lazy_static;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::ffi::OsStr;
use std::fs;
use std::io::{BufReader, Read};
use std::path::Path;

pub struct RestartChooser {
    // Installed file path -> AppClass.
    restart_types: HashMap<String, RestartType>,
}

impl RestartChooser {
    // Construct the RestartChooser from a path to module-info.json.
    pub fn from(json_path: &Path) -> Result<Self> {
        let file = fs::File::open(json_path)
            .with_context(|| format!("Error opening module-info.json {}", json_path.display()))?;
        Self::new(BufReader::new(file))
    }

    // Construct the RestartChooser from json reader.
    pub fn new<R: Read>(reader: BufReader<R>) -> Result<Self> {
        Ok(RestartChooser { restart_types: Self::restart_type_for_all_installed_files(reader)? })
    }

    // TODO(rbraunstein): Create a trait for this to indicate we can replace with an alternative
    // implementation.
    pub fn restart_type(&self, installed_file: &str) -> Option<RestartType> {
        self.restart_types.get(installed_file).cloned()
    }

    // Parse all of module-info.json and for all the installed files for a module,
    // store the app_class[es] of the module.
    fn restart_type_for_all_installed_files<R: Read>(
        reader: BufReader<R>,
    ) -> Result<HashMap<String, RestartType>> {
        let info: HashMap<String, Module> =
            serde_json::from_reader(reader).context("Parsing module-info")?;

        let mut app_classes: HashMap<String, RestartType> = HashMap::new();
        for (_, module) in info.iter() {
            let restart_type = restart_type_for_classes(&module.class);
            for installed_file in module.installed.iter() {
                let device_path: String =
                    Self::strip_product_prefix(installed_file).unwrap_or("".to_string());
                if device_path.is_empty() {
                    // TODO(rbraunstein): Revisit what to do with files outside the PRODUCT_OUT tree
                    // when we have update sets.
                    continue;
                }
                if should_force_reboot_on_filename(&device_path) {
                    app_classes.insert(device_path, RestartType::Reboot);
                    continue;
                }
                if can_soft_restart_based_on_filename(&device_path) {
                    app_classes.insert(device_path, RestartType::SoftRestart);
                    continue;
                }
                // use restart_type from module classes
                app_classes.insert(device_path, restart_type.clone());
            }
        }
        Ok(app_classes)
    }

    fn strip_product_prefix(path: &str) -> Option<String> {
        PATH_MATCHER.captures(path).map(|x| x[1].to_string())
    }
}

// Some file extensions only need a SoftRestart due to being
// reloaded when zygote restarts on `adb shell start`
const SOFT_RESTART_FILE_EXTS: [&str; 3] = ["art", "oat", "vdex"];
fn can_soft_restart_based_on_filename(filename: &str) -> bool {
    let ext = Path::new(filename).extension().and_then(OsStr::to_str).unwrap_or("");
    SOFT_RESTART_FILE_EXTS.contains(&ext)
}

const REBOOTS_FILE_EXTS: [&str; 1] = ["rc"];
fn should_force_reboot_on_filename(filename: &str) -> bool {
    let ext = Path::new(filename).extension().and_then(OsStr::to_str).unwrap_or("");
    REBOOTS_FILE_EXTS.contains(&ext)
}

// Given the class element from module in module info,
// translate it to the most conservate restart type.
// ["SHARED_LIBRARIES"] -> SoftRestart
// ["STATIC_LIBRARIES", "ETC"] -> Reboot    # ETC implies reboot
// TODO(rbraunstein): Implement None and Custom
// for modules that don't need restarts or that need to kill
// a particular running process.
const SOFT_RESET_GROUP: [&str; 4] = ["APPS", "EXECUTABLES", "JAVA_LIBRARIES", "SHARED_LIBRARIES"];
fn restart_type_for_classes(classes: &[String]) -> RestartType {
    for class in classes {
        if !SOFT_RESET_GROUP.contains(&class.as_str()) {
            return RestartType::Reboot;
        }
    }
    RestartType::SoftRestart
}

// The files in module-info are relative to OUT_DIR. Re-root them at PRODUCT_OUT.
//  "out/target/product/vsoc_x86_64/system/priv-app/CarService/CarService.apk"
//       ->                         system/priv-app/CarService/CarService.apk"
// TODO(rbraunstein): Test with running `m` with different OUT/OUT_DIR settings
// to verify if this works or see if there is a better way, like stripe ANDROID_BUILD_TOP
// from OUT_DIR (if it exists).

// Return the path relative to ANDROID_BUILD_TOP that gets put into
// module-info
// TODO(rbraunstein): Should we look at the variable soong saved when creating
// module-info rather than check the env?
//  build/soong/soong_ui.bash --dumpvar-mode OUT_DIR?
#[allow(unused)]
fn get_out_dir_from_env() -> String {
    match std::env::var("OUT_DIR") {
        Ok(x) if !x.is_empty() => x,
        _ => "out".to_string(),
    }
}

lazy_static! {
    static ref PATH_MATCHER: Regex =
        Regex::new(r"/target/product/[^/]+/(.+)$").expect("regex does not compile");
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Module {
    pub class: Vec<String>,
    pub installed: Vec<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub enum RestartType {
    /// The device needs to be rebooted
    Reboot,
    /// Adb shell restart will suffice
    SoftRestart,
    /// No restarts needed.
    None,
    // A force kill command will be enough.
    // RestartBinary,
}

#[cfg(test)]
mod tests {
    use super::*;
    // use std::collections::BTreeSet;
    use std::path::PathBuf;
    const SAMPLE_MODULE_INFO: &str = r#"{
       "adevice": {
             "class": ["EXECUTABLES"],
             "path": ["tools/asuite/adevice"],
             "tags": ["optional"],
             "installed": ["out/host/linux-x86/bin/adevice"],
             "module_name": "adevice"},
       "CarService": {
             "class": ["APPS"], "path": ["packages/services/Car/service-builtin"],
             "tags": ["optional"],
             "installed": ["out/target/product/vsoc_x86_64/system/priv-app/CarService/CarService.apk",
                           "out/target/product/vsoc_x86_64/system/priv-app/CarService/lib/x86_64/libcarservicejni.so",
                           "out/target/product/vsoc_x86_64/system_other/system/priv-app/CarService/oat/x86_64/CarService.odex",
                           "out/target/product/vsoc_x86_64/system_other/system/priv-app/CarService/oat/x86_64/CarService.vdex"] },
       "CarServiceCrashDumpTest": {
             "class": ["JAVA_LIBRARIES"],
             "installed": ["out/host/linux-x86/framework/CarServiceCrashDumpTest.jar"] },
       "CarServiceOverlayCuttleFish": {
             "class": ["ETC"],
             "installed": ["out/target/product/vsoc_x86_64/product/overlay/CarServiceOverlayCuttleFish.apk"]
        },
       "DefaultVehicleHal": {
             "class": ["SHARED_LIBRARIES", "STATIC_LIBRARIES"],
             "installed": ["out/target/product/vsoc_x86_64/vendor/lib64/DefaultVehicleHal.so"],
             "module_name": "DefaultVehicleHal"}
    }"#;

    // Create a build_system with above data.
    fn sample_build_system() -> RestartChooser {
        RestartChooser::new(BufReader::new(SAMPLE_MODULE_INFO.as_bytes())).unwrap()
    }

    #[test]
    fn missing_module_info_file() {
        match RestartChooser::from(&PathBuf::from("bogus_path.json")) {
            Ok(_) => panic!("Should have failed"),
            Err(e) => assert!(
                e.to_string().starts_with("Error opening module-info.json bogus_path.json"),
                "{:?}",
                e,
            ),
        }
    }

    #[test]
    fn malformed_module_info() {
        let module_info_json = "{\nbad";
        match RestartChooser::new(BufReader::new(module_info_json.as_bytes())) {
            Ok(_) => panic!("Should have failed"),
            Err(e) => {
                assert!(e.to_string().starts_with("Parsing module-info"), "{:?}", e);
                assert!(e.root_cause().to_string().starts_with("key must be a string"), "{:?}", e);
            }
        }
    }

    #[test]
    fn module_with_multiple_installed_files() {
        for installed_file in &[
            "system/priv-app/CarService/CarService.apk",
            "system/priv-app/CarService/lib/x86_64/libcarservicejni.so",
            "system_other/system/priv-app/CarService/oat/x86_64/CarService.odex",
            "system_other/system/priv-app/CarService/oat/x86_64/CarService.vdex",
        ] {
            // Those all one module with APPS, which are SoftRestart
            assert_eq!(
                Some(RestartType::SoftRestart),
                sample_build_system().restart_type(installed_file),
                "Wrong class for {}",
                installed_file
            );
        }
    }

    #[test]
    fn host_files_should_not_be_found() {
        assert_eq!(None, sample_build_system().restart_type("out/host/linux-x86/bin/adevice"));
    }

    #[test]
    fn reboot_for_module_with_shared_and_static_lib() {
        assert_eq!(
            Some(RestartType::Reboot),
            sample_build_system().restart_type("vendor/lib64/DefaultVehicleHal.so")
        );
    }

    #[test]
    fn module_with_multiple_installed_files_and_multiple_app_classes() {
        let json = r#"{
        "WeirdModule": {
             "class": ["SHARED_LIBRARIES", "ETC", "JAVA_LIBRARIES"],
             "installed": ["/some/out2/target/product/vsoc_x86_64/vendor/lib64/Weird.so",
                           "bad/file/path",
                           "out/target/product/vsoc_x86_64/vendor/good/file/path"]
        }}"#;
        let build_system = RestartChooser::new(BufReader::new(json.as_bytes())).unwrap();
        // Work on absolute out paths, as long as they still have target/product in them.
        assert_eq!(Some(RestartType::Reboot), build_system.restart_type("vendor/lib64/Weird.so"));
        // One installed file should not interfere with another if that installed file is not
        // on the device.
        assert_eq!(None, build_system.restart_type("bad/file/path"));
        assert_eq!(Some(RestartType::Reboot), build_system.restart_type("vendor/good/file/path"));
    }

    #[test]
    fn unknown_class_returns_reboot() {
        let json = r#"{
        "WeirdModule": {
             "class": ["SOMETHING_NEW_DEFINED_MODULE_INFO"],
             "installed": ["out/target/product/vsoc_x86_64/vendor/good/file/path"]
        }}"#;
        let build_system = RestartChooser::new(BufReader::new(json.as_bytes())).unwrap();
        assert_eq!(Some(RestartType::Reboot), build_system.restart_type("vendor/good/file/path"));
    }

    #[test]
    fn soft_restart_for_certain_file_extensions() {
        let json = r#"{
        "SampleModule": {
             "class": ["SOMETHING_NEW_DEFINED_MODULE_INFO"],
             "installed": ["out/target/product/vsoc_x86_64/vendor/good/file/path.art",
                           "out/target/product/vsoc_x86_64/vendor/good/file/path.oat",
                           "out/target/product/vsoc_x86_64/vendor/good/file/path.vdex",
                           "out/target/product/vsoc_x86_64/vendor/good/file/path.extraart",
                           "out/target/product/vsoc_x86_64/vendor/good/file/path.artextra",
                           "out/target/product/vsoc_x86_64/vendor/good/file/path"]
        }}"#;
        let build_system = RestartChooser::new(BufReader::new(json.as_bytes())).unwrap();

        // Have extensions in SOFT_RESET_FILE_EXTS
        for installed_file in &[
            "vendor/good/file/path.art",
            "vendor/good/file/path.oat",
            "vendor/good/file/path.vdex",
        ] {
            assert_eq!(
                Some(RestartType::SoftRestart),
                build_system.restart_type(installed_file),
                "Wrong class for {}",
                installed_file
            );
        }

        // Do NOT have extensions in SOFT_RESET_FILE_EXTS (REBOOT due to module class)
        for installed_file in &[
            "vendor/good/file/path.extraart",
            "vendor/good/file/path.artextra",
            "vendor/good/file/path",
        ] {
            assert_eq!(
                Some(RestartType::Reboot),
                build_system.restart_type(installed_file),
                "Wrong class for {}",
                installed_file
            );
        }
    }

    #[test]
    fn binary_with_rc_file_reboots_for_rc() {
        let json = r#"{
        "SampleModule": {
             "class": ["EXECUTABLES"],
             "installed": ["out/target/product/vsoc_x86_64/system/bin/surfaceflinger",
                           "out/target/product/vsoc_x86_64/system/bin/surfaceflinger.rc"]
        }}"#;
        let build_system = RestartChooser::new(BufReader::new(json.as_bytes())).unwrap();
        assert_eq!(
            Some(RestartType::Reboot),
            build_system.restart_type("system/bin/surfaceflinger.rc")
        );
        assert_eq!(
            Some(RestartType::SoftRestart),
            build_system.restart_type("system/bin/surfaceflinger")
        );
    }

    #[test]
    fn missing_installed_returns_none() {
        assert_eq!(None, sample_build_system().restart_type("bogus_file"));
    }
}
